#!/usr/bin/env python3
"""Classify the violating lines of given involutions (doubled-odd model).

Input lines on stdin or argv: "m: s1 s2 ... sm" (sigma as printed by dmin).
For each, print the violating lines grouped by D4 line-orbit with family type
(|a|,|b|) of the normalized equation a x + b y = c, centrality, and point count.
"""
import sys
from math import gcd
from collections import Counter, defaultdict

def points(m, sigma):
    pts = []
    for i in range(1, m+1):
        j = sigma[i-1]
        a, b = 2*j-1, 2*i-1
        for sx in (1,-1):
            for sy in (1,-1):
                pts.append((sx*a, sy*b))
    return sorted(set(pts))

def norm_line(p, q):
    dx, dy = q[0]-p[0], q[1]-p[1]
    g = gcd(abs(dx), abs(dy))
    a, b = dy//g, -dx//g
    if a < 0 or (a == 0 and b < 0):
        a, b = -a, -b
    c = a*p[0] + b*p[1]
    return (a, b, c)

def d4_orbit(line):
    a, b, c = line
    out = set()
    for M in [(1,0,0,1),(-1,0,0,1),(1,0,0,-1),(-1,0,0,-1),
              (0,1,1,0),(0,-1,1,0),(0,1,-1,0),(0,-1,-1,0)]:
        a2 = M[0]*a + M[2]*b
        b2 = M[1]*a + M[3]*b
        c2 = c
        if a2 < 0 or (a2 == 0 and b2 < 0):
            a2, b2, c2 = -a2, -b2, -c2
        out.add((a2, b2, c2))
    return frozenset(out)

def analyze(m, sigma):
    pts = points(m, sigma)
    assert len(pts) == 4*m, (m, len(pts))
    cnt = Counter()
    for i in range(len(pts)):
        for j in range(i+1, len(pts)):
            cnt[norm_line(pts[i], pts[j])] += 1
    viol = {}
    for line, pairs in cnt.items():
        k = 1
        while k*(k-1)//2 < pairs: k += 1
        if k >= 3: viol[line] = k
    orbits = defaultdict(list)
    for line, k in viol.items():
        orbits[d4_orbit(line)].append((line, k))
    print(f"m={m} viol_lines={len(viol)} orbits={len(orbits)}")
    for orb, lines in sorted(orbits.items(), key=lambda t: sorted(t[0])[0]):
        a, b, c = sorted(lines)[0][0]
        fam = tuple(sorted((abs(a), abs(b))))
        cen = "CENTRAL" if all(l[0][2] == 0 for l in lines) else ""
        ks = sorted(k for _, k in lines)
        rep = sorted(l for l, _ in lines)
        print(f"   fam={fam} {cen} orbit_size={len(lines)} pts_per_line={ks} rep={rep[:2]}")

def main():
    data = sys.stdin.read().split("\n")
    for row in data:
        row = row.strip()
        if not row: continue
        mm, rest = row.split(":")
        sigma = [int(x) for x in rest.split()]
        analyze(int(mm), sigma)

main()
