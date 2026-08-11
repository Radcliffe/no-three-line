#!/usr/bin/env python3
"""Lazy global solver and exact neighborhood repair for row-perfect rot4 factors."""

import argparse
import json
import math
import random
import time
from collections import Counter, defaultdict

import z3


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&@?!()[]<>{}=*+|-/~^_:;,."


def orbit(n, row, column):
    return (
        (row, column),
        (column, n - 1 - row),
        (n - 1 - row, n - 1 - column),
        (n - 1 - column, row),
    )


def canonical_line(first, second):
    first_row, first_column = first
    second_row, second_column = second
    a = second_row - first_row
    b = first_column - second_column
    c = -(a * first_column + b * first_row)
    divisor = math.gcd(math.gcd(abs(a), abs(b)), abs(c))
    a //= divisor
    b //= divisor
    c //= divisor
    if a < 0 or (a == 0 and b < 0):
        a, b, c = -a, -b, -c
    return a, b, c


def selected_violating_lines(n, arcs):
    return [key for key, _members in selected_violating_line_details(n, arcs)]


def selected_violating_line_details(n, arcs):
    points = []
    for arc_id, (row, column) in enumerate(arcs):
        for point in orbit(n, row, column):
            points.append((point, arc_id))

    lines = defaultdict(set)
    for first in range(len(points)):
        for second in range(first + 1, len(points)):
            key = canonical_line(points[first][0], points[second][0])
            lines[key].add(first)
            lines[key].add(second)
    return [
        (key, {points[index][1] for index in members})
        for key, members in lines.items()
        if len(members) >= 3
    ]


def arcs_from_code(code, expected_n=None):
    if not code.startswith("o") or (len(code) - 1) % 2:
        raise ValueError("expected a compact rot4 code with two columns per row")
    n = (len(code) - 1) // 2
    if expected_n is not None and n != expected_n:
        raise ValueError(f"code has n={n}, not n={expected_n}")
    if n < 6 or n > len(ALPHABET) or n % 2:
        raise ValueError("compact rot4 code must have an even size between 6 and 90")

    cells = set()
    for row in range(n):
        for slot in range(2):
            character = code[1 + 2 * row + slot]
            try:
                column = ALPHABET.index(character)
            except ValueError as error:
                raise ValueError(f"invalid compact-code character {character!r}") from error
            if column >= n or (row, column) in cells:
                raise ValueError("compact code has an invalid or duplicate cell")
            cells.add((row, column))

    m = n // 2
    arcs = sorted((row, column) for row, column in cells if row < m and column < m)
    if len(arcs) != m:
        raise ValueError("compact code does not contain one representative per rot4 orbit")
    expanded = {point for row, column in arcs for point in orbit(n, row, column)}
    if expanded != cells:
        raise ValueError("compact code is not invariant under a quarter turn")

    degrees = [0] * m
    for first, second in arcs:
        if first == second:
            degrees[first] += 2
        else:
            degrees[first] += 1
            degrees[second] += 1
    if any(degree != 2 for degree in degrees):
        raise ValueError("compact code is not a row-perfect quotient 2-factor")
    return n, arcs


def bad_line_metrics(n, arcs):
    points = [point for first, second in arcs for point in orbit(n, first, second)]
    lines = defaultdict(set)
    for first in range(len(points)):
        for second in range(first + 1, len(points)):
            lines[canonical_line(points[first], points[second])].update((first, second))
    counts = [len(members) for members in lines.values() if len(members) >= 3]
    return len(counts), sum(math.comb(count, 3) for count in counts)


