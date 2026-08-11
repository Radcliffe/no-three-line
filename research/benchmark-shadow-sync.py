#!/usr/bin/env python3
"""Measure CaDiCaL shadow synchronization on recorded n=76 near-misses."""

import argparse
import hashlib
import importlib.util
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


MODES = ("baseline", "eager", "candidate", "deferred")
SHADOW_MODES = MODES[1:]


def load_backend():
    filename = Path(__file__).with_name("rot4-sat-repair.py")
    spec = importlib.util.spec_from_file_location("rot4_sat_repair", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, help="in-process CaDiCaL bridge")
    parser.add_argument(
        "--portfolio",
        type=Path,
        default=Path("research/benchmarks/sat-portfolio-2026-08-07.json"),
        help="recorded incumbent portfolio",
    )
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument(
        "--repair-seconds",
        type=float,
        default=0.0,
        help="also run each synchronization mode on every incumbent for this many seconds",
    )
    parser.add_argument("--repair-seed", type=int, default=280)
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.repetitions < 1:
        parser.error("--repetitions must be positive")
    if arguments.repair_seconds < 0:
        parser.error("--repair-seconds cannot be negative")
    return arguments


def formula_digest(clauses):
    digest = hashlib.sha256()
    for clause in clauses:
        digest.update(" ".join(map(str, clause)).encode("ascii"))
        digest.update(b" 0\n")
    return digest.hexdigest()


def difference(after, before, field):
    return after.get(field, 0) - before.get(field, 0)


def synchronize_cut_stream(backend, arguments, n, batches, mode):
    shadow_mode = "deferred" if mode == "baseline" else mode
    engine = backend.FactorSat(
        n,
        "cadical195",
        6,
        retain_formula=True,
        shadow_sync=shadow_mode,
    )
    try:
        initial_formula_clauses = len(engine.formula_clauses)
        if mode != "baseline":
            engine.enable_cadical_shadow(arguments.library)
            shadow_before = engine.cadical_shadow.statistics()
        else:
            shadow_before = {}

        started = time.monotonic()
        for batch in batches:
            engine.add_line_cuts(batch)
        if mode != "baseline":
            engine.flush_cadical_shadow()
        seconds = time.monotonic() - started

        shadow_after = (
            engine.cadical_shadow.statistics() if mode != "baseline" else {}
        )
        if mode != "baseline" and engine.shadow_synced_clauses != len(
            engine.formula_clauses
        ):
            raise AssertionError(f"{mode} did not synchronize the complete retained CNF")
        return {
            "mode": mode,
            "cadicalVersion": (
                engine.cadical_shadow.version if mode != "baseline" else None
            ),
            "seconds": seconds,
            "cuts": len(engine.cuts),
            "addedClauses": len(engine.formula_clauses) - initial_formula_clauses,
            "formulaClauses": len(engine.formula_clauses),
            "formulaSha256": formula_digest(engine.formula_clauses),
            "shadowAddCalls": difference(shadow_after, shadow_before, "addCalls"),
            "shadowClauses": difference(shadow_after, shadow_before, "clauses"),
            "shadowLiterals": difference(shadow_after, shadow_before, "literals"),
            "shadowPackSeconds": difference(
                shadow_after, shadow_before, "packSeconds"
            ),
            "shadowBridgeSeconds": difference(
                shadow_after, shadow_before, "bridgeSeconds"
            ),
            "shadowAddSeconds": difference(
                shadow_after, shadow_before, "addSeconds"
            ),
        }
    finally:
        engine.close()


def summarize_stream_runs(runs):
    summary = {}
    for mode in MODES:
        selected = [run for run in runs if run["mode"] == mode]
        summary[mode] = {
            "medianSeconds": statistics.median(run["seconds"] for run in selected),
            "meanSeconds": statistics.mean(run["seconds"] for run in selected),
            "medianShadowAddCalls": statistics.median(
                run["shadowAddCalls"] for run in selected
            ),
            "medianShadowAddSeconds": statistics.median(
                run["shadowAddSeconds"] for run in selected
            ),
            "cuts": selected[0]["cuts"],
            "addedClauses": selected[0]["addedClauses"],
            "formulaSha256": selected[0]["formulaSha256"],
        }
    fingerprints = {data["formulaSha256"] for data in summary.values()}
    if len(fingerprints) != 1:
        raise AssertionError("synchronization mode changed the encoded formula")
    eager = summary["eager"]
    deferred = summary["deferred"]
    summary["comparison"] = {
        "eagerToDeferredCallReduction": (
            eager["medianShadowAddCalls"] / deferred["medianShadowAddCalls"]
        ),
        "eagerToDeferredShadowAddSpeedup": (
            eager["medianShadowAddSeconds"]
            / deferred["medianShadowAddSeconds"]
        ),
        "eagerToDeferredTotalUpdateSpeedup": (
            eager["medianSeconds"] / deferred["medianSeconds"]
        ),
    }
    return summary


