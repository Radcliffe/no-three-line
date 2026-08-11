#!/usr/bin/env python3
"""Monte Carlo model for K*(m).

lambda_K(m): mean number of violating lines with max coefficient <= K over
(approximately) random Lemma-S survivors.  First-moment model: an escape
(survivor avoiding all coeff<=K families) exists iff S(m)*exp(-lambda_K(m)) >~ 1.
Compare predicted K* with the exact table from dmin maxk.
"""
import random, sys
from math import gcd, log
from collections import Counter

# --- random survivor leaf (biased toward easy leaves; fine for means) ---
def rand_survivor(m):
    def rec(free, labs, fx, pairs):
        if not free: return pairs, fx
        i = free[0]
        opts = []
        if m % 2 and fx is None and (2*i-1) not in labs: opts.append(None)
        for j in free[1:]:
            d, s = j-i, i+j-1
            if d != s and d not in labs and s not in labs: opts.append(j)
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
    if not r: raise RuntimeError("no survivor")
    return r

def fam_viol(pairs, fx, p, q):
    """# violating lines in direction (p,q); multiply by 4 for the family."""
    cnt = Counter()
    for i, j in pairs:
        a, b = 2*i-1, 2*j-1
        for v in (q*b - p*a, q*b + p*a, q*a - p*b, q*a + p*b):
            cnt[v] += 1; cnt[-v] += 1
    if fx:
        g0 = 2*fx-1
        for v in (g0*(q-p), g0*(q+p)):
            cnt[v] += 1; cnt[-v] += 1
    return sum(1 for v in cnt.values() if v >= 3)

def main():
    random.seed(2026)
    KMAX = 12
    fams = [(p,q) for q in range(2, KMAX+1) for p in range(1, q)
            if gcd(p,q) == 1]
    ms = [12, 16, 20, 24, 28, 33, 40]
    R = {12:200, 16:200, 20:150, 24:120, 28:100, 33:80, 40:50}
    print("lambda_K(m) = mean violating lines with max coeff <= K (x4 directions incl.)")
    hdr = "m    " + "".join(f"K<={k:<7d}" for k in range(2, KMAX+1))
    print(hdr)
    lam = {}
    for m in ms:
        acc = Counter()
        for _ in range(R[m]):
            pairs, fx = rand_survivor(m)
            for (p,q) in fams:
                acc[(p,q)] += fam_viol(pairs, fx, p, q)
        row = f"m={m:<3d}"
        for K in range(2, KMAX+1):
            lamK = 4*sum(acc[(p,q)] for (p,q) in fams if q <= K)/R[m]
            lam[(m,K)] = lamK
            row += f"{lamK:<9.2f}"
        print(row); sys.stdout.flush()
    # per-family scaling at largest m
    print("\nper-family mean viol lines (x4) at m=33 and m=48:")
    for m in (33,):
        acc = Counter()
        for _ in range(60):
            pairs, fx = rand_survivor(m)
            for (p,q) in fams: acc[(p,q)] += fam_viol(pairs, fx, p, q)
        n = 60
        top = sorted(fams, key=lambda f: -acc[f])[:12]
        print(f"m={m}: " + ", ".join(f"({p},{q}):{4*acc[(p,q)]/n:.2f}" for (p,q) in top))
    # ln S(m) data (exact, senum/gcount + this session)
    lnS = {12: log(52), 14: log(257), 16: log(1589), 18: log(11417),
           20: log(75375), 22: log(616010), 13: log(623), 15: log(3628),
           17: log(23334), 19: log(172853), 21: log(1376330)}
    print("\nescape model: escape exists iff ln S(m) - lambda_K(m) > 0")
    for m in (12, 16, 20, 24, 28, 33):
        if m in lnS: ls = lnS[m]
        else:
            # extrapolate per parity with quadratic in m through last 3 points
            pts = sorted(k for k in lnS if k % 2 == m % 2)[-3:]
            x1, x2, x3 = pts; y1, y2, y3 = lnS[x1], lnS[x2], lnS[x3]
            # quadratic fit
            import numpy as np
            cs = np.polyfit([x1,x2,x3],[y1,y2,y3],2)
            ls = float(np.polyval(cs, m))
        row = f"m={m:<3d} lnS~{ls:6.2f} | margin lnS-lam:"
        for K in range(2, KMAX+1):
            row += f" K{K}:{ls-lam[(m,K)]:+.1f}"
        print(row)

main()
