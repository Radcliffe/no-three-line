#!/usr/bin/env python3
"""Add an announced configuration and its attribution, then run npm test."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from math import gcd
from pathlib import Path

from convert_optimal_solutions import (
    ALPHABET,
    SYMMETRY_CHARACTER,
    Solution,
    format_solution_object,
    parse_solutions,
)

ROOT = Path(__file__).resolve().parent
MONTHS = (
    "January February March April May June July August September October November December"
).split()
FILES = (
    "README.md",
    "optimal-solutions.txt",
    "optimal-solutions.generated.js",
    "ATTRIBUTION.md",
    "optimal-solution-attributions.js",
    "test/configuration-codec.test.js",
    "test/game.test.js",
)


def validate_discovery(n: int, code: str, discoverer: str, discovered: str) -> Solution:
    if not 3 <= n <= len(ALPHABET):
        raise ValueError(f"The app supports sizes from 3 to {len(ALPHABET)}.")
    if not discoverer or not discoverer.isprintable():
        raise ValueError("The discoverer must be a nonempty, single-line name.")
    match = re.fullmatch(r"([A-Za-z]+) ([1-9][0-9]?), ([0-9]{4})", discovered)
    if not match or match[1] not in MONTHS:
        raise ValueError("Use a date like October 28, 2026.")
    date(int(match[3]), MONTHS.index(match[1]) + 1, int(match[2]))
    groups = {character: group for group, character in SYMMETRY_CHARACTER.items()}
    if len(code) != 2 * n + 1 or code[0] not in groups:
        raise ValueError(f"Expected a symmetry character followed by {2 * n} columns.")
    cells = []
    for row in range(n):
        left, right = (ALPHABET.find(c) for c in code[1 + 2 * row:3 + 2 * row])
        if not 0 <= left < right < n:
            raise ValueError(f"Row {row + 1} needs two in-range columns in ascending order.")
        cells.extend(((row, left), (row, right)))
    # From each point, two later points with the same reduced direction form a line.
    for i, (row, column) in enumerate(cells):
        directions = set()
        for other_row, other_column in cells[i + 1:]:
            dr, dc = other_row - row, other_column - column
            divisor = gcd(dr, dc)
            direction = (dr // divisor, dc // divisor)
            if direction in directions:
                raise ValueError("The configuration contains three collinear points.")
            directions.add(direction)
    return Solution(n, cells, groups[code[0]])


def replace_once(text: str, pattern: str, replacement: str) -> str:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected one update location for {pattern!r}; found {len(matches)}.")
    match = matches[0]
    return text[:match.start()] + replacement + text[match.end():]


def insert_by_size(text: str, pattern: str, n: int, entry: str) -> str:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if not matches:
        raise ValueError("Could not locate existing attribution entries.")
    if any(int(match[1]) == n for match in matches):
        raise ValueError(f"An attribution for size {n} already exists.")
    position = next(
        (match.start() for match in matches if int(match[1]) > n), matches[-1].end()
    )
    return text[:position] + entry + text[position:]


def size_ranges(sizes: list[int]) -> str:
    ranges = []
    for size in sorted(sizes):
        if ranges and size == ranges[-1][1] + 1:
            ranges[-1][1] = size
        else:
            ranges.append([size, size])
    labels = [str(a) if a == b else f"{a} through {b}" for a, b in ranges]
    if not labels:
        return "none"
    if len(labels) < 3:
        return " and ".join(labels)
    return ", ".join(labels[:-1]) + ", and " + labels[-1]


def markdown_name(name: str) -> str:
    # Entities keep punctuation literal, including pipes in the Markdown table.
    return "".join(c if c.isalnum() or c == " " else f"&#{ord(c)};" for c in name)


def prepare_updates(originals: dict[str, str], solution: Solution,
                    discoverer: str, discovered: str) -> dict[str, str]:
    source = originals["optimal-solutions.txt"]
    solutions = parse_solutions(source)
    sizes = {item.size for item in solutions}
    if len(sizes) != len(solutions):
        raise ValueError("The source records contain duplicate sizes; resolve them first.")
    if solution.size in sizes:
        raise ValueError(f"Size {solution.size} already has a bundled solution.")
    if format_solution_object(solutions) != originals["optimal-solutions.generated.js"]:
        raise ValueError("The source records and generated bundle differ; reconcile them first.")
    n = solution.size
    sizes.add(n)
    missing = sorted(set(range(3, len(ALPHABET) + 1)) - sizes)
    updates = dict(originals)
    cells = set(solution.cells)
    grid = "\n".join(
        " " + " ".join("o" if (row, column) in cells else "." for column in range(n))
        for row in range(n)
    )
    updates["optimal-solutions.txt"] = (
        source.rstrip() + f"\n\n#{n}\nNo-Three-in-Line Configuration in Database\n\n"
        f"  1. Lösung:     Sym.-Gruppe  {solution.symmetry_group}\n{grid}\n"
    )
    updates["optimal-solutions.generated.js"] = format_solution_object([*solutions, solution])
    updates["README.md"] = replace_once(
        originals["README.md"],
        r"^The app supports grids from .*\.$",
        f"The app supports grids from 3 × 3 through {len(ALPHABET)} × {len(ALPHABET)} "
        f"and includes known configurations for sizes {size_ranges(sorted(sizes))}.",
    )
    updates["README.md"] = replace_once(
        updates["README.md"], r"^The bundle currently covers [^\n]+",
        f"The bundle currently covers {len(sizes)} sizes: {size_ranges(sorted(sizes))}; "
        f"it omits {size_ranges(missing)}.",
    )
    updates["optimal-solution-attributions.js"] = insert_by_size(
        originals["optimal-solution-attributions.js"],
        r"^  (\d+): \{[^}]*\},\n", n,
        f"  {n}: {{ discoverer: {json.dumps(discoverer, ensure_ascii=False)}, "
        f"date: {json.dumps(discovered)} }},\n",
    )
    updates["ATTRIBUTION.md"] = insert_by_size(
        originals["ATTRIBUTION.md"], r"^\| (\d+) \|[^\n]*\n", n,
        f"| {n} | `{solution.symmetry_group}` | {markdown_name(discoverer)} | "
        f"{discovered} | Explicit |\n",
    )
    updates["test/configuration-codec.test.js"] = replace_once(
        originals["test/configuration-codec.test.js"],
        r"^const numberOfSolutions = \d+; // UPDATE$",
        f"const numberOfSolutions = {len(sizes)}; // UPDATE",
    )
    updates["test/game.test.js"] = replace_once(
        originals["test/game.test.js"], r"^    [\d, ]*// UPDATE$",
        "    " + "".join(f"{size}, " for size in missing) + "// UPDATE",
    )
    return updates


def apply_updates(root: Path, originals: dict[str, str], updates: dict[str, str]) -> None:
    written = []
    try:
        for name, content in updates.items():
            if content != originals[name]:
                written.append(name)
                (root / name).write_text(content, encoding="utf-8")
        print("Updated files. Running npm test…", flush=True)
        subprocess.run(["npm", "test"], cwd=root, check=True)
    except (OSError, subprocess.CalledProcessError, KeyboardInterrupt):
        for name in written:
            (root / name).write_text(originals[name], encoding="utf-8")
        print("Update failed; restored the original files.", file=sys.stderr)
        raise


def main() -> int:
    try:
        n = int(input("Size of the square (n): ").strip())
        code = input("Encoded configuration: ").strip()
        discoverer = input("Discoverer: ").strip()
        discovered = input("Date of discovery (e.g. October 28, 2026): ").strip()
        solution = validate_discovery(n, code, discoverer, discovered)
        originals = {name: (ROOT / name).read_text(encoding="utf-8") for name in FILES}
        updates = prepare_updates(originals, solution, discoverer, discovered)
        apply_updates(ROOT, originals, updates)
    except (ValueError, OSError, EOFError, subprocess.CalledProcessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    print(f"Added size {n}; npm test passed. Manually test the app, then commit and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
