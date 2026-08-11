#!/usr/bin/env python3
"""Run a deterministic seed portfolio and summarize censored search curves."""

import argparse
import json
import re
import statistics
import subprocess
import time
from pathlib import Path


SUMMARY_PATTERN = re.compile(r"(?:^| )([a-z_]+)=([^ ]+)")
PROGRESS_PATTERN = re.compile(r"progress_ms=(\d+) best_energy=(\d+) thread=(\d+)")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("n", type=int)
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=1, help="first seed; subsequent runs increment it")
    parser.add_argument("--lift-from", type=int)
    parser.add_argument("--solutions", type=Path, default=Path("optimal-solutions.generated.js"))
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if min(arguments.seconds, arguments.threads, arguments.runs) < 1:
        parser.error("--seconds, --threads, and --runs must be positive")
    return arguments


def energy_at(events, milliseconds):
    value = events[0][1]
    for event_time, energy, _thread in events:
        if event_time > milliseconds:
            break
        value = energy
    return value


def run_once(arguments, seed, project_root):
    command = [
        str(arguments.executable.resolve()),
        str(arguments.n),
        str(arguments.seconds),
        str(arguments.threads),
        "--seed",
        str(seed),
    ]
    if arguments.lift_from is not None:
        command.extend(
            [
                "--lift-from",
                str(arguments.lift_from),
                "--solutions",
                str(arguments.solutions),
            ]
        )
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.monotonic() - started
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"search failed with exit {completed.returncode}:\n{completed.stderr}")

    lines = completed.stdout.splitlines()
    summary_line = next((line for line in lines if line.startswith("n=")), None)
    if summary_line is None:
        raise RuntimeError(f"search emitted no summary:\n{completed.stdout}")
    summary = dict(SUMMARY_PATTERN.findall(summary_line))
    events = [
        (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        for line in lines
        if (match := PROGRESS_PATTERN.fullmatch(line))
    ]
    if not events:
        raise RuntimeError("search emitted no progress events")
    code_line = next((line for line in lines if line.startswith("best_code=")), None)
    best_code = code_line.removeprefix("best_code=") if code_line else None
    solved = int(summary["best_energy"]) == 0
    validation = None
    if solved:
        checked = subprocess.run(
            ["node", "research/validate-rot4-code.js", best_code],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        validation = json.loads(checked.stdout or checked.stderr)
        if checked.returncode != 0 or not validation.get("valid"):
            raise RuntimeError(f"validator rejected a zero-energy code: {validation}")
    zero_event = next((event for event in events if event[1] == 0), None)
    return {
        "seed": seed,
        "solved": solved,
        "wallSeconds": round(elapsed, 6),
        "timeToZeroMs": zero_event[0] if zero_event else None,
        "initialEnergy": float(summary["initial_energy"]),
        "bestEnergy": int(summary["best_energy"]),
        "iterations": int(summary["iterations"]),
        "restarts": int(summary["restarts"]),
        "progress": [
            {"milliseconds": milliseconds, "energy": energy, "thread": thread}
            for milliseconds, energy, thread in events
        ],
        "bestCode": best_code,
        "validation": validation,
    }


def summarize(arguments, runs):
    checkpoints = [0.1, 0.25, 0.5, 0.75, 1.0]
    curves = []
    for fraction in checkpoints:
        milliseconds = int(arguments.seconds * 1000 * fraction)
        values = [
            energy_at(
                [
                    (event["milliseconds"], event["energy"], event["thread"])
                    for event in run["progress"]
                ],
                milliseconds,
            )
            for run in runs
        ]
        curves.append(
            {
                "milliseconds": milliseconds,
                "minimum": min(values),
                "median": statistics.median(values),
                "mean": statistics.fmean(values),
                "solvedFraction": sum(value == 0 for value in values) / len(values),
            }
        )
    solved_times = [run["timeToZeroMs"] for run in runs if run["timeToZeroMs"] is not None]
    final = [run["bestEnergy"] for run in runs]
    return {
        "n": arguments.n,
        "secondsPerRun": arguments.seconds,
        "threadsPerRun": arguments.threads,
        "runs": len(runs),
        "firstSeed": arguments.seed,
        "liftFrom": arguments.lift_from,
        "solved": len(solved_times),
        "solvedFraction": len(solved_times) / len(runs),
        "medianTimeToZeroMs": statistics.median(solved_times) if solved_times else None,
        "finalEnergy": {
            "minimum": min(final),
            "median": statistics.median(final),
            "mean": statistics.fmean(final),
            "maximum": max(final),
        },
        "censoredCurve": curves,
        "runResults": runs,
    }


def main():
    arguments = parse_arguments()
    project_root = Path(__file__).resolve().parent.parent
    runs = [
        run_once(arguments, arguments.seed + offset, project_root)
        for offset in range(arguments.runs)
    ]
    result = summarize(arguments, runs)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