def run_repairs(backend, arguments, project_root, n, incumbents):
    runs = []
    script = Path(__file__).with_name("rot4-sat-repair.py")
    for index, incumbent in enumerate(incumbents):
        order = SHADOW_MODES[index % len(SHADOW_MODES) :] + SHADOW_MODES[
            : index % len(SHADOW_MODES)
        ]
        for mode in order:
            with tempfile.TemporaryDirectory(prefix="rot4-shadow-benchmark-") as temporary:
                command = [
                    sys.executable,
                    str(script),
                    str(n),
                    "--incumbent",
                    incumbent["code"],
                    "--seconds",
                    str(arguments.repair_seconds),
                    "--seed",
                    str(arguments.repair_seed + index),
                    "--solver",
                    arguments.solver,
                    "--expand-by",
                    "0",
                    "--proof-dir",
                    str(Path(temporary) / "proof"),
                    "--proof-cadical-library",
                    arguments.library,
                    "--proof-shadow-sync",
                    mode,
                ]
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
                    f"{mode} repair failed with exit {completed.returncode}:\n"
                    f"{completed.stderr}"
                )
            result = json.loads(completed.stdout)
            energy = 0 if result["status"] == "sat" else result["best_triples"]
            code = result.get("code") if energy == 0 else result["best_code"]
            arcs = backend.arcs_from_code(code, n)
            _details, checked_energy = backend.selected_line_data(n, arcs)
            if checked_energy != energy:
                raise AssertionError(
                    f"{mode} repair reported energy {energy}, recomputed {checked_energy}"
                )
            shadow = result.get("statistics", {}).get("proofShadow", {})
            runs.append(
                {
                    "instance": index,
                    "mode": mode,
                    "seed": arguments.repair_seed + index,
                    "initialEnergy": incumbent["energy"],
                    "energy": energy,
                    "status": result["status"],
                    "candidates": result.get("candidates", 0),
                    "cuts": result.get("cuts", 0),
                    "wallSeconds": wall_seconds,
                    "shadow": shadow,
                }
            )
    return runs


def summarize_repairs(runs):
    summary = {}
    for mode in SHADOW_MODES:
        selected = [run for run in runs if run["mode"] == mode]
        summary[mode] = {
            "energies": [run["energy"] for run in selected],
            "candidateCounts": [run["candidates"] for run in selected],
            "cutCounts": [run["cuts"] for run in selected],
            "medianWallSeconds": statistics.median(
                run["wallSeconds"] for run in selected
            ),
            "meanWallSeconds": statistics.mean(
                run["wallSeconds"] for run in selected
            ),
            "medianShadowAddCalls": statistics.median(
                run["shadow"].get("addCalls", 0) for run in selected
            ),
            "medianPendingClauses": statistics.median(
                run["shadow"].get("pendingClauses", 0) for run in selected
            ),
        }
    trajectories = {}
    for run in runs:
        trajectory = (
            run["energy"],
            run["status"],
            run["candidates"],
            run["cuts"],
        )
        trajectories.setdefault(run["instance"], set()).add(trajectory)
    summary["comparison"] = {
        "allTrajectoriesMatched": all(
            len(instance_trajectories) == 1
            for instance_trajectories in trajectories.values()
        ),
        "eagerToDeferredMedianWallSpeedup": (
            summary["eager"]["medianWallSeconds"]
            / summary["deferred"]["medianWallSeconds"]
        ),
    }
    return summary


def main():
    arguments = parse_arguments()
    backend = load_backend()
    project_root = Path(__file__).resolve().parent.parent
    portfolio = json.loads(arguments.portfolio.read_text(encoding="utf-8"))
    n = portfolio["n"]
    incumbents = portfolio["incumbentGeneration"]["runs"]
    batches = []
    incumbent_data = []
    for incumbent in incumbents:
        arcs = backend.arcs_from_code(incumbent["code"], n)
        details, energy = backend.selected_line_data(n, arcs)
        if energy != incumbent["energy"]:
            raise AssertionError(
                f"recorded incumbent energy {incumbent['energy']} recomputed as {energy}"
            )
        batches.append([key for key, _arc_ids in details])
        incumbent_data.append(
            {
                "seed": incumbent["seed"],
                "energy": energy,
                "violatingLines": len(details),
                "code": incumbent["code"],
            }
        )

    stream_runs = []
    for repetition in range(arguments.repetitions):
        order = MODES[repetition % len(MODES) :] + MODES[: repetition % len(MODES)]
        for mode in order:
            run = synchronize_cut_stream(backend, arguments, n, batches, mode)
            run["repetition"] = repetition
            stream_runs.append(run)

    report = {
        "date": "2026-08-07",
        "benchmark": "CaDiCaL shadow synchronization on recorded rot4 near-misses",
        "n": n,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "satSolver": "cadical195",
            "cadicalVersion": next(
                run["cadicalVersion"]
                for run in stream_runs
                if run["cadicalVersion"] is not None
            ),
        },
        "library": str(Path(arguments.library).resolve()),
        "librarySha256": hashlib.sha256(
            Path(arguments.library).resolve().read_bytes()
        ).hexdigest(),
        "repetitions": arguments.repetitions,
        "incumbents": incumbent_data,
        "cutStream": {
            "candidateBatches": len(batches),
            "inputViolatingLines": sum(len(batch) for batch in batches),
            "runs": stream_runs,
            "summary": summarize_stream_runs(stream_runs),
        },
        "repair": None,
    }
    if arguments.repair_seconds:
        repair_runs = run_repairs(
            backend,
            arguments,
            project_root,
            n,
            incumbent_data,
        )
        report["repair"] = {
            "secondsPerRun": arguments.repair_seconds,
            "solver": arguments.solver,
            "expandBy": 0,
            "runs": repair_runs,
            "summary": summarize_repairs(repair_runs),
        }

    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
