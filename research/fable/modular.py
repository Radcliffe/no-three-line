#!/usr/bin/env python3
"""The modular involution family sigma_lambda.

Discovery (fifth pass): the K7-escaping survivor found at m = 36 satisfies
    2*sigma(i) - 1 == +- lambda * (2i - 1)  (mod 2m+1),  lambda = 27, lambda^2 == -1.

General construction. Let p = 2m+1 be prime. The odd numbers {1,3,...,2m-1}
are a complete set of representatives for the +- classes of (Z/p)^* (for each
r, exactly one of r, p-r is odd). If lambda^2 == -1 (mod p) then multiplication
by lambda permutes those classes with order 2, i.e. induces an INVOLUTION
sigma_lambda on {1..m}. Such lambda exists iff p == 1 (mod 4) iff m is even.
Fixed points would need lambda == +-1, impossible; consistent with m even
requiring zero fixed points (Theorem 2).

This script tests, for every even m with 2m+1 prime:
  - is sigma_lambda a valid involution (sanity)
  - is it a Lemma-S survivor (labels distinct)
  - its violating-line profile: total lines, orbits, smallest family
    max-coefficient (= the K it escapes), max points on a line
"""
import sys
from math import gcd
from collections import Counter, defaultdict

def is_prime(n):
    if n < 2: return False
    for d in range(2, int(n**0.5)+1):
        if n % d == 0: return False
    return True

def sqrt_minus1(p):
    """least lambda with lambda^2 == -1 mod p"""
    for l in range(2, p):
        if (l*l) % p == p-1: return l
    return None

def sigma_lambda(m, lam):
    p = 2*m+1
    sig = [0]*(m+1)
    for i in range(1, m+1):
        a = 2*i-1
        b = (lam*a) % p
        if b % 2 == 0: b = p - b          # take the odd representative
        j = (b+1)//2
        sig[i] = j
    return sig

def lemma_s_ok(m, sig):
    labs = []
    seen = set()
    for i in range(1, m+1):
        j = sig[i]
        if j == i: labs.append(2*i-1)
        elif i < j: labs += [j-i, i+j-1]
    return len(labs) == len(set(labs)), labs

def profile(m, sig):
    pts = []
    for i in range(1, m+1):
        a, b = 2*sig[i]-1, 2*i-1
        for sx in (1,-1):
            for sy in (1,-1):
                pts.append((sx*a, sy*b))
    pts = sorted(set(pts))
    assert len(pts) == 4*m, (m, len(pts))
    cnt = Counter()
    for x in range(len(pts)):
        for y in range(x+1, len(pts)):
            (x1,y1),(x2,y2) = pts[x], pts[y]
            dx, dy = x2-x1, y2-y1
            g = gcd(abs(dx), abs(dy)); A, B = dy//g, -dx//g
            if A < 0 or (A == 0 and B < 0): A, B = -A, -B
            cnt[(A,B,A*x1+B*y1)] += 1
    viol = {}
    for (A,B,C), pr in cnt.items():
        k = 1
        while k*(k-1)//2 < pr: k += 1
        if k >= 3: viol[(A,B,C)] = k
    if not viol: return 0, 0, None, 0
    minfam = min(max(abs(A),abs(B)) for (A,B,C) in viol)
    maxpts = max(viol.values())
    orbs = set()
    for (A,B,C) in viol:
        best = None
        for M in [(1,0,0,1),(-1,0,0,1),(1,0,0,-1),(-1,0,0,-1),
                  (0,1,1,0),(0,-1,1,0),(0,1,-1,0),(0,-1,-1,0)]:
            a2 = M[0]*A + M[2]*B; b2 = M[1]*A + M[3]*B; c2 = C
            if a2 < 0 or (a2 == 0 and b2 < 0): a2, b2, c2 = -a2, -b2, -c2
            k = (a2,b2,c2)
            if best is None or k < best: best = k
        orbs.add(best)
    return len(viol), len(orbs), minfam, maxpts

def main():
    mmax = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    print("m    n    p=2m+1  lam  LemmaS  violLines  orbits  minFamK  maxPtsOnLine")
    for m in range(2, mmax+1, 2):
        p = 2*m+1
        if not is_prime(p): continue
        lam = sqrt_minus1(p)
        if lam is None: continue
        sig = sigma_lambda(m, lam)
        # validity
        assert all(sig[sig[i]] == i for i in range(1, m+1)), (m, "not involution")
        assert sum(1 for i in range(1, m+1) if sig[i] == i) == m % 2, (m, "fixed pts")
        ok, labs = lemma_s_ok(m, sig)
        vl, vo, mf, mp = profile(m, sig)
        print(f"{m:<4d} {2*m:<4d} {p:<7d} {lam:<4d} {str(ok):<7s} {vl:<10d} {vo:<7d} "
              f"{str(mf):<8s} {mp}")
        sys.stdout.flush()

main()
