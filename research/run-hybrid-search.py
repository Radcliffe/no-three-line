#!/usr/bin/env python3
"""Run factor local search followed by exact conflict-neighborhood repair."""

import argparse
import copy
import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


SUMMARY_PATTERN = re.compile(r"(?:^| )([a-z_]+)=([^ ]+)")
PROGRESS_PATTERN = re.compile(r"progress_ms=(\d+) best_energy=(\d+) thread=(\d+)")
MOVE_PATTERN = re.compile(r"([a-z]+):(\d+)/(\d+)")


def parse_sat_lane(value):
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "SAT lane must be SOLVER:COVER:HALO:EXPAND"
        )
    solver, initial_policy, halo_text, expand_text = parts
    if not solver:
        raise argparse.ArgumentTypeError("SAT lane solver cannot be empty")
    if initial_policy not in {
        "greedy",
        "greedy-conflict",
        "greedy-random",
        "minimum",
    }:
        raise argparse.ArgumentTypeError(f"unknown SAT lane cover {initial_policy!r}")
    try:
        halo = int(halo_text)
        expand = int(expand_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "SAT lane halo and expansion must be integers"
        ) from error
    if halo < 0 or expand < 1:
        raise argparse.ArgumentTypeError(
            "SAT lane halo must be nonnegative and expansion positive"
        )
    return {
        "solver": solver,
        "initial_policy": initial_policy,
        "halo": halo,
        "expand": expand,
    }


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="compiled rot4-factor-search executable")
    parser.add_argument("n", type=int)
    parser.add_argument("--local-seconds", type=int, default=20)
    parser.add_argument("--repair-seconds", type=float, default=20.0)
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="alternate local search and exact repair, splitting both total budgets equally",
    )
    parser.add_argument(
        "--repair-schedule",
        choices=("each", "final"),
        default="each",
        help="repair after every local round or spend the full repair budget after the last",
    )
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--local-stagnation-ms",
        type=int,
        default=0,
        help="restart a local trajectory from the incumbent after this many milliseconds without improvement",
    )
    parser.add_argument(
        "--local-perturb-step",
        type=int,
        default=3,
        help="additional incumbent perturbation moves per local-search worker",
    )
    parser.add_argument(
        "--local-four-edge-percent",
        type=int,
        default=0,
        help="percentage of local and perturbation move attempts using four-edge reconnection",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--initial-incumbent",
        help="compact rot4 code used to seed the first local-search round",
    )
    parser.add_argument(
        "--repair-backend",
        choices=("sat", "z3", "portfolio"),
        default="sat",
        help="exact backend; portfolio runs every requested SAT variant and Z3 concurrently",
    )
    parser.add_argument(
        "--sat-solver",
        action="append",
        help="SAT engine; repeat in portfolio mode (default: cadical195)",
    )
    parser.add_argument(
        "--sat-lane",
        action="append",
        type=parse_sat_lane,
        metavar="SOLVER:COVER:HALO:EXPAND",
        help="explicit raw-SAT portfolio lane; repeat to avoid a Cartesian product",
    )
    parser.add_argument("--sat-conflict-chunk", type=int, default=1_000)
    parser.add_argument("--sat-propagation-chunk", type=int, default=1_000_000)
    parser.add_argument(
        "--sat-sbva",
        nargs="?",
        const="sbva",
        help="preprocess the SAT repair CNF with SBVA (PATH defaults to sbva in PATH)",
    )
    parser.add_argument(
        "--sat-initial-cover-policy",
        action="append",
        choices=("greedy", "greedy-conflict", "greedy-random", "minimum"),
        help=(
            "initial violated-line cover; repeat in portfolio mode "
            "(default: greedy)"
        ),
    )
    parser.add_argument(
        "--sat-core-expansion-policy",
        choices=("score", "marginal", "random"),
        default="score",
    )
    parser.add_argument(
        "--sat-split-rng-streams",
        action="store_true",
        help="isolate cover, core-expansion, and lazy-cut random choices",
    )
    parser.add_argument("--lift-from", type=int)
    parser.add_argument("--solutions", type=Path, default=Path("optimal-solutions.generated.js"))
    parser.add_argument("--core-vertices", type=int, default=6)
    parser.add_argument("--halo-vertices", type=int, default=2)
    parser.add_argument("--free-fraction", type=float, default=0.15)
    parser.add_argument("--expand-by", type=int, default=2)
    parser.add_argument(
        "--output",
        type=Path,
        help="write the complete JSON result to this path instead of standard output",
    )
    arguments = parser.parse_args()
    explicit_sat_solvers = arguments.sat_solver is not None
    explicit_cover_policies = arguments.sat_initial_cover_policy is not None
    arguments.sat_solver = arguments.sat_solver or ["cadical195"]
    arguments.sat_initial_cover_policy = arguments.sat_initial_cover_policy or [
        "greedy"
    ]
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if arguments.local_seconds < 1 or arguments.repair_seconds <= 0 or arguments.threads < 1:
        parser.error("time limits and thread count must be positive")
    if arguments.local_stagnation_ms < 0:
        parser.error("--local-stagnation-ms must be nonnegative")
    if arguments.local_perturb_step < 0:
        parser.error("--local-perturb-step must be nonnegative")
    if not 0 <= arguments.local_four_edge_percent <= 100:
        parser.error("--local-four-edge-percent must be between 0 and 100")
    if arguments.rounds < 1:
        parser.error("--rounds must be positive")
    if arguments.local_seconds < arguments.rounds:
        parser.error("--local-seconds must allow at least one second per round")
    if arguments.sat_conflict_chunk < 1 or arguments.sat_propagation_chunk < 1:
        parser.error("SAT budget chunks must be positive")
    if len(set(arguments.sat_solver)) != len(arguments.sat_solver):
        parser.error("--sat-solver values must be unique")
    if len(set(arguments.sat_initial_cover_policy)) != len(
        arguments.sat_initial_cover_policy
    ):
        parser.error("--sat-initial-cover-policy values must be unique")
    if arguments.sat_lane:
        lane_keys = [
            (
                lane["solver"],
                lane["initial_policy"],
                lane["halo"],
                lane["expand"],
            )
            for lane in arguments.sat_lane
        ]
        if len(set(lane_keys)) != len(lane_keys):
            parser.error("--sat-lane values must be unique")
        if explicit_sat_solvers or explicit_cover_policies or arguments.sat_sbva:
            parser.error(
                "--sat-lane cannot be combined with --sat-solver, "
                "--sat-initial-cover-policy, or --sat-sbva"
            )
        if arguments.repair_backend == "z3":
            parser.error("--sat-lane requires a SAT or portfolio repair backend")
        if arguments.repair_backend != "portfolio" and len(arguments.sat_lane) > 1:
            parser.error("repeat --sat-lane only with --repair-backend portfolio")
    if arguments.repair_backend != "portfolio" and len(arguments.sat_solver) > 1:
        parser.error("repeat --sat-solver only with --repair-backend portfolio")
    if (
        arguments.repair_backend != "portfolio"
        and len(arguments.sat_initial_cover_policy) > 1
    ):
        parser.error(
            "repeat --sat-initial-cover-policy only with --repair-backend portfolio"
        )
    return arguments


