#!/usr/bin/env python3
"""Convert copied no-three-in-line solution text into a JavaScript object.

Input blocks may look like this:

    No-Three-in-Line Configuration in Database

      1. Lösung:     Sym.-Gruppe  rct4
     . . . o o . . . .
     . o . . . . o . .
     ...

The output is suitable for the web app's `optimalSolutions` object:

    const optimalSolutions = {
      9: {
        cells: [[0, 3], [0, 4], ...],
        symmetryGroup: "rct4",
      },
    };
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

GRID_ROW_RE = re.compile(r"^\s*[.oO](?:\s+[.oO])*\s*$")
SYMMETRY_RE = re.compile(r"(?:Sym\.-Gruppe|symmetry)\s+([^\s]+)", re.IGNORECASE)


@dataclass(frozen=True)
class Solution:
    size: int
    cells: list[tuple[int, int]]
    symmetry_group: str


def is_grid_row(line: str) -> bool:
    """Return True if a line consists only of dot/o grid tokens."""
    return bool(GRID_ROW_RE.match(line))


def parse_grid_row(line: str) -> list[str]:
    """Parse a grid row into tokens, accepting either `o` or `O` as active."""
    return [token.lower() for token in line.strip().split()]


def parse_solutions(text: str) -> list[Solution]:
    """Extract every square grid solution block from the pasted text."""
    lines = text.splitlines()
    solutions: list[Solution] = []
    pending_symmetry = ""
    i = 0

    while i < len(lines):
        line = lines[i]

        symmetry_match = SYMMETRY_RE.search(line)
        if symmetry_match:
            pending_symmetry = symmetry_match.group(1).strip()
            i += 1
            continue

        if not is_grid_row(line):
            i += 1
            continue

        grid: list[list[str]] = []
        while i < len(lines) and is_grid_row(lines[i]):
            grid.append(parse_grid_row(lines[i]))
            i += 1

        row_count = len(grid)
        if row_count == 0:
            continue

        column_counts = {len(row) for row in grid}
        if len(column_counts) != 1:
            raise ValueError(
                f"Found a malformed grid with uneven row lengths near line {i + 1}."
            )

        column_count = column_counts.pop()
        if row_count != column_count:
            raise ValueError(
                f"Found a non-square grid near line {i + 1}: {row_count} rows, {column_count} columns."
            )

        cells = [
            (row_index, col_index)
            for row_index, row in enumerate(grid)
            for col_index, token in enumerate(row)
            if token == "o"
        ]

        solutions.append(
            Solution(
                size=row_count,
                cells=cells,
                symmetry_group=pending_symmetry,
            )
        )
        pending_symmetry = ""

    return solutions


def js_string(value: str) -> str:
    """Return a safely quoted JavaScript string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def format_solution_object(
    solutions: Iterable[Solution], const_name: str = "optimalSolutions"
) -> str:
    """Format solutions as a JavaScript const object."""
    by_size: dict[int, Solution] = {}
    duplicates: list[int] = []

    for solution in solutions:
        if solution.size in by_size:
            duplicates.append(solution.size)
        by_size[solution.size] = solution

    if duplicates:
        repeated = ", ".join(str(n) for n in sorted(set(duplicates)))
        print(
            f"Warning: duplicate solution size(s) found: {repeated}. Keeping the last one for each size.",
            file=sys.stderr,
        )

    lines: list[str] = [f"const {const_name} = {{"]

    for size in sorted(by_size):
        solution = by_size[size]
        lines.append(f"  {size}: {{")
        lines.append("    cells: [")
        for row, col in solution.cells:
            lines.append(f"      [{row}, {col}],")
        lines.append("    ],")
        lines.append(f"    symmetryGroup: {js_string(solution.symmetry_group)},")
        lines.append("  },")

    lines.append("};")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert pasted no-three-in-line solution text into a JavaScript optimalSolutions object."
    )
    parser.add_argument(
        "input", type=Path, help="Input text file copied from the solution website."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JavaScript file. If omitted, writes to standard output.",
    )
    parser.add_argument(
        "--const-name",
        default="optimalSolutions",
        help="JavaScript const name to emit. Default: optimalSolutions.",
    )
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    solutions = parse_solutions(text)

    if not solutions:
        raise SystemExit(
            "No solution grids were found. Expected rows containing only '.' and 'o' tokens."
        )

    output = format_solution_object(solutions, args.const_name)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")

    print(f"Converted {len(solutions)} solution(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
