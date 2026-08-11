#!/usr/bin/env python3
"""Compare one-shot and iterated local-search/exact-repair schedules."""

import argparse
import datetime
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_LANES = (
    "glucose42:minimum:4:2",
    "glucose42:greedy-random:0:4",
    "cadical195:greedy-random:4:2",
    "cadical195:minimum:0:4",
)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("n", type=int)
    parser.add_argument("--factor-benchmark", type=Path, required=True)
    parser.add_argument("--rounds", action="append", type=int)
    parser.add_argument(
        "--configuration",
        action="append",
        metavar="ROUNDS:REPAIR[:STAGNATION_MS[:PERTURB_STEP[:FOUR_EDGE_PERCENT]]]",
        help="explicit schedule such as 8:final:0:12:10",
    )
    parser.add_argument("--local-seconds", type=int, default=4)
    parser.add_argument("--repair-seconds", type=float, default=4.0)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=880)
    parser.add_argument("--sat-lane", action="append")
    parser.add_argument("--max-incumbents", type=int)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    arguments.rounds = arguments.rounds or [1, 2, 4]
    arguments.sat_lane = arguments.sat_lane or list(DEFAULT_LANES)
    if arguments.configuration:
        specifications = []
        for value in arguments.configuration:
            try:
                parts = value.split(":")
                if len(parts) < 2 or len(parts) > 5:
                    raise ValueError
                rounds_text, repair_schedule = parts[:2]
                rounds = int(rounds_text)
                stagnation_ms = int(parts[2]) if len(parts) >= 3 else 0
                perturb_step = int(parts[3]) if len(parts) >= 4 else 3
                four_edge_percent = int(parts[4]) if len(parts) >= 5 else 0
            except (TypeError, ValueError) as error:
                parser.error(
                    f"invalid --configuration {value!r}; expected "
                    "ROUNDS:REPAIR[:STAGNATION_MS[:PERTURB_STEP"
                    "[:FOUR_EDGE_PERCENT]]]"
                )
            if repair_schedule not in {"each", "final"}:
                parser.error("repair schedule must be 'each' or 'final'")
            if stagnation_ms < 0:
                parser.error("configuration stagnation milliseconds must be nonnegative")
            if perturb_step < 0:
                parser.error("configuration perturbation step must be nonnegative")
            if not 0 <= four_edge_percent <= 100:
                parser.error("configuration four-edge percentage must be between 0 and 100")
            specifications.append(
                (
                    rounds,
                    repair_schedule,
                    stagnation_ms,
                    perturb_step,
                    four_edge_percent,
                )
            )
    else:
        specifications = [(rounds, "each", 0, 3, 0) for rounds in arguments.rounds]

    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if min(arguments.local_seconds, arguments.threads) < 1:
        parser.error("--local-seconds and --threads must be positive")
    if arguments.repair_seconds <= 0:
        parser.error("--repair-seconds must be positive")
    if len(set(arguments.rounds)) != len(arguments.rounds) or min(arguments.rounds) < 1:
        parser.error("--rounds values must be unique and positive")
    if len(set(specifications)) != len(specifications):
        parser.error("--configuration values must be unique")
    if min(specification[0] for specification in specifications) < 1:
        parser.error("configuration rounds must be positive")
    if max(specification[0] for specification in specifications) > arguments.local_seconds:
        parser.error("each schedule needs at least one local-search second per round")
    if len(set(arguments.sat_lane)) != len(arguments.sat_lane):
        parser.error("--sat-lane values must be unique")
    if arguments.max_incumbents is not None and arguments.max_incumbents < 1:
        parser.error("--max-incumbents must be positive")
    arguments.rounds = list(
        dict.fromkeys(
            specification[0] for specification in specifications
        )
    )
    arguments.specifications = specifications
    return arguments


def load_incumbents(arguments, parser_root):
    data = json.loads(arguments.factor_benchmark.read_text(encoding="utf-8"))
    if data.get("n") != arguments.n:
        raise ValueError("factor benchmark grid size does not match n")
    incumbents = [
        {
            "code": run["bestCode"],
            "energy": run["bestEnergy"],
            "sourceSeed": run.get("seed"),
        }
        for run in data.get("runResults", [])
        if run.get("bestCode")
    ]
    if arguments.max_incumbents is not None:
        incumbents = incumbents[: arguments.max_incumbents]
    if not incumbents:
        raise ValueError(f"no incumbents in {parser_root}")
    return incumbents