def run_local(arguments, project_root, incumbent=None):
    command = [
        str(arguments.executable.resolve()),
        str(arguments.n),
        str(arguments.local_seconds),
        str(arguments.threads),
        "--seed",
        str(arguments.seed),
    ]
    if incumbent is not None:
        command.extend(["--incumbent", incumbent])
    if arguments.local_stagnation_ms:
        command.extend(["--stagnation-ms", str(arguments.local_stagnation_ms)])
    if arguments.local_perturb_step != 3:
        command.extend(["--perturb-step", str(arguments.local_perturb_step)])
    if arguments.local_four_edge_percent:
        command.extend(
            ["--four-edge-percent", str(arguments.local_four_edge_percent)]
        )
    if arguments.lift_from is not None:
        command.extend(
            [
                "--lift-from",
                str(arguments.lift_from),
                "--solutions",
                str(arguments.solutions),
            ]
        )
    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"local search failed with exit {completed.returncode}:\n{completed.stderr}")
    lines = completed.stdout.splitlines()
    summary_line = next((line for line in lines if line.startswith("n=")), None)
    moves_line = next((line for line in lines if line.startswith("moves=")), "")
    code_line = next((line for line in lines if line.startswith("best_code=")), None)
    if summary_line is None or code_line is None:
        raise RuntimeError(f"local search emitted an incomplete result:\n{completed.stdout}")
    summary = dict(SUMMARY_PATTERN.findall(summary_line))
    progress = [
        {
            "milliseconds": int(match.group(1)),
            "energy": int(match.group(2)),
            "thread": int(match.group(3)),
        }
        for line in lines
        if (match := PROGRESS_PATTERN.fullmatch(line))
    ]
    moves = {
        name: {
            "accepted": int(accepted),
            "attempted": int(attempted),
        }
        for name, accepted, attempted in MOVE_PATTERN.findall(moves_line)
    }
    return {
        "bestEnergy": int(summary["best_energy"]),
        "initialEnergy": float(summary["initial_energy"]),
        "iterations": int(summary["iterations"]),
        "restarts": int(summary["restarts"]),
        "stagnationRestarts": int(summary.get("stagnation_restarts", 0)),
        "perturbStep": int(summary.get("perturb_step", 3)),
        "fourEdgePercent": int(summary.get("four_edge_percent", 0)),
        "moves": moves,
        "bestCode": code_line.removeprefix("best_code="),
        "progress": progress,
    }


