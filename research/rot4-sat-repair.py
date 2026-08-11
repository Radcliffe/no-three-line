#!/usr/bin/env python3
"""Native incremental-SAT repair for row-perfect rot4 factor incumbents."""

import argparse
import ctypes
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time
from collections import Counter, defaultdict
from array import array
from itertools import combinations
from pathlib import Path

try:
    from pysat.card import CardEnc, EncType
    from pysat.formula import CNF, IDPool
    from pysat.solvers import Solver
except ImportError as error:
    raise SystemExit(
        "PySAT is required. Install the research dependencies with "
        "`python -m pip install -r research/requirements.txt`."
    ) from error


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&@?!()[]<>{}=*+|-/~^_:;,."


def resolve_executable(executable):
    resolved = shutil.which(str(executable))
    if resolved is not None:
        return resolved
    candidate = Path(executable).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    raise FileNotFoundError(f"could not find executable {str(executable)!r}")


class CadicalShadow:
    ERROR_BYTES = 1024

    def __init__(self, library, proof_path, factor=True):
        self.library_path = resolve_executable(library)
        self.proof_path = Path(proof_path)
        self.factor = factor
        self.clauses = 0
        self.add_calls = 0
        self.literals = 0
        self.pack_seconds = 0.0
        self.bridge_seconds = 0.0
        self.add_seconds = 0.0
        self.closed = False
        self.solved = False
        self.library = ctypes.CDLL(self.library_path)
        self._configure_api()
        self.version = self.library.no3_cadical_version().decode("ascii")
        error = ctypes.create_string_buffer(self.ERROR_BYTES)
        self.handle = self.library.no3_cadical_create(
            os.fsencode(self.proof_path),
            int(factor),
            error,
            len(error),
        )
        if not self.handle:
            raise RuntimeError(
                f"could not create in-process CaDiCaL: {error.value.decode(errors='replace')}"
            )

    def _configure_api(self):
        self.library.no3_cadical_version.argtypes = []
        self.library.no3_cadical_version.restype = ctypes.c_char_p
        self.library.no3_cadical_create.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        self.library.no3_cadical_create.restype = ctypes.c_void_p
        self.library.no3_cadical_add.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        self.library.no3_cadical_add.restype = ctypes.c_int
        self.library.no3_cadical_solve.argtypes = [
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        self.library.no3_cadical_solve.restype = ctypes.c_int
        self.library.no3_cadical_release.argtypes = [ctypes.c_void_p]
        self.library.no3_cadical_release.restype = None

    def add_clauses(self, clauses):
        add_started = time.monotonic()
        pack_started = time.monotonic()
        flattened = array("i")
        clause_count = 0
        for clause in clauses:
            flattened.extend(clause)
            flattened.append(0)
            clause_count += 1
        if not flattened:
            return
        pack_seconds = time.monotonic() - pack_started
        if flattened.itemsize != ctypes.sizeof(ctypes.c_int):
            raise RuntimeError("native integer array is incompatible with the bridge ABI")
        buffer_type = ctypes.c_int * len(flattened)
        buffer = buffer_type.from_buffer(flattened)
        error = ctypes.create_string_buffer(self.ERROR_BYTES)
        bridge_started = time.monotonic()
        result = self.library.no3_cadical_add(
            self.handle,
            buffer,
            len(flattened),
            error,
            len(error),
        )
        bridge_seconds = time.monotonic() - bridge_started
        if result != 0:
            raise RuntimeError(
                f"could not synchronize CaDiCaL clauses: {error.value.decode(errors='replace')}"
            )
        self.clauses += clause_count
        self.add_calls += 1
        self.literals += len(flattened) - clause_count
        self.pack_seconds += pack_seconds
        self.bridge_seconds += bridge_seconds
        self.add_seconds += time.monotonic() - add_started

    def statistics(self):
        return {
            "clauses": self.clauses,
            "addCalls": self.add_calls,
            "literals": self.literals,
            "packSeconds": round(self.pack_seconds, 6),
            "bridgeSeconds": round(self.bridge_seconds, 6),
            "addSeconds": round(self.add_seconds, 6),
        }

    def solve(self, seconds):
        error = ctypes.create_string_buffer(self.ERROR_BYTES)
        started = time.monotonic()
        code = self.library.no3_cadical_solve(
            self.handle,
            seconds,
            error,
            len(error),
        )
        self.solved = True
        if code == 20:
            status = "unsat"
            output = "s UNSATISFIABLE"
        elif code == 10:
            status = "sat"
            output = "s SATISFIABLE"
        elif code == 0:
            status = "timeout"
            output = "c UNKNOWN"
        else:
            status = "failed"
            output = error.value.decode(errors="replace")
        proof_bytes = self.proof_path.stat().st_size if self.proof_path.is_file() else 0
        if status == "unsat" and proof_bytes == 0:
            status = "failed"
            output = "CaDiCaL returned UNSAT without a nonempty proof"
        return {
            "status": status,
            "backend": "cadical-library",
            "version": self.version,
            "proofFormat": "binary DRAT",
            "factor": self.factor,
            "library": self.library_path,
            "librarySha256": hashlib.sha256(
                Path(self.library_path).read_bytes()
            ).hexdigest(),
            "solverStatus": code,
            "proofBytes": proof_bytes,
            **self.statistics(),
            "seconds": round(time.monotonic() - started, 6),
            "output": output,
        }

    def close(self):
        if self.closed:
            return
        self.library.no3_cadical_release(self.handle)
        self.closed = True


def run_cadical_proof(executable, cnf_path, proof_path, seconds, factor=True):
    resolved = resolve_executable(executable)
    started = time.monotonic()
    command = [
        resolved,
        "-q",
        "-t",
        str(max(1, math.ceil(seconds))),
        str(cnf_path),
        str(proof_path),
    ]
    if factor:
        command.insert(2, "--factor")
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=seconds + 2.0,
        )
        output = "\n".join(
            part.strip().replace("\r", "")
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        proof_exists = Path(proof_path).is_file()
        proof_bytes = Path(proof_path).stat().st_size if proof_exists else 0
        if (
            completed.returncode == 20
            and "s UNSATISFIABLE" in output
            and proof_bytes > 0
        ):
            status = "unsat"
        elif completed.returncode == 10 and "s SATISFIABLE" in output:
            status = "sat"
        elif completed.returncode == 0 and "UNKNOWN" in output:
            status = "timeout"
        else:
            status = "failed"
        return {
            "status": status,
            "backend": "cadical",
            "proofFormat": "binary DRAT",
            "factor": factor,
            "executable": resolved,
            "executableSha256": hashlib.sha256(Path(resolved).read_bytes()).hexdigest(),
            "exitCode": completed.returncode,
            "proofBytes": proof_bytes,
            "seconds": round(time.monotonic() - started, 6),
            "output": output[-4000:],
        }
    except subprocess.TimeoutExpired as error:
        output = "\n".join(
            str(part).strip().replace("\r", "")
            for part in (error.stdout, error.stderr)
            if part
        )
        proof_exists = Path(proof_path).is_file()
        return {
            "status": "timeout",
            "backend": "cadical",
            "proofFormat": "binary DRAT",
            "factor": factor,
            "executable": resolved,
            "executableSha256": hashlib.sha256(Path(resolved).read_bytes()).hexdigest(),
            "exitCode": None,
            "proofBytes": Path(proof_path).stat().st_size if proof_exists else 0,
            "seconds": round(time.monotonic() - started, 6),
            "output": output[-4000:],
        }


def run_drat_checker(executable, cnf_path, proof_path, seconds, lrat_path=None):
    resolved = resolve_executable(executable)
    started = time.monotonic()
    command = [
        resolved,
        str(cnf_path),
        str(proof_path),
    ]
    if lrat_path:
        command.extend(["-L", str(lrat_path)])
    command.extend(
        [
            "-t",
            str(max(1, math.ceil(seconds))),
        ]
    )
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=seconds + 2.0,
        )
        output = "\n".join(
            part.strip().replace("\r", "")
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        verified = completed.returncode == 0 and "s VERIFIED" in output
        if lrat_path:
            verified = verified and Path(lrat_path).is_file() and Path(lrat_path).stat().st_size > 0
        return {
            "status": "verified" if verified else "failed",
            "executable": resolved,
            "executableSha256": hashlib.sha256(Path(resolved).read_bytes()).hexdigest(),
            "exitCode": completed.returncode,
            "seconds": round(time.monotonic() - started, 6),
            "output": output[-4000:],
        }
    except subprocess.TimeoutExpired as error:
        output = "\n".join(
            str(part).strip().replace("\r", "")
            for part in (error.stdout, error.stderr)
            if part
        )
        return {
            "status": "timeout",
            "executable": resolved,
            "executableSha256": hashlib.sha256(Path(resolved).read_bytes()).hexdigest(),
            "exitCode": None,
            "seconds": round(time.monotonic() - started, 6),
            "output": output[-4000:],
        }


def run_lrat_checker(executable, cnf_path, lrat_path, seconds):
    resolved = resolve_executable(executable)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [resolved, str(cnf_path), str(lrat_path)],
            text=True,
            capture_output=True,
            check=False,
            timeout=seconds,
        )
        output = "\n".join(
            part.strip().replace("\r", "")
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        verification_marker = next(
            (
                marker
                for marker in ("s VERIFIED UNSAT", "c VERIFIED")
                if marker in output
            ),
            None,
        )
        verified = completed.returncode == 0 and verification_marker is not None
        return {
            "status": "verified" if verified else "failed",
            "verificationMarker": verification_marker,
            "executable": resolved,
            "executableSha256": hashlib.sha256(Path(resolved).read_bytes()).hexdigest(),
            "exitCode": completed.returncode,
            "seconds": round(time.monotonic() - started, 6),
            "output": output[-4000:],
        }
    except subprocess.TimeoutExpired as error:
        output = "\n".join(
            str(part).strip().replace("\r", "")
            for part in (error.stdout, error.stderr)
            if part
        )
        return {
            "status": "timeout",
            "verificationMarker": None,
            "executable": resolved,
            "executableSha256": hashlib.sha256(Path(resolved).read_bytes()).hexdigest(),
            "exitCode": None,
            "seconds": round(time.monotonic() - started, 6),
            "output": output[-4000:],
        }


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


def arcs_from_code(code, expected_n):
    if not code.startswith("o") or (len(code) - 1) % 2:
        raise ValueError("expected a compact rot4 code with two columns per row")
    n = (len(code) - 1) // 2
    if n != expected_n:
        raise ValueError(f"code has n={n}, not n={expected_n}")
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
    expanded = {point for row, column in arcs for point in orbit(n, row, column)}
    if len(arcs) != m or expanded != cells:
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
    return arcs


def compact_code(n, arcs):
    rows = [[] for _ in range(n)]
    for first, second in arcs:
        for row, column in orbit(n, first, second):
            rows[row].append(column)
    return "o" + "".join(ALPHABET[column] for row in rows for column in sorted(row))


def selected_line_data(n, arcs):
    points = []
    for arc_id, (row, column) in enumerate(arcs):
        for point in orbit(n, row, column):
            points.append((point, arc_id))
    lines = defaultdict(set)
    for first in range(len(points)):
        for second in range(first + 1, len(points)):
            key = canonical_line(points[first][0], points[second][0])
            lines[key].update((first, second))

    details = []
    triples = 0
    for key, members in lines.items():
        if len(members) < 3:
            continue
        details.append((key, {points[index][1] for index in members}))
        triples += math.comb(len(members), 3)
    return details, triples


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


def conflict_vertex_data(n, arcs, details):
    m = n // 2
    coverage = [set() for _ in range(m)]
    conflict_scores = [0] * m
    line_vertices = []
    for line_index, (_key, arc_ids) in enumerate(details):
        vertices = set()
        for arc_id in arc_ids:
            vertices.update(arcs[arc_id])
        line_vertices.append(vertices)
        for vertex in vertices:
            coverage[vertex].add(line_index)
            conflict_scores[vertex] += 1
    return coverage, conflict_scores, line_vertices


def greedy_conflict_cover(coverage, conflict_scores, line_count, randomizer, policy):
    free = set()
    uncovered = set(range(line_count))
    while uncovered:
        gains = {
            candidate: len(coverage[candidate] & uncovered)
            for candidate in range(len(coverage))
            if candidate not in free
        }
        best_gain = max(gains.values(), default=0)
        if not best_gain:
            break
        candidates = [
            candidate for candidate, gain in gains.items() if gain == best_gain
        ]
        if policy == "greedy-conflict":
            best_score = max(conflict_scores[candidate] for candidate in candidates)
            candidates = [
                candidate
                for candidate in candidates
                if conflict_scores[candidate] == best_score
            ]
            vertex = min(candidates)
        elif policy == "greedy-random":
            vertex = randomizer.choice(candidates)
        else:
            vertex = min(candidates)
        free.add(vertex)
        uncovered -= coverage[vertex]
    return free, uncovered


def minimum_conflict_cover(line_vertices, m, upper_bound, randomizer):
    started = time.monotonic()
    order = list(range(m))
    randomizer.shuffle(order)
    variable = {vertex: index + 1 for index, vertex in enumerate(order)}
    hard_clauses = [
        [variable[vertex] for vertex in vertices] for vertices in line_vertices
    ]
    maximum_coverage = max(
        (
            sum(vertex in vertices for vertices in line_vertices)
            for vertex in range(m)
        ),
        default=1,
    )
    lower_bound = max(1, math.ceil(len(line_vertices) / maximum_coverage))
    attempts = 0
    for bound in range(lower_bound, upper_bound + 1):
        cardinality = CardEnc.atmost(
            lits=list(range(1, m + 1)),
            bound=bound,
            top_id=m,
            encoding=EncType.seqcounter,
        )
        attempts += 1
        with Solver(
            name="cadical195",
            bootstrap_with=[*hard_clauses, *cardinality.clauses],
        ) as cover_solver:
            if not cover_solver.solve():
                continue
            positive = {
                literal
                for literal in cover_solver.get_model()
                if 0 < literal <= m
            }
            cover = {order[literal - 1] for literal in positive}
            return cover, {
                "lowerBound": lower_bound,
                "attempts": attempts,
                "seconds": round(time.monotonic() - started, 6),
            }
    raise AssertionError("greedy upper bound was not a valid conflict cover")


def choose_free_vertices(
    n,
    arcs,
    details,
    minimum,
    halo,
    randomizer,
    policy="greedy",
    return_metadata=False,
    halo_randomizer=None,
):
    m = n // 2
    coverage, conflict_scores, line_vertices = conflict_vertex_data(n, arcs, details)

    greedy, uncovered = greedy_conflict_cover(
        coverage,
        conflict_scores,
        len(details),
        randomizer,
        "greedy" if policy == "minimum" else policy,
    )
    exact = None
    if policy == "minimum":
        free, exact = minimum_conflict_cover(
            line_vertices,
            m,
            len(greedy),
            randomizer,
        )
        uncovered = {
            line_index
            for line_index, vertices in enumerate(line_vertices)
            if free.isdisjoint(vertices)
        }
    else:
        free = greedy

    if uncovered:
        raise AssertionError("initial repair neighborhood leaves a violated line fixed")
    cover_vertices = sorted(free)

    minimum_fill = []
    for vertex in sorted(range(m), key=lambda item: (-conflict_scores[item], item)):
        if len(free) >= minimum:
            break
        if vertex in free:
            continue
        free.add(vertex)
        minimum_fill.append(vertex)
    remaining = [vertex for vertex in range(m) if vertex not in free]
    (halo_randomizer or randomizer).shuffle(remaining)
    halo_vertices = remaining[:halo]
    free.update(halo_vertices)
    if not return_metadata:
        return free
    return free, {
        "policy": policy,
        "coverVertices": cover_vertices,
        "coverSize": len(cover_vertices),
        "minimumFillVertices": minimum_fill,
        "haloVertices": halo_vertices,
        "freeVertices": sorted(free),
        "exact": exact,
    }


def choose_core_vertices(core, m, free, count, randomizer, policy):
    core_arcs = []
    for assumption in core:
        variable = abs(assumption) - 1
        if variable >= m * m:
            continue
        row, column = divmod(variable, m)
        core_arcs.append((row, column))

    candidates = [vertex for vertex in range(m) if vertex not in free]
    randomizer.shuffle(candidates)
    coverage = {
        vertex: {
            index
            for index, (row, column) in enumerate(core_arcs)
            if row == vertex or column == vertex
        }
        for vertex in candidates
    }
    raw_scores = {
        vertex: sum(
            (row == vertex) + (column == vertex) for row, column in core_arcs
        )
        for vertex in candidates
    }
    chosen = []
    if policy == "random":
        chosen = candidates[:count]
    elif policy == "marginal":
        uncovered = set(range(len(core_arcs)))
        remaining = list(candidates)
        while remaining and len(chosen) < count:
            vertex = max(
                remaining,
                key=lambda candidate: len(coverage[candidate] & uncovered),
            )
            chosen.append(vertex)
            uncovered -= coverage[vertex]
            remaining.remove(vertex)
    else:
        candidates.sort(key=lambda vertex: -raw_scores[vertex])
        chosen = candidates[:count]

    covered = set().union(*(coverage[vertex] for vertex in chosen)) if chosen else set()
    return chosen, {
        "policy": policy,
        "coreSize": len(core),
        "arcAssumptions": len(core_arcs),
        "coveredArcAssumptions": len(covered),
        "remainingArcAssumptions": len(core_arcs) - len(covered),
    }


class FactorSat:
    def __init__(
        self,
        n,
        solver_name,
        direct_threshold,
        conflict_chunk=1_000,
        propagation_chunk=1_000_000,
        retain_formula=False,
        shadow_sync="deferred",
    ):
        self.n = n
        self.m = n // 2
        self.solver_name = solver_name
        self.solver_key = solver_name.lower()
        if "kissat" in self.solver_key:
            raise ValueError("Kissat does not support the assumptions required for neighborhood repair")
        self.direct_threshold = direct_threshold
        self.conflict_chunk = conflict_chunk
        self.propagation_chunk = propagation_chunk
        if shadow_sync not in {"eager", "candidate", "deferred"}:
            raise ValueError(f"unknown CaDiCaL shadow synchronization mode: {shadow_sync}")
        self.shadow_sync = shadow_sync
        self.pool = IDPool(start_from=self.m * self.m + 1)
        self.solver = Solver(name=solver_name, use_timer=True)
        self.cuts = set()
        self.clauses = 0
        self.formula_clauses = [] if retain_formula else None
        self.preprocessing = None
        self.proof_mode = False
        self.proof_solver = None
        self.cadical_shadow = None
        self.cadical_shadow_temporary = None
        self.shadow_synced_clauses = 0
        self._add_degree_constraints()

    def variable(self, row, column):
        return row * self.m + column + 1

    def add_clause(self, clause):
        clause = list(clause)
        self.solver.add_clause(clause)
        if self.formula_clauses is not None:
            self.formula_clauses.append(clause)
        if self.cadical_shadow is not None:
            if self.shadow_sync == "eager":
                self.cadical_shadow.add_clauses([clause])
                self.shadow_synced_clauses += 1
        self.clauses += 1

    def add_formula(self, clauses):
        clauses = [list(clause) for clause in clauses]
        self.solver.append_formula(clauses)
        if self.formula_clauses is not None:
            self.formula_clauses.extend(clauses)
        if self.cadical_shadow is not None:
            if self.shadow_sync == "eager":
                self.cadical_shadow.add_clauses(clauses)
                self.shadow_synced_clauses += len(clauses)
        self.clauses += len(clauses)

    def flush_cadical_shadow(self):
        if self.cadical_shadow is None:
            return 0
        pending = len(self.formula_clauses) - self.shadow_synced_clauses
        if pending < 0:
            raise AssertionError("CaDiCaL shadow synchronized past the retained CNF")
        if pending:
            self.cadical_shadow.add_clauses(
                self.formula_clauses[self.shadow_synced_clauses :]
            )
            self.shadow_synced_clauses = len(self.formula_clauses)
        return pending

    def enable_cadical_shadow(self, library):
        if self.formula_clauses is None:
            raise RuntimeError("CaDiCaL shadow requires a retained original CNF")
        if self.cadical_shadow is not None:
            raise RuntimeError("CaDiCaL shadow is already enabled")
        temporary = tempfile.TemporaryDirectory(prefix="rot4-cadical-shadow-")
        shadow = None
        try:
            shadow = CadicalShadow(
                library,
                Path(temporary.name) / "proof.drat",
                factor=True,
            )
            shadow.add_clauses(self.formula_clauses)
        except Exception:
            if shadow is not None:
                shadow.close()
            temporary.cleanup()
            raise
        self.cadical_shadow_temporary = temporary
        self.cadical_shadow = shadow
        self.shadow_synced_clauses = len(self.formula_clauses)
        return {
            "backend": "cadical-library",
            "version": shadow.version,
            "library": shadow.library_path,
            "librarySha256": hashlib.sha256(
                Path(shadow.library_path).read_bytes()
            ).hexdigest(),
            "initialClauses": shadow.clauses,
            "factor": shadow.factor,
            "synchronization": self.shadow_sync,
        }

    def preprocess_sbva(self, executable, seconds):
        resolved = resolve_executable(executable)

        input_variables = self.pool.top
        input_clauses = len(self.formula_clauses)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="rot4-sbva-") as temporary:
            input_path = Path(temporary) / "input.cnf"
            output_path = Path(temporary) / "output.cnf"
            formula = CNF(from_clauses=self.formula_clauses)
            formula.nv = max(formula.nv, input_variables)
            formula.to_file(input_path)
            try:
                completed = subprocess.run(
                    [resolved, "-i", str(input_path), "-o", str(output_path)],
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=max(0.001, seconds),
                )
            except subprocess.TimeoutExpired:
                self.preprocessing = {
                    "backend": "sbva",
                    "executable": resolved,
                    "status": "timeout",
                    "inputVariables": input_variables,
                    "inputClauses": input_clauses,
                    "seconds": round(time.monotonic() - started, 6),
                }
                return False
            if completed.returncode != 0:
                message = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(
                    f"SBVA failed with exit {completed.returncode}: {message}"
                )
            processed = CNF(from_file=output_path)

        if processed.nv < self.m * self.m:
            raise RuntimeError(
                "SBVA output does not preserve the original arc-variable identifier range"
            )
        replacement = Solver(
            name=self.solver_name,
            bootstrap_with=processed.clauses,
            use_timer=True,
        )
        self.solver.delete()
        self.solver = replacement
        self.pool = IDPool(start_from=processed.nv + 1)
        self.clauses = len(processed.clauses)
        self.preprocessing = {
            "backend": "sbva",
            "executable": resolved,
            "status": "ok",
            "inputVariables": input_variables,
            "outputVariables": processed.nv,
            "addedVariables": processed.nv - input_variables,
            "inputClauses": input_clauses,
            "outputClauses": len(processed.clauses),
            "removedClauses": input_clauses - len(processed.clauses),
            "originalFormulaRetained": True,
            "seconds": round(time.monotonic() - started, 6),
        }
        return True

    def restart_for_proof(self, solver_name):
        if self.formula_clauses is None:
            raise RuntimeError("proof restart requires a retained CNF")
        if self.cadical_shadow is not None:
            raise RuntimeError("internal proof restart cannot replace a CaDiCaL shadow")
        replacement = Solver(
            name=solver_name,
            bootstrap_with=self.formula_clauses,
            use_timer=True,
            with_proof=True,
        )
        self.solver.delete()
        self.solver = replacement
        self.solver_name = solver_name
        self.solver_key = solver_name.lower()
        self.clauses = len(self.formula_clauses)
        self.proof_mode = True
        self.proof_solver = solver_name

    def write_unsat_proof(
        self,
        directory,
        fixing_assumptions,
        metadata,
        checker=None,
        checker_seconds=3600.0,
        emit_lrat=False,
        lrat_checker=None,
        lrat_checker_seconds=3600.0,
    ):
        if not self.proof_mode:
            raise RuntimeError("proof output requires a fresh proof-enabled global solver")
        if fixing_assumptions:
            raise ValueError("refusing to emit a global proof with fixing assumptions")
        if emit_lrat and not checker:
            raise ValueError("LRAT conversion requires an external DRAT checker")
        proof = self.solver.get_proof()
        if not proof or proof[-1].strip() != "0":
            raise RuntimeError(
                f"proof solver {self.proof_solver!r} did not emit a complete DRUP trace"
            )

        destination = Path(directory).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            raise FileExistsError(f"proof directory is not empty: {destination}")
        cnf_path = destination / "formula.cnf"
        proof_path = destination / "proof.drup"
        lrat_path = destination / "proof.lrat" if emit_lrat else None
        metadata_path = destination / "metadata.json"

        formula = CNF(from_clauses=self.formula_clauses)
        formula.nv = max(formula.nv, self.pool.top)
        formula.to_file(cnf_path)
        proof_path.write_text("\n".join(proof) + "\n", encoding="ascii")
        artifact = {
            **metadata,
            "status": "global_unsat",
            "proofSolver": self.proof_solver,
            "proofFormat": "DRUP",
            "variables": formula.nv,
            "clauses": len(formula.clauses),
            "proofLines": len(proof),
            "cnf": str(cnf_path),
            "proof": str(proof_path),
            "cnfSha256": hashlib.sha256(cnf_path.read_bytes()).hexdigest(),
            "proofSha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        }
        if checker:
            artifact["externalChecker"] = run_drat_checker(
                checker,
                cnf_path,
                proof_path,
                checker_seconds,
                lrat_path=lrat_path,
            )
        if lrat_path and lrat_path.is_file():
            artifact.update(
                lratFormat="LRAT",
                lrat=str(lrat_path),
                lratSha256=hashlib.sha256(lrat_path.read_bytes()).hexdigest(),
                lratBytes=lrat_path.stat().st_size,
            )
            if lrat_checker and artifact["externalChecker"]["status"] == "verified":
                artifact["lratChecker"] = run_lrat_checker(
                    lrat_checker,
                    cnf_path,
                    lrat_path,
                    lrat_checker_seconds,
                )
        artifact["metadata"] = str(metadata_path)
        metadata_path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if checker and artifact["externalChecker"]["status"] != "verified":
            raise RuntimeError(
                "external proof checking failed; inspect "
                f"{metadata_path} and retain the unverified artifacts"
            )
        if lrat_checker and artifact.get("lratChecker", {}).get("status") != "verified":
            raise RuntimeError(
                "LRAT proof checking failed; inspect "
                f"{metadata_path} and retain the unverified artifacts"
            )
        return artifact

    def write_cadical_proof(
        self,
        directory,
        fixing_assumptions,
        metadata,
        cadical,
        cadical_seconds,
        checker=None,
        checker_seconds=3600.0,
        emit_lrat=False,
        lrat_checker=None,
        lrat_checker_seconds=3600.0,
    ):
        if self.formula_clauses is None:
            raise RuntimeError("external certification requires a retained original CNF")
        if fixing_assumptions:
            raise ValueError("refusing to certify global UNSAT with fixing assumptions")
        if emit_lrat and not checker:
            raise ValueError("LRAT conversion requires an external DRAT checker")

        destination = Path(directory).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            raise FileExistsError(f"proof directory is not empty: {destination}")
        cnf_path = destination / "formula.cnf"
        proof_path = destination / "proof.drat"
        lrat_path = destination / "proof.lrat" if emit_lrat else None
        metadata_path = destination / "metadata.json"

        formula = CNF(from_clauses=self.formula_clauses)
        formula.to_file(cnf_path)
        if self.cadical_shadow is not None:
            self.flush_cadical_shadow()
            producer = self.cadical_shadow.solve(cadical_seconds)
            if self.cadical_shadow.proof_path.is_file():
                shutil.copyfile(self.cadical_shadow.proof_path, proof_path)
        else:
            if not cadical:
                raise ValueError("external CaDiCaL executable is not configured")
            producer = run_cadical_proof(
                cadical,
                cnf_path,
                proof_path,
                cadical_seconds,
            )
        artifact = {
            **metadata,
            "status": (
                "global_unsat"
                if producer["status"] == "unsat"
                else f"certification_{producer['status']}"
            ),
            "proofSolver": producer["backend"],
            "proofFormat": "binary DRAT",
            "proofProducer": producer,
            "variables": formula.nv,
            "clauses": len(formula.clauses),
            "cnf": str(cnf_path),
            "proof": str(proof_path),
            "cnfSha256": hashlib.sha256(cnf_path.read_bytes()).hexdigest(),
        }
        if proof_path.is_file():
            artifact.update(
                proofSha256=hashlib.sha256(proof_path.read_bytes()).hexdigest(),
                proofBytes=proof_path.stat().st_size,
            )
        if producer["status"] == "unsat" and checker:
            artifact["externalChecker"] = run_drat_checker(
                checker,
                cnf_path,
                proof_path,
                checker_seconds,
                lrat_path=lrat_path,
            )
        if lrat_path and lrat_path.is_file():
            artifact.update(
                lratFormat="LRAT",
                lrat=str(lrat_path),
                lratSha256=hashlib.sha256(lrat_path.read_bytes()).hexdigest(),
                lratBytes=lrat_path.stat().st_size,
            )
            if lrat_checker and artifact.get("externalChecker", {}).get("status") == "verified":
                artifact["lratChecker"] = run_lrat_checker(
                    lrat_checker,
                    cnf_path,
                    lrat_path,
                    lrat_checker_seconds,
                )
        artifact["metadata"] = str(metadata_path)
        metadata_path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if producer["status"] != "unsat":
            raise RuntimeError(
                "CaDiCaL did not confirm global UNSAT; inspect "
                f"{metadata_path} and retain the diagnostic artifacts"
            )
        if checker and artifact.get("externalChecker", {}).get("status") != "verified":
            raise RuntimeError(
                "external proof checking failed; inspect "
                f"{metadata_path} and retain the unverified artifacts"
            )
        if lrat_checker and artifact.get("lratChecker", {}).get("status") != "verified":
            raise RuntimeError(
                "LRAT proof checking failed; inspect "
                f"{metadata_path} and retain the unverified artifacts"
            )
        return artifact

    def add_atmost_two(self, literals):
        if len(literals) <= 2:
            return
        if len(literals) <= self.direct_threshold:
            for triple in combinations(literals, 3):
                self.add_clause([-literal for literal in triple])
            return
        encoded = CardEnc.atmost(
            lits=literals,
            bound=2,
            vpool=self.pool,
            encoding=EncType.seqcounter,
        )
        self.add_formula(encoded.clauses)

    def _add_degree_constraints(self):
        for vertex in range(self.m):
            loop = self.variable(vertex, vertex)
            incident = [
                self.variable(vertex, other) for other in range(self.m) if other != vertex
            ]
            incident.extend(
                self.variable(other, vertex) for other in range(self.m) if other != vertex
            )
            self.add_atmost_two(incident)
            at_least_two = CardEnc.atleast(
                lits=incident,
                bound=2,
                vpool=self.pool,
                encoding=EncType.seqcounter,
            )
            for clause in at_least_two.clauses:
                self.add_clause([loop, *clause])
            for literal in incident:
                self.add_clause([-loop, -literal])

    def add_line_cut(self, key):
        coefficients = line_coefficients(self.n, key)
        incidence = tuple(
            sorted(
                (row, column, coefficient)
                for (row, column), coefficient in coefficients.items()
            )
        )
        if incidence in self.cuts:
            return False
        self.cuts.add(incidence)

        singles = []
        doubled = []
        for (row, column), coefficient in coefficients.items():
            literal = self.variable(row, column)
            if coefficient == 1:
                singles.append(literal)
            elif coefficient == 2:
                doubled.append(literal)
            else:
                self.add_clause([-literal])
        self.add_atmost_two(singles)
        for doubled_literal in doubled:
            for single_literal in singles:
                self.add_clause([-doubled_literal, -single_literal])
        for first, second in combinations(doubled, 2):
            self.add_clause([-first, -second])
        return True

    def add_line_cuts(self, keys):
        added = sum(self.add_line_cut(key) for key in keys)
        if self.shadow_sync == "candidate":
            self.flush_cadical_shadow()
        return added

    def assumptions(self, incumbent, free):
        selected = set(incumbent)
        return [
            self.variable(row, column)
            if (row, column) in selected
            else -self.variable(row, column)
            for row in range(self.m)
            for column in range(self.m)
            if row not in free and column not in free
        ]

    def solve(self, assumptions, seconds):
        deadline = time.monotonic() + seconds
        try:
            try:
                self.solver.prop_budget(self.propagation_chunk)
                propagation_budget_supported = True
            except NotImplementedError:
                propagation_budget_supported = False
            while time.monotonic() < deadline:
                self.solver.conf_budget(self.conflict_chunk)
                if propagation_budget_supported:
                    self.solver.prop_budget(self.propagation_chunk)
                result = self.solver.solve_limited(assumptions=assumptions)
                if result is not None:
                    return result
            return None
        except NotImplementedError:
            pass

        remaining = max(0.001, deadline - time.monotonic())
        timer = threading.Timer(remaining, self.solver.interrupt)
        timer.daemon = True
        timer.start()
        try:
            result = self.solver.solve_limited(
                assumptions=assumptions,
                expect_interrupt=True,
            )
        finally:
            timer.cancel()
            self.solver.clear_interrupt()
        return result

    def model_arcs(self):
        positive = {literal for literal in self.solver.get_model() if literal > 0}
        return [
            (row, column)
            for row in range(self.m)
            for column in range(self.m)
            if self.variable(row, column) in positive
        ]

    def expand_from_core(self, free, count, randomizer, policy="score"):
        core = self.solver.get_core() or []
        chosen, metadata = choose_core_vertices(
            core,
            self.m,
            free,
            count,
            randomizer,
            policy,
        )
        free.update(chosen)
        return metadata, chosen

    def statistics(self):
        result = self.solver.accum_stats()
        statistics = {
            "restarts": result.get("restarts"),
            "conflicts": result.get("conflicts"),
            "decisions": result.get("decisions"),
            "propagations": result.get("propagations"),
            "satSeconds": self.solver.time_accum(),
        }
        if self.cadical_shadow is not None:
            statistics["proofShadow"] = {
                **self.cadical_shadow.statistics(),
                "synchronization": self.shadow_sync,
                "pendingClauses": len(self.formula_clauses)
                - self.shadow_synced_clauses,
            }
        return statistics

    def close(self):
        if self.cadical_shadow is not None:
            self.cadical_shadow.close()
            self.cadical_shadow = None
        if self.cadical_shadow_temporary is not None:
            self.cadical_shadow_temporary.cleanup()
            self.cadical_shadow_temporary = None
        self.solver.delete()


def repair(arguments):
    deadline = time.monotonic() + arguments.seconds
    n = arguments.n
    m = n // 2
    incumbent = arcs_from_code(arguments.incumbent, n)
    details, initial_triples = selected_line_data(n, incumbent)
    if not details:
        return {
            "backend": "sat",
            "solver": arguments.solver,
            "active_solver": arguments.solver,
            "status": "sat",
            "initial_bad_lines": 0,
            "initial_triples": 0,
            "best_bad_lines": 0,
            "best_triples": 0,
            "code": arguments.incumbent,
            "proof": None,
            "proof_shadow": None,
        }

    if arguments.split_rng_streams:
        initial_randomizer = random.Random(arguments.seed ^ 0x13579BDF)
        halo_randomizer = random.Random(arguments.seed ^ 0x6C8E9CF1)
        core_randomizer = random.Random(arguments.seed ^ 0x2468ACE0)
        cut_randomizer = random.Random(arguments.seed ^ 0x5A17C0DE)
        rng_streams = "split-cover-halo-core-cut"
    else:
        initial_randomizer = random.Random(arguments.seed)
        halo_randomizer = initial_randomizer
        core_randomizer = initial_randomizer
        cut_randomizer = initial_randomizer
        rng_streams = "legacy-shared"
    minimum = max(arguments.core_vertices, math.ceil(arguments.free_fraction * m))
    free, initial_neighborhood = choose_free_vertices(
        n,
        incumbent,
        details,
        min(m, minimum),
        arguments.halo_vertices,
        initial_randomizer,
        policy=arguments.initial_cover_policy,
        return_metadata=True,
        halo_randomizer=halo_randomizer,
    )
    initial_free = len(free)
    engine = FactorSat(
        n,
        arguments.solver,
        arguments.direct_threshold,
        arguments.conflict_chunk,
        arguments.propagation_chunk,
        retain_formula=bool(arguments.sbva or arguments.proof_dir),
        shadow_sync=arguments.proof_shadow_sync,
    )

    best_arcs = incumbent
    best_bad_lines = len(details)
    best_triples = initial_triples
    candidates = 0
    calls = 0
    expansions = []
    status = "timeout"
    proof_artifact = None
    proof_shadow = None
    try:
        engine.add_line_cuts(key for key, _arc_ids in details)
        if arguments.proof_cadical_library:
            proof_shadow = engine.enable_cadical_shadow(
                arguments.proof_cadical_library
            )
        if arguments.sbva:
            engine.preprocess_sbva(
                arguments.sbva,
                max(0.001, deadline - time.monotonic()),
            )
        while time.monotonic() < deadline:
            if (
                len(free) == m
                and arguments.proof_dir
                and not arguments.proof_cadical
                and not arguments.proof_cadical_library
                and not engine.proof_mode
            ):
                engine.restart_for_proof(arguments.proof_solver)
            remaining = max(0.001, deadline - time.monotonic())
            assumptions = engine.assumptions(incumbent, free)
            solved = engine.solve(assumptions, remaining)
            calls += 1
            if solved is None:
                status = "timeout"
                break
            if solved is False:
                if len(free) == m:
                    status = "unsat"
                    if arguments.proof_dir:
                        proof_metadata = {
                            "n": n,
                            "primarySolver": arguments.solver,
                            "seed": arguments.seed,
                            "cuts": len(engine.cuts),
                            "fixingAssumptions": 0,
                            "initialNeighborhood": initial_neighborhood,
                            "coreExpansionPolicy": arguments.core_expansion_policy,
                            "rngStreams": rng_streams,
                            "searchPreprocessing": engine.preprocessing,
                            "proofShadow": proof_shadow,
                        }
                        if arguments.proof_cadical or arguments.proof_cadical_library:
                            proof_artifact = engine.write_cadical_proof(
                                arguments.proof_dir,
                                assumptions,
                                proof_metadata,
                                arguments.proof_cadical,
                                arguments.proof_cadical_seconds,
                                checker=arguments.proof_checker,
                                checker_seconds=arguments.proof_check_seconds,
                                emit_lrat=arguments.proof_lrat,
                                lrat_checker=arguments.lrat_checker,
                                lrat_checker_seconds=arguments.lrat_check_seconds,
                            )
                        else:
                            proof_artifact = engine.write_unsat_proof(
                                arguments.proof_dir,
                                assumptions,
                                proof_metadata,
                                checker=arguments.proof_checker,
                                checker_seconds=arguments.proof_check_seconds,
                                emit_lrat=arguments.proof_lrat,
                                lrat_checker=arguments.lrat_checker,
                                lrat_checker_seconds=arguments.lrat_check_seconds,
                            )
                    break
                if arguments.expand_by == 0:
                    status = "unsat_neighborhood"
                    break
                core_metadata, added_vertices = engine.expand_from_core(
                    free,
                    min(arguments.expand_by, m - len(free)),
                    core_randomizer,
                    policy=arguments.core_expansion_policy,
                )
                expansions.append(
                    {
                        **core_metadata,
                        "addedVertices": added_vertices,
                        "freeVertices": len(free),
                    }
                )
                continue

            arcs = engine.model_arcs()
            candidates += 1
            candidate_details, triples = selected_line_data(n, arcs)
            bad_lines = len(candidate_details)
            if (triples, bad_lines) < (best_triples, best_bad_lines):
                best_arcs = arcs
                best_bad_lines = bad_lines
                best_triples = triples
            if not candidate_details:
                return {
                    "backend": "sat",
                    "solver": arguments.solver,
                    "active_solver": engine.solver_name,
                    "status": "sat",
                    "calls": calls,
                    "candidates": candidates,
                    "cuts": len(engine.cuts),
                    "clauses": engine.clauses,
                    "variables": engine.pool.top,
                    "preprocessing": engine.preprocessing,
                    "initial_free_vertices": initial_free,
                    "initial_neighborhood": initial_neighborhood,
                    "core_expansion_policy": arguments.core_expansion_policy,
                    "rng_streams": rng_streams,
                    "free_vertices": len(free),
                    "expansions": expansions,
                    "initial_bad_lines": len(details),
                    "initial_triples": initial_triples,
                    "best_bad_lines": 0,
                    "best_triples": 0,
                    "code": compact_code(n, arcs),
                    "proof": None,
                    "proof_shadow": proof_shadow,
                    "statistics": engine.statistics(),
                }
            keys = [key for key, _arc_ids in candidate_details]
            cut_randomizer.shuffle(keys)
            if engine.add_line_cuts(keys) == 0:
                raise AssertionError("a violating SAT model produced no new line cut")

        return {
            "backend": "sat",
            "solver": arguments.solver,
            "active_solver": engine.solver_name,
            "status": status,
            "calls": calls,
            "candidates": candidates,
            "cuts": len(engine.cuts),
            "clauses": engine.clauses,
            "variables": engine.pool.top,
            "preprocessing": engine.preprocessing,
            "initial_free_vertices": initial_free,
            "initial_neighborhood": initial_neighborhood,
            "core_expansion_policy": arguments.core_expansion_policy,
            "rng_streams": rng_streams,
            "free_vertices": len(free),
            "expansions": expansions,
            "initial_bad_lines": len(details),
            "initial_triples": initial_triples,
            "best_bad_lines": best_bad_lines,
            "best_triples": best_triples,
            "best_code": compact_code(n, best_arcs),
            "proof": proof_artifact,
            "proof_shadow": proof_shadow,
            "statistics": engine.statistics(),
        }
    finally:
        engine.close()


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int)
    parser.add_argument("--incumbent", required=True)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--solver", default="cadical195")
    parser.add_argument(
        "--proof-shadow-sync",
        choices=("eager", "candidate", "deferred"),
        default="deferred",
        help=(
            "synchronize later cuts with an in-process proof shadow per clause, "
            "per SAT candidate, or once at the proof boundary"
        ),
    )
    parser.add_argument(
        "--proof-dir",
        type=Path,
        help="write CNF, proof trace, and metadata after globally unfixed UNSAT",
    )
    parser.add_argument(
        "--proof-solver",
        default="glucose42",
        help="proof-capable solver used after all fixing assumptions are removed",
    )
    parser.add_argument(
        "--proof-cadical",
        nargs="?",
        const="cadical",
        help=(
            "independently re-solve the retained original CNF with proof-producing "
            "CaDiCaL (PATH defaults to cadical in PATH)"
        ),
    )
    parser.add_argument(
        "--proof-cadical-library",
        help=(
            "keep the retained original CNF in an in-process proof-tracing "
            "CaDiCaL bridge library"
        ),
    )
    parser.add_argument(
        "--proof-cadical-seconds",
        type=float,
        default=3600.0,
        help="CaDiCaL certification time limit",
    )
    parser.add_argument(
        "--proof-checker",
        nargs="?",
        const="drat-trim",
        help="verify emitted proofs with drat-trim (PATH defaults to drat-trim in PATH)",
    )
    parser.add_argument(
        "--proof-check-seconds",
        type=float,
        default=3600.0,
        help="external proof-checker time limit",
    )
    parser.add_argument(
        "--proof-lrat",
        action="store_true",
        help="ask drat-trim to emit an LRAT certificate alongside DRAT/DRUP",
    )
    parser.add_argument(
        "--lrat-checker",
        nargs="?",
        const="lrat-check",
        help="verify emitted LRAT (PATH defaults to lrat-check in PATH)",
    )
    parser.add_argument(
        "--lrat-check-seconds",
        type=float,
        default=3600.0,
        help="LRAT checker time limit",
    )
    parser.add_argument(
        "--sbva",
        nargs="?",
        const="sbva",
        help="optionally preprocess the initial CNF with SBVA (PATH defaults to sbva in PATH)",
    )
    parser.add_argument("--core-vertices", type=int, default=6)
    parser.add_argument("--halo-vertices", type=int, default=2)
    parser.add_argument("--free-fraction", type=float, default=0.15)
    parser.add_argument("--expand-by", type=int, default=2)
    parser.add_argument(
        "--initial-cover-policy",
        choices=("greedy", "greedy-conflict", "greedy-random", "minimum"),
        default="greedy",
        help="policy for hitting every initially violated line with free vertices",
    )
    parser.add_argument(
        "--core-expansion-policy",
        choices=("score", "marginal", "random"),
        default="score",
        help="policy for choosing vertices after an UNSAT neighborhood core",
    )
    parser.add_argument(
        "--split-rng-streams",
        action="store_true",
        help=(
            "isolate initial-cover, core-expansion, and lazy-cut random choices "
            "for matched policy experiments"
        ),
    )
    parser.add_argument(
        "--direct-threshold",
        type=int,
        default=6,
        help="largest at-most-two constraint expanded directly into ternary clauses",
    )
    parser.add_argument(
        "--conflict-chunk",
        type=int,
        default=1_000,
        help="conflicts between wall-clock deadline checks",
    )
    parser.add_argument(
        "--propagation-chunk",
        type=int,
        default=1_000_000,
        help="propagations between wall-clock deadline checks when supported",
    )
    arguments = parser.parse_args()
    if arguments.n < 6 or arguments.n > 90 or arguments.n % 2:
        parser.error("n must be even and between 6 and 90")
    if arguments.seconds <= 0:
        parser.error("--seconds must be positive")
    if min(arguments.core_vertices, arguments.halo_vertices, arguments.expand_by) < 0:
        parser.error("repair neighborhood sizes must be nonnegative")
    if not 0 <= arguments.free_fraction <= 1:
        parser.error("--free-fraction must be between zero and one")
    if arguments.direct_threshold < 3:
        parser.error("--direct-threshold must be at least three")
    if arguments.conflict_chunk < 1:
        parser.error("--conflict-chunk must be positive")
    if arguments.propagation_chunk < 1:
        parser.error("--propagation-chunk must be positive")
    if arguments.proof_cadical and not arguments.proof_dir:
        parser.error("--proof-cadical requires --proof-dir")
    if arguments.proof_cadical_library and not arguments.proof_dir:
        parser.error("--proof-cadical-library requires --proof-dir")
    if arguments.proof_cadical and arguments.proof_cadical_library:
        parser.error("--proof-cadical and --proof-cadical-library are mutually exclusive")
    if arguments.proof_cadical_seconds <= 0:
        parser.error("--proof-cadical-seconds must be positive")
    if arguments.proof_checker and not arguments.proof_dir:
        parser.error("--proof-checker requires --proof-dir")
    if arguments.proof_check_seconds <= 0:
        parser.error("--proof-check-seconds must be positive")
    if arguments.proof_lrat and not arguments.proof_checker:
        parser.error("--proof-lrat requires --proof-checker")
    if arguments.lrat_checker and not arguments.proof_lrat:
        parser.error("--lrat-checker requires --proof-lrat")
    if arguments.lrat_check_seconds <= 0:
        parser.error("--lrat-check-seconds must be positive")
    return arguments


def main():
    arguments = parse_arguments()
    started = time.monotonic()
    result = repair(arguments)
    result.update(n=arguments.n, seconds=round(time.monotonic() - started, 3), seed=arguments.seed)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
