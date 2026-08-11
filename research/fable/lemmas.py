"""
Structural necessary conditions on the involution, derived from special line families.

Lemma S (slope ±1 lines):
  Each pair orbit {i,j} (i<j) puts 2 points on each line x-y = ±2(j-i) and
  2 points on each line x-y = ±2(i+j-1); a fixed orbit {i} puts 1 point on
  x-y = ±2(2i-1) and 2 points on x-y=0.
  So the label multiset  L = {j-i : pairs} ∪ {i+j-1 : pairs} ∪ {2i-1 : fixed}
  must have ALL DISTINCT elements (any repeat -> >=3 points on a slope-1 line,
  except fixed-label collisions which give 1+1=2... careful: two fixed impossible).
  Wait: two labels equal v means the line x-y=2v carries 2+2=4 or 2+1=3 points -> bad,
  EXCEPT if both contributions are single points (two fixed orbits), which can't happen.
  Hence: all m labels distinct, values in {1,...,2m-2} (fixed label 2i-1 <= 2m-1).

Lemma R (lines through the center):
  Orbit {i,j} puts 2 points on each central line of slope ±(2i-1)/(2j-1) and
  ±(2j-1)/(2i-1); fixed orbit {i} puts 2 points on each of slope ±1.
  So the reduced fractions q/p over orbits, closed under reciprocal, must be
  pairwise distinct across orbits.
"""
from math import gcd
from model import involutions, points_of, no3

def labels(pairs, fixed):
    L = []
    for (i, j) in pairs:
        L.append(j - i)
        L.append(i + j - 1)
    if fixed is not None:
        L.append(2*fixed - 1)
    return L

def lemma_S(pairs, fixed):
    L = labels(pairs, fixed)
    return len(set(L)) == len(L)

def lemma_R(pairs, fixed):
    seen = set()
    orbs = list(pairs) + ([(fixed, fixed)] if fixed is not None else [])
    for (i, j) in orbs:
        p, q = 2*j - 1, 2*i - 1
        g = gcd(p, q)
        fr = (q//g, p//g)
        rec = (p//g, q//g)
        if fr in seen or rec in seen:
            return False
        seen.add(fr); seen.add(rec)
    return True

if __name__ == "__main__":
    print(f"{'n':>4} {'m':>3} {'#inv':>9} {'pass S':>8} {'pass R':>8} {'pass S&R':>9} {'no3 sols':>9}  S,R necessary?")
    for m in range(1, 14):
        n = 2*m
        tot = pS = pR = pSR = sols = 0
        viol = 0
        for pairs, fixed in involutions(m):
            tot += 1
            s = lemma_S(pairs, fixed); r = lemma_R(pairs, fixed)
            pS += s; pR += r; pSR += s and r
            ok = no3(points_of(pairs, fixed))
            sols += ok
            if ok and not (s and r):
                viol += 1
        print(f"{n:>4} {m:>3} {tot:>9} {pS:>8} {pR:>8} {pSR:>9} {sols:>9}  {'VIOLATION!' if viol else 'yes'}")
