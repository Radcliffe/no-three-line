#!/usr/bin/env python3
"""Compare matched SAT repair-neighborhood policies on rot4 incumbents."""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_INITIAL = ("greedy", "greedy-conflict", "greedy-random", "minimum")
DEFAULT_CORE = ("score", "marginal", "random")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int)
    parser.add_argument("--incumbent", action="append", default=[])
    parser.add_argument(
        "--portfolio",
        type=Path,
        help="load incumbentGeneration.runs from a recorded portfolio",
    )
    parser.add_argument(
        "--factor-benchmark",
        type=Path,
        help="load runResults bestCode values from a local-search benchmark",
    )
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=380)
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument("--initial-policy", action="append")
    parser.add_argument("--core-policy", action="append")
    parser.add_argument("--core-vertices", type=int, default=6)
    parser.add_argument("--halo-vertices", type=int, default=2)
    parser.add_argument("--free-fraction", type=float, default=0.15)
    parser.add_argument("--expand-by", type=int, default=2)
    parser.add_argument("--sbva", nargs="?", const="sbva")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    arguments.initial_policy = arguments.initial_policy or list(DEFAULT_INITIAL)
    arguments.core_policy = arguments.core_policy or list(DEFAULT_CORE)
    if arguments.portfolio:
        data = json.loads(arguments.portfolio.read_text(encoding="utf-8"))
        if data.get("n") != arguments.n:
            parser.error("--portfolio grid size does not match n")
        arguments.incumbent.extend(
            run["code"] for run in data["incumbentGeneration"]["runs"]
        )
    if arguments.factor_benchmark:
        data = json.loads(arguments.factor_benchmark.read_text(encoding="utf-8"))
        if data.get("n") != arguments.n:
            parser.error("--factor-benchmark grid size does not match n")
        arguments.incumbent.extend(
            run["bestCode"]
            for run in data.get("runResults", [])
            if run.get("bestCode")
        )
    if not arguments.incumbent:
        parser.error("provide an incumbent source")
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if arguments.seconds <= 0:
        parser.error("--seconds must be positive")
    if len(set(arguments.initial_policy)) != len(arguments.initial_policy):
        parser.error("--initial-policy values must be unique")
    if len(set(arguments.core_policy)) != len(arguments.core_policy):
        parser.error("--core-policy values must be unique")
    invalid_initial = set(arguments.initial_policy) - set(DEFAULT_INITIAL)
    invalid_core = set(arguments.core_policy) - set(DEFAULT_CORE)
    if invalid_initial or invalid_core:
        parser.error(
            f"unknown policies: {sorted(invalid_initial | invalid_core)}"
        )
    return arguments


def variant_name(initial_policy, core_policy):
    return f"{initial_policy}+{core_policy}"


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
        raise RuntimeError(
            f"validator disagreed with repair energy {expected_energy}: {result}"
        )
    return {
        "triples": research.get("triples"),
        "violatingLines": research.get("violatingLines"),
        "applicationViolatingLines": application.get("violatingLines"),
        "rot4": research.get("rotated"),
        "rowPerfectFactor": research.get("rowPerfectFactor"),
    }


def run_variant(
    arguments,
    project_root,
    incumbent,
    instance,
    initial_policy,
    core_policy,
):
    command = [
        sys.executable,
        "research/rot4-sat-repair.py",
        str(arguments.n),
        "--incumbent",
        incumbent,
        "--seconds",
        str(arguments.seconds),
        "--seed",
        str(arguments.seed + instance),
        "--solver",
        arguments.solver,
        "--core-vertices",
        str(arguments.core_vertices),
        "--halo-vertices",
        str(arguments.halo_vertices),
        "--free-fraction",
        str(arguments.free_fraction),
        "--expand-by",
        str(arguments.expand_by),
        "--initial-cover-policy",
        initial_policy,
        "--core-expansion-policy",
        core_policy,
        "--split-rng-streams",
    ]
    if arguments.sbva:
        command.extend(["--sbva", arguments.sbva])
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
            f"{variant_name(initial_policy, core_policy)} failed with "
            f"exit {completed.returncode}:\n{completed.stderr}"
        )
    result = json.loads(completed.stdout)
    energy = 0 if result["status"] == "sat" else result["best_triples"]
    code = result.get("code") if energy == 0 else result["best_code"]
    validation = validate(project_root, code, energy)
    expansions = result.get("expansions", [])
    covered = sum(item.get("coveredArcAssumptions", 0) for item in expansions)
    core_arcs = sum(item.get("arcAssumptions", 0) for item in expansions)
    return {
        "variant": variant_name(initial_policy, core_policy),
        "initialPolicy": initial_policy,
        "corePolicy": core_policy,
        "seed": arguments.seed + instance,
        "status": result["status"],
        "initialEnergy": result["initial_triples"],
        "energy": energy,
        "improvement": result["initial_triples"] - energy,
        "wallSeconds": wall_seconds,
        "calls": result.get("calls", 0),
        "candidates": result.get("candidates", 0),
        "cuts": result.get("cuts", 0),
        "initialFreeVertices": result.get("initial_free_vertices"),
        "initialNeighborhood": result.get("initial_neighborhood"),
        "finalFreeVertices": result.get("free_vertices"),
        "expansions": expansions,
        "coveredCoreArcAssumptions": covered,
        "coreArcAssumptions": core_arcs,
        "coreCoverageFraction": covered / core_arcs if core_arcs else None,
        "statistics": result.get("statistics"),
        "bestCode": code,
        "validation": validation,
    }