def validate_code(project_root, code, energy):
    completed = subprocess.run(
        ["node", "research/validate-rot4-code.js", code],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    validation = json.loads(completed.stdout or completed.stderr)
    research = validation.get("research", {})
    application = validation.get("application", {})
    if not research.get("rotated") or not research.get("rowPerfectFactor"):
        raise RuntimeError(f"invalid rot4 factor: {validation}")
    if research.get("triples") != energy:
        raise RuntimeError(
            f"reported energy {energy} recomputed as {research.get('triples')}"
        )
    if research.get("violatingLines") != application.get("violatingLines"):
        raise RuntimeError(f"validator disagreement: {validation}")
    if (energy == 0) != bool(validation.get("valid")):
        raise RuntimeError(f"unexpected validator status: {validation}")
    return validation


def strategy_name(
    rounds,
    repair_schedule,
    stagnation_ms=0,
    perturb_step=3,
    four_edge_percent=0,
):
    suffix = "" if repair_schedule == "each" else f"-repair-{repair_schedule}"
    if stagnation_ms:
        suffix += f"-stagnation-{stagnation_ms}ms"
    if perturb_step != 3:
        suffix += f"-perturb-{perturb_step}"
    if four_edge_percent:
        suffix += f"-four-{four_edge_percent}pct"
    return f"rounds-{rounds}{suffix}"


def run_schedule(
    arguments,
    project_root,
    incumbent,
    instance,
    rounds,
    repair_schedule,
    stagnation_ms,
    perturb_step,
    four_edge_percent,
):
    seed = arguments.seed + instance
    command = [
        sys.executable,
        "research/run-hybrid-search.py",
        str(arguments.executable.resolve()),
        str(arguments.n),
        "--initial-incumbent",
        incumbent["code"],
        "--local-seconds",
        str(arguments.local_seconds),
        "--repair-seconds",
        str(arguments.repair_seconds),
        "--rounds",
        str(rounds),
        "--repair-schedule",
        repair_schedule,
        "--threads",
        str(arguments.threads),
        "--seed",
        str(seed),
        "--repair-backend",
        "portfolio",
    ]
    if stagnation_ms:
        command.extend(["--local-stagnation-ms", str(stagnation_ms)])
    if perturb_step != 3:
        command.extend(["--local-perturb-step", str(perturb_step)])
    if four_edge_percent:
        command.extend(
            ["--local-four-edge-percent", str(four_edge_percent)]
        )
    for lane in arguments.sat_lane:
        command.extend(["--sat-lane", lane])

    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    wall_seconds = time.monotonic() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"hybrid schedule failed with exit {completed.returncode}:\n"
            f"{completed.stderr}\n{completed.stdout}"
        )
    result = json.loads(completed.stdout)
    validation = validate_code(
        project_root, result["finalCode"], result["finalEnergy"]
    )

    previous_energy = incumbent["energy"]
    local_gains = []
    repair_gains = []
    for round_result in result["roundResults"]:
        local_energy = round_result["repairInputEnergy"]
        ending_energy = round_result["endingEnergy"]
        local_gains.append(previous_energy - local_energy)
        repair_gains.append(local_energy - ending_energy)
        previous_energy = ending_energy
    return {
        "rounds": rounds,
        "repairSchedule": repair_schedule,
        "stagnationMs": stagnation_ms,
        "perturbStep": perturb_step,
        "fourEdgePercent": four_edge_percent,
        "seed": seed,
        "wallSeconds": round(wall_seconds, 6),
        "initialEnergy": incumbent["energy"],
        "finalEnergy": result["finalEnergy"],
        "improvement": incumbent["energy"] - result["finalEnergy"],
        "localGains": local_gains,
        "repairGains": repair_gains,
        "validation": validation,
        "result": result,
    }