def choose_free_vertices(n, arcs, details, minimum, halo, randomizer):
    m = n // 2
    line_vertices = []
    coverage = [set() for _ in range(m)]
    conflict_scores = [0] * m
    for line_index, (_key, arc_ids) in enumerate(details):
        vertices = set()
        for arc_id in arc_ids:
            first, second = arcs[arc_id]
            vertices.update((first, second))
        line_vertices.append(vertices)
        for vertex in vertices:
            coverage[vertex].add(line_index)
            conflict_scores[vertex] += 1

    free = set()
    uncovered = set(range(len(line_vertices)))
    while uncovered:
        vertex = max(
            (candidate for candidate in range(m) if candidate not in free),
            key=lambda candidate: len(coverage[candidate] & uncovered),
        )
        covered = coverage[vertex] & uncovered
        if not covered:
            break
        free.add(vertex)
        uncovered -= covered

    ranked = sorted(range(m), key=lambda vertex: (-conflict_scores[vertex], vertex))
    for vertex in ranked:
        if len(free) >= minimum:
            break
        free.add(vertex)

    remaining = [vertex for vertex in range(m) if vertex not in free]
    randomizer.shuffle(remaining)
    free.update(remaining[:halo])
    return free


def representative(n, row, column):
    m = n // 2
    for _ in range(4):
        if row < m and column < m:
            return row, column
        row, column = column, n - 1 - row
    raise AssertionError("orbit did not meet the fundamental domain")


def line_coefficients(n, key):
    a, b, c = key
    coefficients = Counter()
    if a == 0:
        if (-c) % b:
            return coefficients
        row = (-c) // b
        if not 0 <= row < n:
            return coefficients
        for column in range(n):
            coefficients[representative(n, row, column)] += 1
        return coefficients

    for row in range(n):
        numerator = -(b * row + c)
        if numerator % a:
            continue
        column = numerator // a
        if 0 <= column < n:
            coefficients[representative(n, row, column)] += 1
    return coefficients


def full_constraint_stats(n):
    incidences = set()
    for delta_row in range(n):
        for delta_column in range(-(n - 1), n):
            if (delta_row == 0 and delta_column <= 0) or math.gcd(delta_row, abs(delta_column)) != 1:
                continue
            for start_row in range(n):
                for start_column in range(n):
                    previous_row = start_row - delta_row
                    previous_column = start_column - delta_column
                    if 0 <= previous_row < n and 0 <= previous_column < n:
                        continue
                    points = []
                    row, column = start_row, start_column
                    while 0 <= row < n and 0 <= column < n:
                        points.append((row, column))
                        row += delta_row
                        column += delta_column
                    if len(points) < 3:
                        continue
                    coefficients = Counter(representative(n, row, column) for row, column in points)
                    if sum(coefficients.values()) > 2:
                        incidences.add(
                            tuple(
                                sorted(
                                    (row, column, coefficient)
                                    for (row, column), coefficient in coefficients.items()
                                )
                            )
                        )

    arities = Counter(len(incidence) for incidence in incidences)
    doubled = sum(
        any(coefficient == 2 for _, _, coefficient in incidence) for incidence in incidences
    )
    literals = sum(len(incidence) for incidence in incidences)
    return {
        "n": n,
        "constraints": len(incidences),
        "with_coefficient_2": doubled,
        "mean_arity": literals / len(incidences),
        "arity_histogram": dict(sorted(arities.items())),
    }


def compact_code(n, arcs):
    rows = [[] for _ in range(n)]
    for first, second in arcs:
        for row, column in orbit(n, first, second):
            rows[row].append(column)
    return "o" + "".join(ALPHABET[column] for row in rows for column in sorted(row))


def make_factor_solver(n, seed):
    m = n // 2
    variables = [[z3.Bool(f"y_{row}_{column}") for column in range(m)] for row in range(m)]
    solver = z3.Solver()
    solver.set(random_seed=seed)
    for vertex in range(m):
        terms = [(variables[vertex][vertex], 2)]
        terms.extend((variables[vertex][other], 1) for other in range(m) if other != vertex)
        terms.extend((variables[other][vertex], 1) for other in range(m) if other != vertex)
        solver.add(z3.PbEq(terms, 2))
    return solver, variables


def arcs_from_model(model, variables):
    m = len(variables)
    return [
        (row, column)
        for row in range(m)
        for column in range(m)
        if z3.is_true(model.eval(variables[row][column]))
    ]


