"""
Fully symmetric (D4) no-three-in-line configurations.

Coordinates: for even n = 2m, center the grid so lattice points have odd
integer coordinates in {-(n-1), ..., -1, 1, ..., n-1} (both coords odd).
D4 acts by sign changes and swap.

Claim (verified below): a full-symmetry solution is exactly an involution
sigma of {1..m} with at most one fixed point, giving points
  { (±(2*sigma(i)-1), ±(2i-1)) : i = 1..m }
and no 3 collinear.
"""
from math import gcd
from itertools import combinations
import sys

def points_of(pairs, fixed):
    """pairs: list of (i,j) with i<j; fixed: None or index. Coordinates doubled-odd."""
    pts = []
    for (i, j) in pairs:
        a, b = 2*i - 1, 2*j - 1
        for s in (1, -1):
            for t in (1, -1):
                pts.append((s*b, t*a))   # rows ±a get x = ±b
                pts.append((s*a, t*b))   # rows ±b get x = ±a
    if fixed is not None:
        a = 2*fixed - 1
        pts += [(a, a), (a, -a), (-a, a), (-a, -a)]
    assert len(set(pts)) == len(pts)
    return pts

def collinear_triples(pts):
    """Return list of collinear triples (brute O(k^3) reference checker)."""
    bad = []
    for p, q, r in combinations(pts, 3):
        if (q[0]-p[0])*(r[1]-p[1]) == (q[1]-p[1])*(r[0]-p[0]):
            bad.append((p, q, r))
    return bad

def no3(pts):
    """O(k^2) check via line hashing."""
    lines = {}
    for a, b in combinations(pts, 2):
        dx, dy = b[0]-a[0], b[1]-a[1]
        g = gcd(dx, dy)
        dx, dy = dx//g, dy//g
        if dx < 0 or (dx == 0 and dy < 0):
            dx, dy = -dx, -dy
        c = dy*a[0] - dx*a[1]
        key = (dy, -dx, c)
        lines[key] = lines.get(key, 0) + 1
        if lines[key] >= 3:
            return False
    return True

def involutions(m):
    """All involutions of {1..m} with (# fixed points) == m mod 2 (i.e. 0 or 1)."""
    def rec(free, pairs, fixed):
        if not free:
            yield pairs, fixed
            return
        i = free[0]
        rest = free[1:]
        if fixed is None and m % 2 == 1:
            yield from rec(rest, pairs, i)
        for k, j in enumerate(rest):
            yield from rec(rest[:k] + rest[k+1:], pairs + [(i, j)], fixed)
    yield from rec(list(range(1, m+1)), [], None)

def in_grid_check(pts, n):
    for x, y in pts:
        assert -(n-1) <= x <= n-1 and x % 2 == 1 or x % 2 == -1
    # rows/cols exactly 2 each
    from collections import Counter
    rc = Counter(y for _, y in pts); cc = Counter(x for x, _ in pts)
    assert all(v == 2 for v in rc.values()) and len(rc) == n
    assert all(v == 2 for v in cc.values()) and len(cc) == n

if __name__ == "__main__":
    mmax = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    for m in range(1, mmax+1):
        n = 2*m
        sols = []
        total = 0
        for pairs, fixed in involutions(m):
            total += 1
            pts = points_of(pairs, fixed)
            if no3(pts):
                # cross-check with brute force
                assert not collinear_triples(pts)
                in_grid_check(pts, n)
                sols.append((pairs, fixed))
        print(f"n={n:3d} (m={m:2d}): involutions checked={total:8d}  full-symmetry solutions={len(sols)}")
        for pairs, fixed in sols:
            print(f"        pairs={pairs} fixed={fixed}")