def repair_specs(arguments):
    if arguments.repair_backend == "z3":
        return [{"name": "z3", "kind": "z3"}]
    if arguments.sat_lane:
        specs = [
            {
                "name": (
                    f"sat-{lane['solver']}-cover-{lane['initial_policy']}"
                    f"-h{lane['halo']}-x{lane['expand']}"
                ),
                "kind": "sat",
                "solver": lane["solver"],
                "sbva": False,
                "initial_policy": lane["initial_policy"],
                "halo": lane["halo"],
                "expand": lane["expand"],
            }
            for lane in arguments.sat_lane
        ]
        if arguments.repair_backend == "portfolio":
            specs.append({"name": "z3", "kind": "z3"})
        return specs
    if arguments.repair_backend == "sat":
        return [
            {
                "name": "sat-sbva" if arguments.sat_sbva else "sat",
                "kind": "sat",
                "solver": arguments.sat_solver[0],
                "sbva": bool(arguments.sat_sbva),
                "initial_policy": arguments.sat_initial_cover_policy[0],
            }
        ]

    qualify_solver = len(arguments.sat_solver) > 1
    qualify_cover = len(arguments.sat_initial_cover_policy) > 1
    specs = []
    for solver in arguments.sat_solver:
        solver_base = f"sat-{solver}" if qualify_solver else "sat"
        for initial_policy in arguments.sat_initial_cover_policy:
            base = (
                f"{solver_base}-cover-{initial_policy}"
                if qualify_cover
                else solver_base
            )
            specs.append(
                {
                    "name": base,
                    "kind": "sat",
                    "solver": solver,
                    "sbva": False,
                    "initial_policy": initial_policy,
                }
            )
            if arguments.sat_sbva:
                specs.append(
                    {
                        "name": f"{base}-sbva",
                        "kind": "sat",
                        "solver": solver,
                        "sbva": True,
                        "initial_policy": initial_policy,
                    }
                )
    specs.append({"name": "z3", "kind": "z3"})
    return specs


def repair_command(arguments, spec, code):
    script = (
        "research/rot4-sat-repair.py"
        if spec["kind"] == "sat"
        else "research/rot4-lazy-z3.py"
    )
    command = [
        sys.executable,
        script,
        str(arguments.n),
        "--seconds",
        str(arguments.repair_seconds),
        "--seed",
        str(arguments.seed),
        "--incumbent",
        code,
        "--core-vertices",
        str(arguments.core_vertices),
        "--halo-vertices",
        str(spec.get("halo", arguments.halo_vertices)),
        "--free-fraction",
        str(arguments.free_fraction),
        "--expand-by",
        str(spec.get("expand", arguments.expand_by)),
    ]
    if spec["kind"] == "sat":
        command.extend(
            [
                "--solver",
                spec["solver"],
                "--conflict-chunk",
                str(arguments.sat_conflict_chunk),
                "--propagation-chunk",
                str(arguments.sat_propagation_chunk),
                "--initial-cover-policy",
                spec["initial_policy"],
                "--core-expansion-policy",
                arguments.sat_core_expansion_policy,
            ]
        )
        if arguments.sat_lane or arguments.sat_split_rng_streams or len(
            arguments.sat_initial_cover_policy
        ) > 1:
            command.append("--split-rng-streams")
        if spec["sbva"]:
            command.extend(["--sbva", arguments.sat_sbva])
    return command