def add_new_line_cuts(solver, variables, n, keys, cuts):
    added = 0
    for key in keys:
        coefficients = line_coefficients(n, key)
        incidence = tuple(
            sorted(
                (row, column, coefficient)
                for (row, column), coefficient in coefficients.items()
            )
        )
        if incidence in cuts:
            continue
        solver.add(
            z3.PbLe(
                [
                    (variables[row][column], coefficient)
                    for (row, column), coefficient in coefficients.items()
                ],
                2,
            )
        )
        cuts.add(incidence)
        added += 1
    return added


def solve(n, seconds, seed):
    randomizer = random.Random(seed)
    solver, variables = make_factor_solver(n, seed)

    deadline = time.monotonic() + seconds
    cuts = set()
    iterations = 0
    candidates = 0
    best_bad_lines = None

    while time.monotonic() < deadline:
        remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
        solver.set(timeout=remaining_ms)
        status = solver.check()
        iterations += 1
        if status != z3.sat:
            return {
                "status": str(status),
                "iterations": iterations,
                "candidates": candidates,
                "cuts": len(cuts),
                "best_bad_lines": best_bad_lines,
            }

        model = solver.model()
        arcs = arcs_from_model(model, variables)
        candidates += 1
        bad_lines = selected_violating_lines(n, arcs)
        if best_bad_lines is None or len(bad_lines) < best_bad_lines:
            best_bad_lines = len(bad_lines)
        if not bad_lines:
            return {
                "status": "sat",
                "iterations": iterations,
                "candidates": candidates,
                "cuts": len(cuts),
                "best_bad_lines": 0,
                "code": compact_code(n, arcs),
            }

        randomizer.shuffle(bad_lines)
        added = add_new_line_cuts(solver, variables, n, bad_lines, cuts)
        if added == 0:
            raise AssertionError("a violating model produced no new cut")

    return {
        "status": "timeout",
        "iterations": iterations,
        "candidates": candidates,
        "cuts": len(cuts),
        "best_bad_lines": best_bad_lines,
    }


