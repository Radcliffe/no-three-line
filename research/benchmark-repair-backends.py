#!/usr/bin/env python3
"""Compare SAT solver/preprocessor variants and Z3 on identical incumbents."""

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int)
    parser.add_argument("--incumbent", action="append", default=[])
    parser.add_argument("--incumbents", type=Path, help="file containing one compact code per line")
    parser.add_argument(
        "--factor-benchmark",
        type=Path,
        help="load bestCode values from benchmark-factor-search.py JSON",
    )
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--sat-solver",
        action="append",
        help="SAT engine; repeat to compare several (default: cadical195)",
    )
    parser.add_argument("--sat-conflict-chunk", type=int, default=1_000)
    parser.add_argument("--sat-propagation-chunk", type=int, default=1_000_000)
    parser.add_argument(
        "--sbva",
        nargs="?",
        const="sbva",
        help="include an SBVA-preprocessed SAT run (PATH defaults to sbva in PATH)",
    )
    parser.add_argument("--skip-z3", action="store_true", help="benchmark SAT variants only")
    parser.add_argument("--core-vertices", type=int, default=6)
    parser.add_argument("--halo-vertices", type=int, default=2)
    parser.add_argument("--free-fraction", type=float, default=0.15)
    parser.add_argument("--expand-by", type=int, default=2)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    arguments.sat_solver = arguments.sat_solver or ["cadical195"]
    if arguments.incumbents:
        arguments.incumbent.extend(
            line.strip()
            for line in arguments.incumbents.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if arguments.factor_benchmark:
        factor_report = json.loads(arguments.factor_benchmark.read_text(encoding="utf-8"))
        if factor_report.get("n") != arguments.n:
            parser.error("--factor-benchmark grid size does not match n")
        arguments.incumbent.extend(
            run["bestCode"]
            for run in factor_report.get("runResults", [])
            if run.get("bestCode")
        )
    if not arguments.incumbent:
        parser.error("provide --incumbent CODE or --incumbents PATH")
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if arguments.seconds <= 0:
        parser.error("--seconds must be positive")
    if arguments.sat_conflict_chunk < 1 or arguments.sat_propagation_chunk < 1:
        parser.error("SAT budget chunks must be positive")
    if len(set(arguments.sat_solver)) != len(arguments.sat_solver):
        parser.error("--sat-solver values must be unique")
    return arguments


def backend_specs(arguments):
    qualify_solver = len(arguments.sat_solver) > 1
    specs = []
    for solver in arguments.sat_solver:
        base = f"sat-{solver}" if qualify_solver else "sat"
        specs.append({"name": base, "kind": "sat", "solver": solver, "sbva": False})
        if arguments.sbva:
            specs.append(
                {
                    "name": f"{base}-sbva",
                    "kind": "sat",
                    "solver": solver,
                    "sbva": True,
                }
            )
    if not arguments.skip_z3:
        specs.append({"name": "z3", "kind": "z3"})
    return specs


def command(arguments, spec, code, seed):
    script = (
        "research/rot4-sat-repair.py"
        if spec["kind"] == "sat"
        else "research/rot4-lazy-z3.py"
    )
    result = [
        sys.executable,
        script,
        str(arguments.n),
        "--seconds",
        str(arguments.seconds),
        "--seed",
        str(seed),
        "--incumbent",
        code,
        "--core-vertices",
        str(arguments.core_vertices),
        "--halo-vertices",
        str(arguments.halo_vertices),
        "--free-fraction",
        str(arguments.free_fraction),
        "--expand-by",
        str(arguments.expand_by),
    ]
    if spec["kind"] == "sat":
        result.extend(
            [
                "--solver",
                spec["solver"],
                "--conflict-chunk",
                str(arguments.sat_conflict_chunk),
                "--propagation-chunk",
                str(arguments.sat_propagation_chunk),
            ]
        )
    if spec.get("sbva"):
        result.extend(["--sbva", arguments.sbva])
    return result


def validate(project_root, code, expected_energy):
    completed = subprocess.run(
        ["node", "research/validate-rot4-code.js", code],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    result = json.loads(completed.stdout or completed.stderr)
    research = result.get("research", {})
    application = result.get("application", {})
    consistent = (
        completed.returncode in (0, 1)
        and research.get("triples") == expected_energy
        and research.get("rotated")
        and research.get("rowPerfectFactor")
        and research.get("violatingLines") == application.get("violatingLines")
    )
    if expected_energy == 0:
        consistent = consistent and result.get("valid")
    if not consistent:
        raise RuntimeError(f"validator disagreed with repair energy {expected_energy}: {result}")
    return result


def run_backend(arguments, spec, code, seed, project_root):
    started = time.monotonic()
    completed = subprocess.run(
        command(arguments, spec, code, seed),
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    wall_seconds = time.monotonic() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"{spec['name']} failed with exit {completed.returncode}:\n{completed.stderr}"
        )
    result = json.loads(completed.stdout)
    energy = 0 if result["status"] == "sat" else result["best_triples"]
    code = result.get("code") if energy == 0 else result.get("best_code")
    validation = validate(project_root, code, energy)
    return {
        "backend": spec["name"],
        "energy": energy,
        "wallSeconds": round(wall_seconds, 6),
        "validation": validation,
        "result": result,
    }


def backend_summary(name, results):
    energies = [result["energy"] for result in results]
    wall = [result["wallSeconds"] for result in results]
    return {
        "backend": name,
        "solved": sum(energy == 0 for energy in energies),
        "solvedFraction": sum(energy == 0 for energy in energies) / len(energies),
        "finalEnergy": {
            "minimum": min(energies),
            "median": statistics.median(energies),
            "mean": statistics.fmean(energies),
            "maximum": max(energies),
        },
        "wallSeconds": {
            "median": statistics.median(wall),
            "mean": statistics.fmean(wall),
        },
    }


def portfolio_summary(instances):
    energies = [instance["portfolioEnergy"] for instance in instances]
    wall = [instance["concurrentWallSeconds"] for instance in instances]
    return {
        "solved": sum(energy == 0 for energy in energies),
        "solvedFraction": sum(energy == 0 for energy in energies) / len(energies),
        "finalEnergy": {
            "minimum": min(energies),
            "median": statistics.median(energies),
            "mean": statistics.fmean(energies),
            "maximum": max(energies),
        },
        "concurrentWallSeconds": {
            "median": statistics.median(wall),
            "mean": statistics.fmean(wall),
        },
    }


def main():
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parent.parent
    specs = backend_specs(arguments)
    backends = [spec["name"] for spec in specs]
    instances = []
    grouped = {backend: [] for backend in backends}
    wins = {backend: 0 for backend in backends}
    wins["ties"] = 0
    for index, code in enumerate(arguments.incumbent):
        seed = arguments.seed + index
        results = {
            spec["name"]: run_backend(arguments, spec, code, seed, project_root)
            for spec in specs
        }
        for backend in grouped:
            grouped[backend].append(results[backend])
        minimum = min(result["energy"] for result in results.values())
        winners = [
            backend for backend, result in results.items() if result["energy"] == minimum
        ]
        if len(winners) == 1:
            wins[winners[0]] += 1
        else:
            wins["ties"] += 1
        instances.append(
            {
                "index": index,
                "seed": seed,
                "incumbent": code,
                "portfolioEnergy": minimum,
                "concurrentWallSeconds": max(
                    result["wallSeconds"] for result in results.values()
                ),
                "winners": winners,
                "results": results,
            }
        )

    output = {
        "n": arguments.n,
        "secondsPerBackend": arguments.seconds,
        "instances": len(instances),
        "backends": specs,
        "winsByFinalEnergy": wins,
        "summary": {
            backend: backend_summary(backend, results) for backend, results in grouped.items()
        },
        "portfolioSummary": portfolio_summary(instances),
        "instanceResults": instances,
    }
    rendered = json.dumps(output, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
