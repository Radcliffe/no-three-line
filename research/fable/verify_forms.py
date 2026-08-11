#!/usr/bin/env python3
"""Verify the arithmetic reformulation of family violations.

Claim: let sigma be an involution model config (pairs {i,j}, sigma(i)=j, plus
optional fixed point f), a_t = 2i-1, b_t = 2j-1 (a<b), fixed g0 = 2f-1.
For a primitive direction (dx,dy), dy>=0... consider the line functional
c(x,y) = dy*x - dx*y. The 8 points of pair-orbit t give c-values
  { s1*(dy*b_t) - s2*(dx*a_t) } and { s1*(dy*a_t) - s2*(dx*b_t) }, s1,s2 in {+-1}
i.e. the multiset { +-(dy*b - dx*a), +-(dy*b + dx*a), +-(dy*a - dx*b), +-(dy*a + dx*b) }.
The fixed orbit gives { +-(dy*g0 - dx*g0), +-(dy*g0 + dx*g0) }.
A line of this family with value c violates iff the total multiset multiplicity
of c is >= 3.  Number of violating lines of the family = # values with mult>=3.

We check this against direct geometry for random Lemma-S survivors.
"""
import random, sys
from math import gcd
from collections import Counter

def rand_survivor(m):
    """Random leaf of the Lemma-S survivor tree via randomized backtracking DFS."""
    def rec(free, labs, fx, pairs):
        if not free:
            return pairs, fx
        i = free[0]
        opts = []
        if m % 2 and fx is None and (2*i-1) not in labs:
            opts.append(None)
        for j in free[1:]:
            d, s = j-i, i+j-1
            if d != s and d not in labs and s not in labs:
                opts.append(j)
        random.shuffle(opts)
        for o in opts:
            if o is None:
                r = rec(free[1:], labs | {2*i-1}, i, pairs)
            else:
                r = rec([x for x in free[1:] if x != o],
                        labs | {o-i, i+o-1}, fx, pairs + [(i,o)])
            if r: return r
        return None
    r = rec(list(range(1, m+1)), set(), None, [])
    if not r: raise RuntimeError("no survivor found")
    return r

def points(pairs, fx):
    pts = []
    if fx:
        g0 = 2*fx-1
        pts += [(s1*g0, s2*g0) for s1 in (1,-1) for s2 in (1,-1)]
    for i, j in pairs:
        a, b = 2*i-1, 2*j-1
        for s1 in (1,-1):
            for s2 in (1,-1):
                pts.append((s1*b, s2*a)); pts.append((s1*a, s2*b))
    return pts

def geometric_family_viol(pts, dx, dy):
    """# lines with direction (dx,dy) containing >=3 points."""
    cnt = Counter()
    for (x, y) in pts:
        cnt[dy*x - dx*y] += 1
    return sum(1 for v in cnt.values() if v >= 3)

def form_family_viol(pairs, fx, dx, dy):
    cnt = Counter()
    for i, j in pairs:
        a, b = 2*i-1, 2*j-1
        for v in (dy*b - dx*a, dy*b + dx*a, dy*a - dx*b, dy*a + dx*b):
            cnt[v] += 1; cnt[-v] += 1
    if fx:
        g0 = 2*fx-1
        for v in (dy*g0 - dx*g0, dy*g0 + dx*g0):
            cnt[v] += 1; cnt[-v] += 1
    # The +-v increments model the 8 points of the orbit exactly (the point set is
    # centrally symmetric); a form value v=0 correctly adds 2 to cnt[0], because both
    # points of that +- pair lie on the central line c=0. No special-casing needed.
    return sum(1 for v in cnt.values() if v >= 3)

def main():
    random.seed(12345)
    fams = [(1,2),(2,1),(1,-2),(1,3),(3,1),(2,3),(3,-2),(1,4),(3,4),(2,5),(5,6),(1,6)]
    bad = 0; total = 0
    for m in [8, 11, 14, 17, 20, 23, 26]:
        for trial in range(30):
            pairs, fx = rand_survivor(m)
            pts = points(pairs, fx)
            assert len(pts) == 4*m and len(set(pts)) == 4*m
            for (p, q) in fams:
                g = gcd(abs(p), abs(q));  dx, dy = p//g, q//g
                gv = geometric_family_viol(pts, dx, dy)
                fv = form_family_viol(pairs, fx, dx, dy)
                total += 1
                if gv != fv:
                    bad += 1
                    if bad < 5:
                        print(f"MISMATCH m={m} fam=({dx},{dy}) geo={gv} form={fv} pairs={pairs} fx={fx}")
    print(f"checked {total} (m,config,family) cases: mismatches={bad}")

main()