def repair(n, seconds, seed, incumbent_code, core_vertices, halo_vertices, free_fraction, expand_by):
    _decoded_n, incumbent_arcs = arcs_from_code(incumbent_code, n)
    randomizer = random.Random(seed)
    solver, variables = make_factor_solver(n, seed)
    m = n // 2
    selected = set(incumbent_arcs)

    guards = [[z3.Bool(f"keep_{row}_{column}") for column in range(m)] for row in range(m)]
    for row in range(m):
        for column in range(m):
            solver.add(
                z3.Implies(
                    guards[row][column],
                    variables[row][column] == ((row, column) in selected),
                )
            )

    initial_details = selected_violating_line_details(n, incumbent_arcs)
    initial_bad_lines, initial_triples = bad_line_metrics(n, incumbent_arcs)
    if initial_bad_lines == 0:
        return {
            "status": "sat",
            "iterations": 0,
            "candidates": 0,
            "cuts": 0,
            "expansions": 0,
            "initial_free_vertices": 0,
            "free_vertices": 0,
            "initial_bad_lines": 0,
            "initial_triples": 0,
            "best_bad_lines": 0,
            "best_triples": 0,
            "code": incumbent_code,
        }

    minimum = max(core_vertices, math.ceil(free_fraction * m))
    free = choose_free_vertices(
        n,
        incumbent_arcs,
        initial_details,
        min(m, minimum),
        halo_vertices,
        randomizer,
    )
    initial_free_vertices = len(free)
    cuts = set()
    add_new_line_cuts(
        solver,
        variables,
        n,
        [key for key, _arc_ids in initial_details],
        cuts,
    )

    deadline = time.monotonic() + seconds
    iterations = 0
    candidates = 0
    expansions = 0
    best_arcs = incumbent_arcs
    best_bad_lines = initial_bad_lines
    best_triples = initial_triples
    final_status = "timeout"

    while time.monotonic() < deadline:
        remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
        solver.set(timeout=remaining_ms)
        assumptions = [
            guards[row][column]
            for row in range(m)
            for column in range(m)
            if row not in free and column not in free
        ]
        status = solver.check(*assumptions)
        iterations += 1

        if status == z3.unsat:
            if len(free) == m:
                final_status = "unsat"
                break
            if expand_by == 0:
                final_status = "unsat_neighborhood"
                break
            remaining = [vertex for vertex in range(m) if vertex not in free]
            randomizer.shuffle(remaining)
            free.update(remaining[: max(1, expand_by)])
            expansions += 1
            continue
        if status != z3.sat:
            final_status = str(status)
            break

        model = solver.model()
        arcs = arcs_from_model(model, variables)
        candidates += 1
        details = selected_violating_line_details(n, arcs)
        bad_lines, triples = bad_line_metrics(n, arcs)
        if (triples, bad_lines) < (best_triples, best_bad_lines):
            best_arcs = arcs
            best_bad_lines = bad_lines
            best_triples = triples
        if bad_lines == 0:
            return {
                "status": "sat",
                "iterations": iterations,
                "candidates": candidates,
                "cuts": len(cuts),
                "expansions": expansions,
                "initial_free_vertices": initial_free_vertices,
                "free_vertices": len(free),
                "initial_bad_lines": initial_bad_lines,
                "initial_triples": initial_triples,
                "best_bad_lines": 0,
                "best_triples": 0,
                "code": compact_code(n, arcs),
            }

        keys = [key for key, _arc_ids in details]
        randomizer.shuffle(keys)
        added = add_new_line_cuts(solver, variables, n, keys, cuts)
        if added == 0:
            raise AssertionError("a violating repair model produced no new cut")

    return {
        "status": final_status,
        "iterations": iterations,
        "candidates": candidates,
        "cuts": len(cuts),
        "expansions": expansions,
        "initial_free_vertices": initial_free_vertices,
        "free_vertices": len(free),
        "initial_bad_lines": initial_bad_lines,
        "initial_triples": initial_triples,
        "best_bad_lines": best_bad_lines,
        "best_triples": best_triples,
        "best_code": compact_code(n, best_arcs),
    }


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int, nargs="?", default=20, help="even board size")
    parser.add_argument("--seconds", type=float, default=10.0, help="wall-clock limit")
    parser.add_argument("--seed", type=int, default=1, help="deterministic solver and cut-order seed")
    parser.add_argument(
        "--incumbent",
        help="repair this row-perfect compact code by fixing arcs outside a conflict neighborhood",
    )
    parser.add_argument(
        "--core-vertices",
        type=int,
        default=6,
        help="minimum number of conflict vertices freed during incumbent repair",
    )
    parser.add_argument(
        "--halo-vertices",
        type=int,
        default=2,
        help="additional random quotient vertices freed around the conflict core",
    )
    parser.add_argument(
        "--free-fraction",
        type=float,
        default=0.15,
        help="minimum fraction of quotient vertices freed during repair",
    )
    parser.add_argument(
        "--expand-by",
        type=int,
        default=2,
        help="vertices added whenever the current repair neighborhood is unsatisfiable",
    )
    parser.add_argument(
        "--constraint-stats",
        action="store_true",
        help="enumerate reduced line-incidence statistics instead of solving",
    )
    arguments = parser.parse_args()
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if arguments.seconds <= 0:
        parser.error("--seconds must be positive")
    if arguments.core_vertices < 0 or arguments.halo_vertices < 0 or arguments.expand_by < 0:
        parser.error("repair neighborhood sizes must be nonnegative")
    if not 0 <= arguments.free_fraction <= 1:
        parser.error("--free-fraction must be between zero and one")
    return arguments


def main():
    arguments = parse_arguments()
    if arguments.constraint_stats:
        print(json.dumps(full_constraint_stats(arguments.n), sort_keys=True))
        return

    start = time.monotonic()
    if arguments.incumbent:
        result = repair(
            arguments.n,
            arguments.seconds,
            arguments.seed,
            arguments.incumbent,
            arguments.core_vertices,
            arguments.halo_vertices,
            arguments.free_fraction,
            arguments.expand_by,
        )
    else:
        result = solve(arguments.n, arguments.seconds, arguments.seed)
    result.update(n=arguments.n, seconds=round(time.monotonic() - start, 3), seed=arguments.seed)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
