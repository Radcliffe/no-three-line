#!/usr/bin/env python3
"""Compare CaDiCaL proof production with and without bounded variable addition."""

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

from pysat.examples.genhard import PHP


sys.dont_write_bytecode = True


def load_backend():
    filename = Path(__file__).with_name("rot4-sat-repair.py")
    spec = importlib.util.spec_from_file_location("rot4_sat_repair", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cadical", default="cadical")
    parser.add_argument("--library", help="optional in-process CaDiCaL bridge")
    parser.add_argument("--checker", default="drat-trim")
    parser.add_argument("--holes", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seconds", type=float, default=60.0)
    arguments = parser.parse_args()
    if arguments.holes < 2 or arguments.repetitions < 1 or arguments.seconds <= 0:
        parser.error("holes >= 2, repetitions >= 1, and seconds > 0 are required")

    backend = load_backend()
    formula = PHP(nof_holes=arguments.holes)
    variants = []
    library_variant = None
    with tempfile.TemporaryDirectory(prefix="cadical-proof-benchmark-") as temporary:
        temporary = Path(temporary)
        cnf_path = temporary / "pigeonhole.cnf"
        formula.to_file(cnf_path)
        for factor in (False, True):
            runs = []
            for repetition in range(arguments.repetitions):
                proof_path = temporary / f"factor-{int(factor)}-{repetition}.drat"
                result = backend.run_cadical_proof(
                    arguments.cadical,
                    cnf_path,
                    proof_path,
                    arguments.seconds,
                    factor=factor,
                )
                if result["status"] != "unsat":
                    raise RuntimeError(result)
                checked = backend.run_drat_checker(
                    arguments.checker,
                    cnf_path,
                    proof_path,
                    arguments.seconds,
                )
                if checked["status"] != "verified":
                    raise RuntimeError(checked)
                runs.append(
                    {
                        "seconds": result["seconds"],
                        "proofBytes": result["proofBytes"],
                        "proofSha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
                        "verified": True,
                    }
                )
            variants.append(
                {
                    "factor": factor,
                    "meanSeconds": round(
                        statistics.fmean(run["seconds"] for run in runs), 6
                    ),
                    "medianProofBytes": int(
                        statistics.median(run["proofBytes"] for run in runs)
                    ),
                    "runs": runs,
                }
            )

        if arguments.library:
            runs = []
            for repetition in range(arguments.repetitions):
                proof_path = temporary / f"library-{repetition}.drat"
                started = time.monotonic()
                shadow = backend.CadicalShadow(
                    arguments.library,
                    proof_path,
                    factor=True,
                )
                try:
                    shadow.add_clauses(formula.clauses)
                    setup_seconds = time.monotonic() - started
                    result = shadow.solve(arguments.seconds)
                finally:
                    shadow.close()
                if result["status"] != "unsat":
                    raise RuntimeError(result)
                checked = backend.run_drat_checker(
                    arguments.checker,
                    cnf_path,
                    proof_path,
                    arguments.seconds,
                )
                if checked["status"] != "verified":
                    raise RuntimeError(checked)
                runs.append(
                    {
                        "setupSeconds": round(setup_seconds, 6),
                        "solveSeconds": result["seconds"],
                        "proofBytes": result["proofBytes"],
                        "proofSha256": hashlib.sha256(
                            proof_path.read_bytes()
                        ).hexdigest(),
                        "verified": True,
                    }
                )
            library_variant = {
                "factor": True,
                "meanSetupSeconds": round(
                    statistics.fmean(run["setupSeconds"] for run in runs), 6
                ),
                "meanSolveSeconds": round(
                    statistics.fmean(run["solveSeconds"] for run in runs), 6
                ),
                "medianProofBytes": int(
                    statistics.median(run["proofBytes"] for run in runs)
                ),
                "runs": runs,
            }

    baseline, factored = variants
    result = {
        "benchmark": "pigeonhole proof-producing preprocessing",
        "holes": arguments.holes,
        "pigeons": arguments.holes + 1,
        "variables": formula.nv,
        "clauses": len(formula.clauses),
        "repetitions": arguments.repetitions,
        "variants": variants,
        "factorSpeedup": round(
            baseline["meanSeconds"] / factored["meanSeconds"], 3
        ),
        "factorProofSizeRatio": round(
            factored["medianProofBytes"] / baseline["medianProofBytes"], 3
        ),
    }
    if library_variant:
        result["libraryVariant"] = library_variant
        result["processToLibraryBoundarySpeedup"] = round(
            factored["meanSeconds"] / library_variant["meanSolveSeconds"], 3
        )
        result["processToLibraryIncludingSetupSpeedup"] = round(
            factored["meanSeconds"]
            / (
                library_variant["meanSetupSeconds"]
                + library_variant["meanSolveSeconds"]
            ),
            3,
        )
    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
