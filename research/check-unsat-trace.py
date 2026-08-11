#!/usr/bin/env python3
"""Semantically verify every addition in a DRUP trace with an independent SAT call."""

import argparse
import json
from pathlib import Path

try:
    from pysat.formula import CNF
    from pysat.solvers import Solver
except ImportError as error:
    raise SystemExit(
        "PySAT is required. Install the research dependencies with "
        "`python -m pip install -r research/requirements.txt`."
    ) from error


def parse_proof(path):
    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="ascii").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("c"):
            continue
        deleting = line.startswith("d ")
        fields = line[2:].split() if deleting else line.split()
        try:
            values = [int(field) for field in fields]
        except ValueError as error:
            raise ValueError(f"invalid proof integer on line {line_number}") from error
        if not values or values[-1] != 0:
            raise ValueError(f"proof line {line_number} does not end in zero")
        yield line_number, deleting, values[:-1]


def check_trace(cnf_path, proof_path, solver_name="cadical195"):
    formula = CNF(from_file=cnf_path)
    additions = 0
    deletions = 0
    derived_empty = False
    with Solver(name=solver_name, bootstrap_with=formula.clauses) as checker:
        for line_number, deleting, clause in parse_proof(proof_path):
            if deleting:
                # Retaining deletions is sound: every accepted addition remains
                # implied by the stronger set of original and derived clauses.
                deletions += 1
                continue
            literals = set(clause)
            if any(-literal in literals for literal in literals):
                additions += 1
                continue
            normalized = sorted(literals, key=lambda literal: (abs(literal), literal))
            if checker.solve(assumptions=[-literal for literal in normalized]) is not False:
                raise ValueError(f"proof addition on line {line_number} is not implied")
            checker.add_clause(normalized)
            additions += 1
            if not normalized:
                derived_empty = True
        if not derived_empty:
            raise ValueError("proof does not derive the empty clause")

    return {
        "valid": True,
        "checker": solver_name,
        "variables": formula.nv,
        "initialClauses": len(formula.clauses),
        "additions": additions,
        "ignoredDeletions": deletions,
        "derivedEmpty": derived_empty,
    }


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cnf", type=Path)
    parser.add_argument("proof", type=Path)
    parser.add_argument("--solver", default="cadical195")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    result = check_trace(arguments.cnf, arguments.proof, arguments.solver)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
