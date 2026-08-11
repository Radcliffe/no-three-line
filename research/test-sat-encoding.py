#!/usr/bin/env python3
"""Exhaustively check the native SAT encodings on the 3-vertex quotient."""

import importlib.util
import itertools
import json
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path


sys.dont_write_bytecode = True


def load_backend():
    filename = Path(__file__).with_name("rot4-sat-repair.py")
    spec = importlib.util.spec_from_file_location("rot4_sat_repair", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_checker():
    filename = Path(__file__).with_name("check-unsat-trace.py")
    spec = importlib.util.spec_from_file_location("check_unsat_trace", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def degree_equations(bits, m):
    return all(
        2 * bits[vertex * m + vertex]
        + sum(bits[vertex * m + other] for other in range(m) if other != vertex)
        + sum(bits[other * m + vertex] for other in range(m) if other != vertex)
        == 2
        for vertex in range(m)
    )


def satisfies_cut(bits, m, coefficients):
    return (
        sum(
            coefficient * bits[row * m + column]
            for (row, column), coefficient in coefficients.items()
        )
        <= 2
    )


def brute_line_coefficients(module, n, key):
    a, b, c = key
    coefficients = {}
    for row in range(n):
        for column in range(n):
            if a * column + b * row + c != 0:
                continue
            representative = module.representative(n, row, column)
            coefficients[representative] = coefficients.get(representative, 0) + 1
    return coefficients


def check_line_enumeration(module):
    n = 8
    points = [(row, column) for row in range(n) for column in range(n)]
    keys = {
        module.canonical_line(first, second)
        for index, first in enumerate(points)
        for second in points[index + 1 :]
    }
    for key in keys:
        actual = module.line_coefficients(n, key)
        expected = brute_line_coefficients(module, n, key)
        if actual != expected:
            raise AssertionError({"key": key, "actual": actual, "expected": expected})
    return len(keys)


class RecordingShadow:
    def __init__(self):
        self.clauses = 0
        self.calls = 0

    def add_clauses(self, clauses):
        clauses = list(clauses)
        self.clauses += len(clauses)
        self.calls += bool(clauses)

    def statistics(self):
        return {"clauses": self.clauses, "addCalls": self.calls}

    def close(self):
        pass


def check_shadow_synchronization(module):
    keys = [
        module.canonical_line((0, 0), (1, 1)),
        module.canonical_line((0, 1), (2, 2)),
    ]
    results = {}
    formulas = []
    for mode in ("eager", "candidate", "deferred"):
        engine = module.FactorSat(
            6,
            "cadical195",
            6,
            retain_formula=True,
            shadow_sync=mode,
        )
        shadow = RecordingShadow()
        engine.cadical_shadow = shadow
        engine.shadow_synced_clauses = len(engine.formula_clauses)
        initial_clauses = len(engine.formula_clauses)
        engine.add_line_cuts(keys)
        added_clauses = len(engine.formula_clauses) - initial_clauses
        calls_before_flush = shadow.calls
        pending_before_flush = len(engine.formula_clauses) - engine.shadow_synced_clauses
        flushed = engine.flush_cadical_shadow()
        if shadow.clauses != added_clauses:
            raise AssertionError(f"{mode} shadow missed retained clauses")
        if engine.shadow_synced_clauses != len(engine.formula_clauses):
            raise AssertionError(f"{mode} shadow cursor did not reach the CNF boundary")
        results[mode] = {
            "addedClauses": added_clauses,
            "callsBeforeFlush": calls_before_flush,
            "pendingBeforeFlush": pending_before_flush,
            "flushedClauses": flushed,
            "totalCalls": shadow.calls,
        }
        formulas.append(engine.formula_clauses)
        engine.close()

    if not all(formula == formulas[0] for formula in formulas[1:]):
        raise AssertionError("shadow synchronization mode changed the retained CNF")
    if results["eager"]["callsBeforeFlush"] <= 1:
        raise AssertionError("eager shadow test did not exercise per-clause calls")
    if results["candidate"]["callsBeforeFlush"] != 1:
        raise AssertionError("candidate shadow did not batch the cut group")
    if results["deferred"]["callsBeforeFlush"] != 0:
        raise AssertionError("deferred shadow synchronized before the explicit flush")
    if results["deferred"]["totalCalls"] != 1:
        raise AssertionError("deferred shadow did not use exactly one final batch")
    return results


def check_neighborhood_policies(module):
    incumbent = "oHM9HBQ2GAM5O8A04DNFSNPFR013L9BIK8QST2E461E6GPTJL5O7JDR3ICK7C"
    n = 30
    arcs = module.arcs_from_code(incumbent, n)
    details, energy = module.selected_line_data(n, arcs)
    if energy != 20:
        raise AssertionError(f"neighborhood regression energy changed to {energy}")

    policies = {}
    for policy in ("greedy", "greedy-conflict", "greedy-random", "minimum"):
        free, metadata = module.choose_free_vertices(
            n,
            arcs,
            details,
            minimum=4,
            halo=1,
            randomizer=random.Random(30),
            policy=policy,
            return_metadata=True,
        )
        for _key, arc_ids in details:
            vertices = {
                vertex for arc_id in arc_ids for vertex in arcs[arc_id]
            }
            if free.isdisjoint(vertices):
                raise AssertionError(f"{policy} left a violated line fixed")
        if len(free) != max(4, metadata["coverSize"]) + 1:
            raise AssertionError(f"{policy} neighborhood size metadata is inconsistent")
        policies[policy] = metadata

    m = 8
    core_arcs = [
        (0, 1),
        (1, 0),
        (0, 2),
        (0, 3),
        (1, 2),
        (1, 3),
        (4, 5),
        (4, 6),
        (4, 7),
    ]
    core = [row * m + column + 1 for row, column in core_arcs]
    score, score_metadata = module.choose_core_vertices(
        core,
        m,
        set(),
        2,
        random.Random(1),
        "score",
    )
    marginal, marginal_metadata = module.choose_core_vertices(
        core,
        m,
        set(),
        2,
        random.Random(1),
        "marginal",
    )
    if marginal_metadata["coveredArcAssumptions"] <= score_metadata[
        "coveredArcAssumptions"
    ]:
        raise AssertionError(
            {"score": score, "marginal": marginal, "core": core_arcs}
        )
    return {
        "initial": policies,
        "core": {
            "score": {"vertices": score, **score_metadata},
            "marginal": {"vertices": marginal, **marginal_metadata},
        },
    }


def check(module, keys, sbva=None):
    n = 6
    m = n // 2
    engine = module.FactorSat(n, "cadical195", 6, retain_formula=bool(sbva))
    coefficients = [module.line_coefficients(n, key) for key in keys]
    engine.add_line_cuts(keys)
    if sbva:
        engine.preprocess_sbva(sbva, 5.0)
    assignments = 0
    for bits in itertools.product((False, True), repeat=m * m):
        assumptions = [index + 1 if bit else -(index + 1) for index, bit in enumerate(bits)]
        actual = engine.solver.solve(assumptions=assumptions)
        expected = degree_equations(bits, m) and all(
            satisfies_cut(bits, m, line) for line in coefficients
        )
        if actual != expected:
            raise AssertionError(
                {"bits": bits, "actual": actual, "expected": expected, "cuts": coefficients}
            )
        assignments += 1
    engine.close()
    return assignments, coefficients


def check_proof_artifact(module):
    from pysat.examples.genhard import PHP

    checker = load_checker()
    engine = module.FactorSat(6, "cadical195", 6, retain_formula=True)
    offset = engine.pool.top
    pigeonhole = PHP(nof_holes=3)
    engine.add_formula(
        [
            [literal + offset if literal > 0 else literal - offset for literal in clause]
            for clause in pigeonhole.clauses
        ]
    )
    sbva = shutil.which("sbva")
    retained_before_sbva = len(engine.formula_clauses)
    if sbva:
        engine.preprocess_sbva(sbva, 5.0)
        if len(engine.formula_clauses) != retained_before_sbva:
            raise AssertionError("SBVA changed the retained proof formula")
    engine.restart_for_proof("glucose42")
    if engine.solve([], 5.0) is not False:
        raise AssertionError("proof test formula unexpectedly satisfiable")
    try:
        engine.write_unsat_proof(Path(tempfile.gettempdir()) / "refused-proof", [1], {})
    except ValueError:
        refused_assumptions = True
    else:
        refused_assumptions = False
    if not refused_assumptions:
        raise AssertionError("proof output accepted a fixing assumption")

    external_checker = os.environ.get("DRAT_TRIM") or shutil.which("drat-trim")
    lrat_checker = os.environ.get("LRAT_CHECK") or shutil.which("lrat-check")
    with tempfile.TemporaryDirectory(prefix="rot4-proof-test-") as temporary:
        artifact = engine.write_unsat_proof(
            Path(temporary) / "proof",
            [],
            {"n": 6},
            checker=external_checker,
            checker_seconds=5.0,
            emit_lrat=bool(external_checker and lrat_checker),
            lrat_checker=lrat_checker if external_checker else None,
            lrat_checker_seconds=5.0,
        )
        checked = checker.check_trace(artifact["cnf"], artifact["proof"], "cadical195")
        rejected_invalid = None
        rejected_invalid_lrat = None
        if external_checker:
            invalid_path = Path(temporary) / "invalid.drup"
            invalid_path.write_text("1 0\n0\n", encoding="ascii")
            invalid = module.run_drat_checker(
                external_checker,
                artifact["cnf"],
                invalid_path,
                5.0,
            )
            rejected_invalid = invalid["status"] == "failed"
            if not rejected_invalid:
                raise AssertionError("external checker accepted a corrupt proof")
        if external_checker and lrat_checker:
            lrat_lines = Path(artifact["lrat"]).read_text(encoding="ascii").splitlines()
            truncated_lrat = Path(temporary) / "truncated.lrat"
            truncated_lrat.write_text(
                "\n".join(lrat_lines[:-1]) + "\n",
                encoding="ascii",
            )
            invalid_lrat = module.run_lrat_checker(
                lrat_checker,
                artifact["cnf"],
                truncated_lrat,
                5.0,
            )
            rejected_invalid_lrat = invalid_lrat["status"] == "failed"
            if not rejected_invalid_lrat:
                raise AssertionError("LRAT checker accepted a truncated proof")
    engine.close()
    return {
        "proofLines": artifact["proofLines"],
        "sbvaRawRestart": bool(sbva),
        "refusedFixingAssumptions": refused_assumptions,
        "checkedAdditions": checked["additions"],
        "externalVerified": (
            artifact.get("externalChecker", {}).get("status") == "verified"
            if external_checker
            else None
        ),
        "externalRejectedInvalid": rejected_invalid,
        "lratVerified": (
            artifact.get("lratChecker", {}).get("status") == "verified"
            if external_checker and lrat_checker
            else None
        ),
        "lratVerificationMarker": (
            artifact.get("lratChecker", {}).get("verificationMarker")
            if external_checker and lrat_checker
            else None
        ),
        "lratRejectedTruncated": rejected_invalid_lrat,
    }


def check_cadical_artifact(module):
    from pysat.examples.genhard import PHP

    cadical = os.environ.get("CADICAL_PROOF") or shutil.which("cadical")
    external_checker = os.environ.get("DRAT_TRIM") or shutil.which("drat-trim")
    lrat_checker = os.environ.get("LRAT_CHECK") or shutil.which("lrat-check")
    sbva = shutil.which("sbva")
    if not cadical or not external_checker:
        return None

    sat_engine = module.FactorSat(6, "cadical195", 6, retain_formula=True)
    try:
        with tempfile.TemporaryDirectory(prefix="rot4-cadical-sat-test-") as temporary:
            try:
                sat_engine.write_cadical_proof(
                    Path(temporary) / "refused",
                    [1],
                    {"n": 6},
                    cadical,
                    5.0,
                )
            except ValueError:
                refused_assumptions = True
            else:
                refused_assumptions = False
            if not refused_assumptions:
                raise AssertionError("external certification accepted fixing assumptions")

            proof_directory = Path(temporary) / "proof"
            try:
                sat_engine.write_cadical_proof(
                    proof_directory,
                    [],
                    {"n": 6},
                    cadical,
                    5.0,
                )
            except RuntimeError:
                sat_metadata = json.loads(
                    (proof_directory / "metadata.json").read_text(encoding="utf-8")
                )
                rejected_sat = sat_metadata["status"] == "certification_sat"
            else:
                rejected_sat = False
        if not rejected_sat:
            raise AssertionError("external certification accepted a SAT formula")
    finally:
        sat_engine.close()

    engine = module.FactorSat(6, "cadical195", 6, retain_formula=True)
    try:
        offset = engine.pool.top
        pigeonhole = PHP(nof_holes=3)
        engine.add_formula(
            [
                [literal + offset if literal > 0 else literal - offset for literal in clause]
                for clause in pigeonhole.clauses
            ]
        )
        original_clauses = len(engine.formula_clauses)
        if sbva:
            engine.preprocess_sbva(sbva, 5.0)
            if len(engine.formula_clauses) != original_clauses:
                raise AssertionError("SBVA changed the retained original formula")
        if engine.solve([], 5.0) is not False:
            raise AssertionError("preprocessed proof test formula unexpectedly satisfiable")

        with tempfile.TemporaryDirectory(prefix="rot4-cadical-proof-test-") as temporary:
            artifact = engine.write_cadical_proof(
                Path(temporary) / "proof",
                [],
                {"n": 6, "searchPreprocessing": engine.preprocessing},
                cadical,
                5.0,
                checker=external_checker,
                checker_seconds=5.0,
                emit_lrat=bool(lrat_checker),
                lrat_checker=lrat_checker,
                lrat_checker_seconds=5.0,
            )
        return {
            "status": artifact["status"],
            "refusedFixingAssumptions": refused_assumptions,
            "rejectedSatCertification": rejected_sat,
            "cnfSha256": artifact["cnfSha256"],
            "proofBytes": artifact["proofBytes"],
            "proofSha256": artifact["proofSha256"],
            "producerStatus": artifact["proofProducer"]["status"],
            "factorEnabled": artifact["proofProducer"]["factor"],
            "dratVerified": artifact["externalChecker"]["status"] == "verified",
            "lratVerified": (
                artifact.get("lratChecker", {}).get("status") == "verified"
                if lrat_checker
                else None
            ),
            "lratSha256": artifact.get("lratSha256"),
            "lratVerificationMarker": (
                artifact.get("lratChecker", {}).get("verificationMarker")
                if lrat_checker
                else None
            ),
            "sbvaOriginalRetained": (
                engine.preprocessing.get("originalFormulaRetained") is True
                if engine.preprocessing
                else None
            ),
            "originalClauses": original_clauses,
            "searchClauses": engine.clauses,
        }
    finally:
        engine.close()


def check_cadical_library_artifact(module):
    from pysat.examples.genhard import PHP

    library = os.environ.get("CADICAL_LIBRARY")
    external_checker = os.environ.get("DRAT_TRIM") or shutil.which("drat-trim")
    lrat_checker = os.environ.get("LRAT_CHECK") or shutil.which("lrat-check")
    sbva = shutil.which("sbva")
    if not library:
        return None

    with tempfile.TemporaryDirectory(prefix="rot4-library-timeout-test-") as temporary:
        timeout_shadow = module.CadicalShadow(
            library,
            Path(temporary) / "proof.drat",
            factor=True,
        )
        try:
            timeout_shadow.add_clauses(PHP(nof_holes=12).clauses)
            timeout_result = timeout_shadow.solve(0.001)
        finally:
            timeout_shadow.close()
    if timeout_result["status"] != "timeout":
        raise AssertionError("in-process CaDiCaL deadline did not interrupt solving")

    sat_engine = module.FactorSat(6, "cadical195", 6, retain_formula=True)
    try:
        sat_engine.enable_cadical_shadow(library)
        with tempfile.TemporaryDirectory(prefix="rot4-library-sat-test-") as temporary:
            proof_directory = Path(temporary) / "proof"
            try:
                sat_engine.write_cadical_proof(
                    proof_directory,
                    [],
                    {"n": 6},
                    None,
                    5.0,
                )
            except RuntimeError:
                metadata = json.loads(
                    (proof_directory / "metadata.json").read_text(encoding="utf-8")
                )
                rejected_sat = metadata["status"] == "certification_sat"
            else:
                rejected_sat = False
        if not rejected_sat:
            raise AssertionError("in-process certification accepted a SAT formula")
    finally:
        sat_engine.close()

    engine = module.FactorSat(6, "cadical195", 6, retain_formula=True)
    try:
        shadow = engine.enable_cadical_shadow(library)
        offset = engine.pool.top
        pigeonhole = PHP(nof_holes=3)
        engine.add_formula(
            [
                [literal + offset if literal > 0 else literal - offset for literal in clause]
                for clause in pigeonhole.clauses
            ]
        )
        original_clauses = len(engine.formula_clauses)
        pending_before_proof = original_clauses - engine.shadow_synced_clauses
        if pending_before_proof != len(pigeonhole.clauses):
            raise AssertionError("deferred proof shadow did not retain the expected queue")
        if sbva:
            engine.preprocess_sbva(sbva, 5.0)
        if engine.solve([], 5.0) is not False:
            raise AssertionError("in-process proof test formula unexpectedly satisfiable")

        with tempfile.TemporaryDirectory(prefix="rot4-library-proof-test-") as temporary:
            artifact = engine.write_cadical_proof(
                Path(temporary) / "proof",
                [],
                {"n": 6, "proofShadow": shadow},
                None,
                5.0,
                checker=external_checker,
                checker_seconds=5.0,
                emit_lrat=bool(external_checker and lrat_checker),
                lrat_checker=lrat_checker if external_checker else None,
                lrat_checker_seconds=5.0,
            )
        return {
            "status": artifact["status"],
            "backend": artifact["proofProducer"]["backend"],
            "version": artifact["proofProducer"]["version"],
            "proofSeconds": artifact["proofProducer"]["seconds"],
            "proofBytes": artifact["proofBytes"],
            "proofSha256": artifact["proofSha256"],
            "cnfSha256": artifact["cnfSha256"],
            "synchronizedClauses": artifact["proofProducer"]["clauses"],
            "originalClauses": original_clauses,
            "pendingBeforeProof": pending_before_proof,
            "shadowAddCalls": artifact["proofProducer"]["addCalls"],
            "shadowSynchronization": shadow["synchronization"],
            "dratVerified": (
                artifact.get("externalChecker", {}).get("status") == "verified"
                if external_checker
                else None
            ),
            "lratVerified": (
                artifact.get("lratChecker", {}).get("status") == "verified"
                if external_checker and lrat_checker
                else None
            ),
            "lratVerificationMarker": (
                artifact.get("lratChecker", {}).get("verificationMarker")
                if lrat_checker
                else None
            ),
            "rejectedSatCertification": rejected_sat,
            "deadlineStatus": timeout_result["status"],
        }
    finally:
        engine.close()


def main():
    module = load_backend()
    enumerated_lines = check_line_enumeration(module)
    shadow_synchronization = check_shadow_synchronization(module)
    neighborhood_policies = check_neighborhood_policies(module)
    proof = check_proof_artifact(module)
    cadical_proof = check_cadical_artifact(module)
    cadical_library_proof = check_cadical_library_artifact(module)
    if cadical_proof and cadical_library_proof:
        for field in ("cnfSha256", "proofSha256", "proofBytes"):
            if cadical_proof[field] != cadical_library_proof[field]:
                raise AssertionError(
                    f"CaDiCaL command and library artifacts differ in {field}"
                )
    assignments, degree_only = check(module, [])
    _assignments, coefficient_two = check(
        module,
        [module.canonical_line((0, 0), (1, 1))],
    )
    _assignments, ternary = check(
        module,
        [module.canonical_line((0, 1), (2, 2))],
    )
    sbva = shutil.which("sbva")
    sbva_assignments = None
    if sbva:
        sbva_assignments, _cuts = check(
            module,
            [
                module.canonical_line((0, 0), (1, 1)),
                module.canonical_line((0, 1), (2, 2)),
            ],
            sbva,
        )
    print(
        json.dumps(
            {
                "assignments": assignments,
                "enumeratedLines": enumerated_lines,
                "shadowSynchronization": shadow_synchronization,
                "neighborhoodPolicies": neighborhood_policies,
                "proof": proof,
                "cadicalProof": cadical_proof,
                "cadicalLibraryProof": cadical_library_proof,
                "sbvaAssignments": sbva_assignments,
                "degreeOnlyCuts": degree_only,
                "coefficientTwoCut": [
                    [[row, column, value] for (row, column), value in sorted(line.items())]
                    for line in coefficient_two
                ],
                "ternaryCut": [
                    [[row, column, value] for (row, column), value in sorted(line.items())]
                    for line in ternary
                ],
                "status": "ok",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