def summarize(strategy, instances):
    runs = [instance["results"][strategy] for instance in instances]
    energies = [run["finalEnergy"] for run in runs]
    improvements = [run["improvement"] for run in runs]
    completed_rounds = [len(run["result"]["roundResults"]) for run in runs]
    maximum_rounds = max(completed_rounds)
    round_ending_energies = []
    for round_index in range(maximum_rounds):
        values = []
        for run in runs:
            results = run["result"]["roundResults"]
            values.append(results[min(round_index, len(results) - 1)]["endingEnergy"])
        round_ending_energies.append(
            {
                "round": round_index + 1,
                "energies": values,
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
            }
        )
    return {
        "energies": energies,
        "improvements": improvements,
        "meanEnergy": statistics.fmean(energies),
        "medianEnergy": statistics.median(energies),
        "minimumEnergy": min(energies),
        "meanImprovement": statistics.fmean(improvements),
        "medianImprovement": statistics.median(improvements),
        "meanWallSeconds": statistics.fmean(run["wallSeconds"] for run in runs),
        "localImprovingRounds": sum(
            gain > 0 for run in runs for gain in run["localGains"]
        ),
        "repairImprovingRounds": sum(
            gain > 0 for run in runs for gain in run["repairGains"]
        ),
        "roundEndingEnergy": round_ending_energies,
    }


def main():
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parent.parent
    incumbents = load_incumbents(arguments, arguments.factor_benchmark)
    strategies = [
        strategy_name(*specification)
        for specification in arguments.specifications
    ]
    instances = []

    for instance, incumbent in enumerate(incumbents):
        validate_code(project_root, incumbent["code"], incumbent["energy"])
        order_offset = instance % len(arguments.specifications)
        schedule_order = (
            arguments.specifications[order_offset:]
            + arguments.specifications[:order_offset]
        )
        results = {}
        for (
            rounds,
            repair_schedule,
            stagnation_ms,
            perturb_step,
            four_edge_percent,
        ) in schedule_order:
            print(
                f"instance {instance + 1}/{len(incumbents)}, "
                f"rounds={rounds}, repair={repair_schedule}, "
                f"stagnation_ms={stagnation_ms}, perturb_step={perturb_step}, "
                f"four_edge_percent={four_edge_percent}",
                file=sys.stderr,
                flush=True,
            )
            results[
                strategy_name(
                    rounds,
                    repair_schedule,
                    stagnation_ms,
                    perturb_step,
                    four_edge_percent,
                )
            ] = run_schedule(
                arguments,
                project_root,
                incumbent,
                instance,
                rounds,
                repair_schedule,
                stagnation_ms,
                perturb_step,
                four_edge_percent,
            )
        best_energy = min(run["finalEnergy"] for run in results.values())
        instances.append(
            {
                "index": instance,
                "incumbent": incumbent,
                "bestEnergy": best_energy,
                "winners": [
                    strategy
                    for strategy, run in results.items()
                    if run["finalEnergy"] == best_energy
                ],
                "results": results,
            }
        )

    summary = {
        strategy: summarize(strategy, instances) for strategy in strategies
    }
    baseline = "rounds-1" if "rounds-1" in summary else strategies[0]
    for strategy in strategies:
        deltas = [
            instance["results"][strategy]["finalEnergy"]
            - instance["results"][baseline]["finalEnergy"]
            for instance in instances
        ]
        summary[strategy]["energyDeltaFromBaseline"] = deltas
        summary[strategy]["meanEnergyDeltaFromBaseline"] = statistics.fmean(deltas)
        summary[strategy]["winsAgainstBaseline"] = sum(delta < 0 for delta in deltas)
        summary[strategy]["lossesAgainstBaseline"] = sum(delta > 0 for delta in deltas)

    ranked = sorted(strategies, key=lambda strategy: summary[strategy]["meanEnergy"])
    report = {
        "date": datetime.date.today().isoformat(),
        "benchmark": "iterated rot4 local-search and exact-repair feedback",
        "n": arguments.n,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "sourceFactorBenchmark": str(arguments.factor_benchmark),
        "parameters": {
            "totalLocalSeconds": arguments.local_seconds,
            "totalRepairSeconds": arguments.repair_seconds,
            "threads": arguments.threads,
            "rounds": arguments.rounds,
            "configurations": [
                {
                    "rounds": rounds,
                    "repairSchedule": repair_schedule,
                    "stagnationMs": stagnation_ms,
                    "perturbStep": perturb_step,
                    "fourEdgePercent": four_edge_percent,
                }
                for (
                    rounds,
                    repair_schedule,
                    stagnation_ms,
                    perturb_step,
                    four_edge_percent,
                ) in arguments.specifications
            ],
            "satLanes": arguments.sat_lane,
            "includesZ3": True,
            "seedStart": arguments.seed,
        },
        "strategies": strategies,
        "baseline": baseline,
        "rankedStrategies": ranked,
        "summary": summary,
        "instanceResults": instances,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