def run_one_repair(arguments, project_root, code, spec):
    completed = subprocess.run(
        repair_command(arguments, spec, code),
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{spec['name']} repair failed with exit {completed.returncode}:\n"
            f"{completed.stderr}"
        )
    return json.loads(completed.stdout)


def result_energy(result):
    return 0 if result.get("status") == "sat" else result.get("best_triples", math.inf)


def run_repair(arguments, project_root, code):
    specs = repair_specs(arguments)
    if arguments.repair_backend != "portfolio":
        return run_one_repair(arguments, project_root, code, specs[0])

    with ThreadPoolExecutor(max_workers=len(specs)) as executor:
        futures = {
            spec["name"]: executor.submit(
                run_one_repair,
                arguments,
                project_root,
                code,
                spec,
            )
            for spec in specs
        }
        results = {backend: future.result() for backend, future in futures.items()}
    winner = min(results, key=lambda backend: result_energy(results[backend]))
    winner_result = results[winner]
    combined = {
        "backend": "portfolio",
        "winner": winner,
        "status": winner_result["status"],
        "best_triples": result_energy(winner_result),
        "best_bad_lines": winner_result.get("best_bad_lines"),
        "results": results,
    }
    if winner_result.get("status") == "sat":
        combined["code"] = winner_result["code"]
    else:
        combined["best_code"] = winner_result.get("best_code", code)
    return combined


def validate(project_root, code):
    completed = subprocess.run(
        ["node", "research/validate-rot4-code.js", code],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    result = json.loads(completed.stdout or completed.stderr)
    if completed.returncode != 0 or not result.get("valid"):
        raise RuntimeError(f"dual validation failed: {result}")
    return result


def main():
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parent.parent
    base_local_seconds, extra_local_seconds = divmod(
        arguments.local_seconds, arguments.rounds
    )
    local_budgets = [
        base_local_seconds + (round_index < extra_local_seconds)
        for round_index in range(arguments.rounds)
    ]
    repair_budget = (
        arguments.repair_seconds / arguments.rounds
        if arguments.repair_schedule == "each"
        else arguments.repair_seconds
    )

    final_energy = math.inf
    final_code = arguments.initial_incumbent
    local = None
    repair = None
    round_results = []
    for round_index, local_budget in enumerate(local_budgets):
        incoming_code = final_code
        incoming_energy = None if math.isinf(final_energy) else final_energy
        round_arguments = copy.copy(arguments)
        round_arguments.local_seconds = local_budget
        round_arguments.repair_seconds = repair_budget
        round_arguments.seed = arguments.seed + round_index

        local = run_local(round_arguments, project_root, incoming_code)
        if local["bestEnergy"] < final_energy:
            final_energy = local["bestEnergy"]
            final_code = local["bestCode"]

        repair = None
        repair_input_code = final_code
        repair_input_energy = final_energy
        should_repair = (
            arguments.repair_schedule == "each"
            or round_index == arguments.rounds - 1
        )
        if final_energy > 0 and should_repair:
            repair = run_repair(round_arguments, project_root, final_code)
            repair_energy = result_energy(repair)
            if repair.get("status") == "sat":
                final_energy = 0
                final_code = repair["code"]
            elif repair_energy < final_energy:
                final_energy = repair_energy
                final_code = repair["best_code"]

        round_results.append(
            {
                "round": round_index + 1,
                "seed": round_arguments.seed,
                "localSeconds": local_budget,
                "repairSeconds": repair_budget if should_repair else 0.0,
                "incomingEnergy": incoming_energy,
                "incomingCode": incoming_code,
                "local": local,
                "repairInputEnergy": repair_input_energy,
                "repairInputCode": repair_input_code,
                "repair": repair,
                "endingEnergy": final_energy,
                "endingCode": final_code,
            }
        )
        if final_energy == 0:
            break

    validation = validate(project_root, final_code) if final_energy == 0 else None
    rendered = json.dumps(
        {
            "n": arguments.n,
            "seed": arguments.seed,
            "requestedRounds": arguments.rounds,
            "completedRounds": len(round_results),
            "repairSchedule": arguments.repair_schedule,
            "totalLocalSeconds": arguments.local_seconds,
            "totalRepairSeconds": arguments.repair_seconds,
            "solved": final_energy == 0,
            "finalEnergy": final_energy,
            "finalCode": final_code,
            "local": local,
            "repair": repair,
            "roundResults": round_results,
            "validation": validation,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