def summarize(variants, instances):
    summaries = {}
    for variant in variants:
        runs = [
            instance["results"][variant]
            for instance in instances
            if variant in instance["results"]
        ]
        energies = [run["energy"] for run in runs]
        improvements = [run["improvement"] for run in runs]
        wall = [run["wallSeconds"] for run in runs]
        coverage_numerators = [
            run["coveredCoreArcAssumptions"] for run in runs
        ]
        coverage_denominators = [run["coreArcAssumptions"] for run in runs]
        summaries[variant] = {
            "solved": sum(energy == 0 for energy in energies),
            "energies": energies,
            "improvements": improvements,
            "meanEnergy": statistics.fmean(energies),
            "medianEnergy": statistics.median(energies),
            "meanImprovement": statistics.fmean(improvements),
            "medianImprovement": statistics.median(improvements),
            "meanWallSeconds": statistics.fmean(wall),
            "medianWallSeconds": statistics.median(wall),
            "totalCandidates": sum(run["candidates"] for run in runs),
            "totalExpansions": sum(len(run["expansions"]) for run in runs),
            "coreCoverageFraction": (
                sum(coverage_numerators) / sum(coverage_denominators)
                if sum(coverage_denominators)
                else None
            ),
        }
    return summaries


def main():
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parent.parent
    variants = [
        variant_name(initial, core)
        for initial in arguments.initial_policy
        for core in arguments.core_policy
    ]
    instances = []
    wins = {variant: 0 for variant in variants}
    wins["ties"] = 0
    for instance, incumbent in enumerate(arguments.incumbent):
        specifications = [
            (initial, core)
            for initial in arguments.initial_policy
            for core in arguments.core_policy
        ]
        offset = instance % len(specifications)
        specifications = specifications[offset:] + specifications[:offset]
        results = {}
        for initial_policy, core_policy in specifications:
            run = run_variant(
                arguments,
                project_root,
                incumbent,
                instance,
                initial_policy,
                core_policy,
            )
            results[run["variant"]] = run
        minimum = min(run["energy"] for run in results.values())
        winners = [
            variant for variant, run in results.items() if run["energy"] == minimum
        ]
        if len(winners) == 1:
            wins[winners[0]] += 1
        else:
            wins["ties"] += 1
        instances.append(
            {
                "index": instance,
                "incumbent": incumbent,
                "initialEnergy": next(iter(results.values()))["initialEnergy"],
                "bestEnergy": minimum,
                "winners": winners,
                "results": results,
            }
        )

    report = {
        "date": "2026-08-07",
        "benchmark": "rot4 SAT repair neighborhood policies",
        "n": arguments.n,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "solver": arguments.solver,
            "sbva": arguments.sbva,
        },
        "secondsPerVariant": arguments.seconds,
        "seedStart": arguments.seed,
        "rngStreams": "split-cover-halo-core-cut",
        "parameters": {
            "coreVertices": arguments.core_vertices,
            "haloVertices": arguments.halo_vertices,
            "freeFraction": arguments.free_fraction,
            "expandBy": arguments.expand_by,
        },
        "variants": variants,
        "winsByFinalEnergy": wins,
        "summary": summarize(variants, instances),
        "instanceResults": instances,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
