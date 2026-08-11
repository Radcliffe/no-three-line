#!/usr/bin/env python3
"""Compare halo sizes and core-expansion widths for SAT repair neighborhoods."""

import argparse
import importlib.util
import json
import platform
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace


INITIAL_POLICIES = ("greedy", "greedy-conflict", "greedy-random", "minimum")


def load_policy_benchmark():
    filename = Path(__file__).with_name("benchmark-neighborhood-policies.py")
    spec = importlib.util.spec_from_file_location("neighborhood_policies", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int)
    parser.add_argument("--incumbent", action="append", default=[])
    parser.add_argument("--portfolio", type=Path)
    parser.add_argument("--factor-benchmark", type=Path)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=580)
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument(
        "--initial-policy",
        action="append",
        choices=INITIAL_POLICIES,
    )
    parser.add_argument("--core-policy", default="score", choices=("score", "marginal", "random"))
    parser.add_argument("--halo", action="append", type=int)
    parser.add_argument("--expand", action="append", type=int)
    parser.add_argument(
        "--configuration",
        action="append",
        metavar="HALO:EXPAND",
        help="explicit size pair; repeat to avoid the full halo/expand Cartesian product",
    )
    parser.add_argument("--core-vertices", type=int, default=6)
    parser.add_argument("--free-fraction", type=float, default=0.15)
    parser.add_argument("--max-incumbents", type=int)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    arguments.initial_policy = arguments.initial_policy or [
        "greedy-random",
        "minimum",
    ]
    arguments.halo = arguments.halo or [0, 2, 4]
    arguments.expand = arguments.expand or [1, 2, 4]
    if arguments.configuration:
        configurations = []
        for value in arguments.configuration:
            try:
                halo, expand = (int(part) for part in value.split(":", 1))
            except (TypeError, ValueError) as error:
                parser.error(f"invalid --configuration {value!r}; expected HALO:EXPAND")
            configurations.append((halo, expand))
    else:
        configurations = [
            (halo, expand) for halo in arguments.halo for expand in arguments.expand
        ]

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
    if arguments.max_incumbents is not None:
        if arguments.max_incumbents < 1:
            parser.error("--max-incumbents must be positive")
        arguments.incumbent = arguments.incumbent[: arguments.max_incumbents]
    if not arguments.incumbent:
        parser.error("provide an incumbent source")
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if arguments.seconds <= 0:
        parser.error("--seconds must be positive")
    if len(set(arguments.initial_policy)) != len(arguments.initial_policy):
        parser.error("--initial-policy values must be unique")
    if len(set(arguments.halo)) != len(arguments.halo) or min(arguments.halo) < 0:
        parser.error("--halo values must be unique and nonnegative")
    if len(set(arguments.expand)) != len(arguments.expand) or min(arguments.expand) < 1:
        parser.error("--expand values must be unique and positive")
    if len(set(configurations)) != len(configurations):
        parser.error("--configuration values must be unique")
    if any(halo < 0 or expand < 1 for halo, expand in configurations):
        parser.error("configuration halo must be nonnegative and expansion positive")
    arguments.configurations = configurations
    return arguments


def name(initial_policy, core_policy, halo, expand):
    return f"{initial_policy}+{core_policy}-h{halo}-x{expand}"


def summarize(variants, instances):
    output = {}
    for variant in variants:
        runs = [instance["results"][variant] for instance in instances]
        energies = [run["energy"] for run in runs]
        improvements = [run["improvement"] for run in runs]
        output[variant] = {
            "energies": energies,
            "improvements": improvements,
            "meanEnergy": statistics.fmean(energies),
            "medianEnergy": statistics.median(energies),
            "meanImprovement": statistics.fmean(improvements),
            "medianImprovement": statistics.median(improvements),
            "meanWallSeconds": statistics.fmean(
                run["wallSeconds"] for run in runs
            ),
            "totalCandidates": sum(run["candidates"] for run in runs),
            "totalExpansions": sum(len(run["expansions"]) for run in runs),
            "meanInitialFreeVertices": statistics.fmean(
                run["initialFreeVertices"] for run in runs
            ),
            "meanFinalFreeVertices": statistics.fmean(
                run["finalFreeVertices"] for run in runs
            ),
        }
    return output


def portfolio_summary(instances, variants):
    energies = [
        min(instance["results"][variant]["energy"] for variant in variants)
        for instance in instances
    ]
    improvements = [
        instance["initialEnergy"] - energy
        for instance, energy in zip(instances, energies)
    ]
    return {
        "energies": energies,
        "meanEnergy": statistics.fmean(energies),
        "meanImprovement": statistics.fmean(improvements),
    }


def main():
    arguments = parse_arguments()
    policies = load_policy_benchmark()
    project_root = Path(__file__).resolve().parent.parent
    specifications = [
        (initial_policy, halo, expand)
        for initial_policy in arguments.initial_policy
        for halo, expand in arguments.configurations
    ]
    variants = [
        name(initial, arguments.core_policy, halo, expand)
        for initial, halo, expand in specifications
    ]
    wins = {variant: 0 for variant in variants}
    wins["ties"] = 0
    instances = []
    for index, incumbent in enumerate(arguments.incumbent):
        offset = index % len(specifications)
        order = specifications[offset:] + specifications[:offset]
        results = {}
        for initial_policy, halo, expand in order:
            run_arguments = SimpleNamespace(
                n=arguments.n,
                seconds=arguments.seconds,
                seed=arguments.seed,
                solver=arguments.solver,
                core_vertices=arguments.core_vertices,
                halo_vertices=halo,
                free_fraction=arguments.free_fraction,
                expand_by=expand,
                sbva=None,
            )
            run = policies.run_variant(
                run_arguments,
                project_root,
                incumbent,
                index,
                initial_policy,
                arguments.core_policy,
            )
            variant = name(initial_policy, arguments.core_policy, halo, expand)
            run.update(variant=variant, haloVertices=halo, expandBy=expand)
            results[variant] = run
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
                "index": index,
                "incumbent": incumbent,
                "initialEnergy": next(iter(results.values()))["initialEnergy"],
                "bestEnergy": minimum,
                "winners": winners,
                "results": results,
            }
        )

    summary = summarize(variants, instances)
    ranked = sorted(variants, key=lambda variant: summary[variant]["meanEnergy"])
    report = {
        "date": "2026-08-07",
        "benchmark": "rot4 SAT repair neighborhood sizes",
        "n": arguments.n,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "solver": arguments.solver,
        },
        "secondsPerVariant": arguments.seconds,
        "seedStart": arguments.seed,
        "rngStreams": "split-cover-halo-core-cut",
        "parameters": {
            "initialPolicies": arguments.initial_policy,
            "corePolicy": arguments.core_policy,
            "haloVertices": arguments.halo,
            "expandBy": arguments.expand,
            "configurations": [
                {"haloVertices": halo, "expandBy": expand}
                for halo, expand in arguments.configurations
            ],
            "coreVertices": arguments.core_vertices,
            "freeFraction": arguments.free_fraction,
        },
        "variants": variants,
        "rankedVariants": ranked,
        "winsByFinalEnergy": wins,
        "summary": summary,
        "portfolio": portfolio_summary(instances, variants),
        "instanceResults": instances,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
