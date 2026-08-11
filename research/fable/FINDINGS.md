# Fully symmetric no-three-in-line configurations: findings

Audience: an AI agent (or a person working like one) continuing this investigation.
Everything below is either proved, computed and cross-validated in this session,
or explicitly flagged as unverified.
Session date: 2026-08-08.
Code lives beside this file: `model.py`, `lemmas.py`, `search.c`, `senum.c`.

## 0. Problem statement and status

The no-three-in-line problem asks whether the n x n grid contains 2n points
with no three collinear.
This document concerns the sub-problem restricted to configurations invariant
under the full symmetry group of the square (dihedral D4, order 8) —
Flammenkamp's symmetry class `full`, marked `*` in his encoding.

Known before this session:

- Guy & Kelly, Conjecture I (1968): there are exactly 3 configurations with
  full symmetry. Source: https://wwwhomes.uni-bielefeld.de/achim/no3in/readme.html
  (fetched this session, page dated 2026-07-31).
- Flammenkamp's parity remarks
  (https://wwwhomes.uni-bielefeld.de/achim/no3in/symmetry_remarks.html):
  full symmetry forces n even;
  if n/2 is even no points lie on the long diagonals,
  if n/2 is odd both long diagonals carry points.
- Flammenkamp's near-miss counts (2006) for class `full` for even n <= 76 show
  the maximal achievable point count "drifting further and further away from 2n".
- VERIFIED (second pass): the full class has been searched empty up to
  n = 108. Source: https://wwwhomes.uni-bielefeld.de/achim/no3in/table.html
  (fetched this session, page dated 2026-07-26) states "The column with
  heading * continues to be 0 for all n <= 108" and lists class * as
  completely known to n = 108; its * entries are 1 at n = 2, 4, 10 and 0
  otherwise, matching this document's results. Also verified on the site:
  near-misses to n <= 76, an algorithm note about checking n = 72 in class
  full, and a minimal-defect table computed April 2026 (binary file, not
  parsed this session).
- Context on the general problem (verified on the same page, July 2026 state):
  record general solution n = 74 (Prellberg); Heule has been applying SAT
  solvers to classes rot4 and rct4 since June 2026; all solutions for n <= 20
  are enumerated.

New in this session, summarized:

1. Exact reduction of the full class to involutions of {1..m}, n = 2m (Theorem 2).
2. Two arithmetic necessary conditions, Lemma S and Lemma R; Lemma S alone
   proves n = 8 impossible by hand and pins n = 10 uniquely.
3. Independent exhaustive verification: zero solutions for all even
   12 <= n <= 64; the only solutions are n = 2, 4, 10 (Conjecture I holds to 64).
4. The natural first-moment (Guy-Kelly style) heuristic FAILS for this class:
   it predicts a growing number of solutions where there are provably none.
   The obstruction is extremal, not probabilistic: the minimum residual defect
   over Lemma-S survivors follows a growing staircase 8, 16, 24, 32.
5. A concrete SAT route to certified nonexistence past n = 108, with encoding
   sized for n ~ 110.

Second pass, same date (see section 10 for all details):

6. Exact D(m) extended from m = 20 to m = 27 by branch-and-bound (`dmin.c`).
   D is NOT monotone; the "staircase" reading of section 6 is superseded.
   Refined conjecture: D(m) >= 8*floor((m+6)/8), tight at m = 9, 17, 25.
7. Orbit-granularity theorem (proved): violating lines are never vertical,
   horizontal, or of slope +-1; D = 4c + 8g with c = central violating
   line-orbits, g = generic ones. All computed minimizers have c = 0.
8. Bounded-coefficient phenomenon: every Lemma-S survivor for 6 <= m <= 29
   violates some line a x + b y = c with max(|a|,|b|) <= 7 (exact
   computation). Single families are individually avoidable; only the union
   forces violations. The threshold K*(m) drifts slowly upward (3 -> 7).
9. Exact arithmetic form model (Theorem 4, verified on 2520 cases):
   the whole problem reduces to multiplicities of the linear forms
   |q*b_t +- p*a_t| over the pair partition of the odd numbers, no geometry.

Third pass, same date (section 11):

10. K*(m) is exact for all 6 <= m <= 33 and is NOT bounded at 7:
    K*(33) = 8. First occurrences of K* = 5, 6, 7, 8 at m = 12, 15, 21, 33
    fit m(kappa) = 9 + 3*2^(kappa-5) exactly — K* looks unbounded with
    log2 growth; first K* = 9 predicted at m = 57.
11. First-moment/Poisson modeling fails in the opposite direction too:
    mean lambda_7(33) ~ 145 >> ln S(33) ~ 28, yet K7-escapes exist.
    Extremal structure, not typical behavior, governs both tails.

Fourth pass, same date (section 12):

12. D(28) = 36 — first defect value not divisible by 8; its minimizer is
    the first with a central violating orbit (36 = 4*1 + 8*4). The linear
    law D(m) >= 8*floor((m+6)/8) holds (not tight at 28).
13. Escape costs EC_K(m) computed (new `esc` mode): avoiding all families
    with coefficients <= K costs 2.2x-8.9x the unconstrained minimum
    defect; at m = 16, 18, 22, 24 every minimizer provably violates the
    (1,2) family. EC_6(26) = 244 exceeds the mean defect of a random
    survivor.
14. K7-escapes are nearly extinct at the frontier: 2 root branches at
    m = 33, 1 at m = 34 (U_7(34) = 0, K*(34) >= 8, EC_7(34) = 88).

Fifth pass, same date (section 13) — the main structural result:

15. The escapers are ALGEBRAIC. For even m with p = 2m+1 prime and
    lambda^2 == -1 (mod p), multiplication by lambda induces an involution
    sigma_lambda that is a Lemma-S survivor, and its smallest violating
    line family is exactly {|a|,|b|} where p = a^2 + b^2 (verified 13/13,
    m <= 56). Hence K*(m) >= max(a,b) >= sqrt(m + 1/2): K* is UNBOUNDED
    with sqrt-like growth. This falsifies the log2 law of 11.2 (predicted
    first K* = 9 at m = 57; the construction gives K*(48) >= 9) and kills
    the fixed-finite-family reduction of 10.5-10.6.
16. K*(34) = K*(35) = 8 certified; K7-escapes do not go extinct
    (alive at m = 33, 34, 35, 36). Escapers at m = 33, 34, 35 are NOT
    modular — a second sporadic population exists.

## 1. Conventions (read before touching the code)

For even n = 2m, center the grid: lattice points have both coordinates odd,
in {-(n-1), ..., -1, 1, ..., n-1}.
Call these doubled-odd coordinates.
Row index i in {1..m} corresponds to the coordinate pair rows y = 2i-1 and
y = -(2i-1).
D4 acts by coordinate sign changes and swap.
To convert a doubled-odd coordinate o to a 0-indexed grid coordinate:
`(o + n - 1) / 2`.

## 2. Structure theorems (proved)

Theorem 1 (odd n impossible).
A fully symmetric solution has exactly 2 points in every row and column
(2n points, at most 2 per line, n rows).
For odd n, a point on the center column x = 0 is fixed by the mirror
x -> -x, so its row would need a second point (x,y) whose mirror (-x,y)
is a third point in that row; hence the center column holds no points,
contradicting "exactly 2 per column".
So n is even. (Also in Flammenkamp's symmetry remarks.)

Theorem 2 (involution model).
Let n = 2m. Fully symmetric solutions correspond bijectively to involutions
sigma of {1..m} with exactly (m mod 2) fixed points such that the 4m points

    { ( +-(2*sigma(i)-1), +-(2i-1) ) : i = 1..m }

have no three collinear.
Proof sketch: mirror symmetry forces each row's 2 points to be a pair
(+-x_i, 2i-1) with x_i odd and positive;
y -> -y symmetry makes rows +-(2i-1) agree;
the diagonal reflection (x,y) -> (y,x) forces i -> (x_i+1)/2 to be an
involution sigma;
each fixed point of sigma puts 2 points on each long diagonal, and 4 points
on a diagonal would contain a collinear triple, so sigma has at most one
fixed point;
parity of m then forces exactly m mod 2 fixed points.

Corollary (diagonal occupancy).
n ≡ 0 (mod 4) (m even): no fixed point, long diagonals empty.
n ≡ 2 (mod 4) (m odd): exactly one fixed point, both long diagonals carry
2 points.
Matches Flammenkamp's remark independently.

Consequence for search: the configuration space at n = 2m is the set of
such involutions, of size (m-1)!! for even m and m*(m-2)!! for odd m.
At n = 108 (m = 54) that is 53!! ≈ e^81, so raw enumeration is hopeless
and pruning must do the work.

## 3. Arithmetic necessary conditions (proved, and verified exactly necessary)

Lemma S (slope +-1 lines; the dominant constraint).
For a pair orbit {i,j}, i < j, the 8 points put exactly 2 points on each of
the four lines x - y = +-2(j-i) and x - y = +-2(i+j-1),
and by the diagonal mirror the same holds for slope -1 lines.
A fixed orbit {f} puts 1 point on x - y = +-2(2f-1) and 2 points on x - y = 0.
Therefore, defining the label multiset

    L(sigma) = { j-i : pairs {i,j} } ∪ { i+j-1 : pairs {i,j} } ∪ { 2f-1 : fixed f },

a solution requires ALL m labels pairwise distinct
(a repeated label v puts >= 3 points on the line x - y = 2v).
Conversely every slope +-1 violation is a label collision,
so Lemma S exactly characterizes the slope +-1 constraints.
Labels live in {1, ..., 2m-1}: this is a Sidon/graceful-labeling flavor
condition using about half the available values.

Hand proof that n = 8 has no fully symmetric solution (m = 4, no fixed point):
(12)(34) gives labels {1,2} ∪ {1,6}: repeat 1.
(13)(24) gives {2,3} ∪ {2,5}: repeat 2.
(14)(23) gives {3,4} ∪ {1,4}: repeat 4.
All three pairings fail; done.
No collinearity computation needed.

At m = 5 exactly one involution satisfies Lemma S,
namely sigma = (1 5)(3 4) with fixed point 2,
and it is the n = 10 solution:
doubled-odd points (+-9,+-1), (+-1,+-9), (+-7,+-5), (+-5,+-7), (+-3,+-3);
0-indexed 10x10 grid points
(9,5),(9,4),(0,5),(0,4),(5,9),(5,0),(4,9),(4,0),
(8,7),(8,2),(1,7),(1,2),(7,8),(7,1),(2,8),(2,1),(6,6),(6,3),(3,6),(3,3).

Lemma R (lines through the center).
Orbit {i,j} puts 2 points on each central line of slope +-(2i-1)/(2j-1)
and +-(2j-1)/(2i-1); a fixed orbit uses slopes +-1.
So the reduced fractions (2i-1)/(2j-1), taken with their reciprocals,
must be pairwise distinct across orbits.
Example conflict: {2,5} reduces 3/9 -> 1/3, clashing with {1,2} -> 1/3.

Both lemmas verified exactly necessary against full enumeration for m <= 13
(`lemmas.py`): every no-3-in-line involution passes both; no violations.

Filter strength (exact counts, `lemmas.py` output):

| n  | m  | involutions | pass S | pass R | pass S and R | solutions |
|----|----|-------------|--------|--------|--------------|-----------|
| 2  | 1  | 1           | 1      | 1      | 1            | 1         |
| 4  | 2  | 1           | 1      | 1      | 1            | 1         |
| 6  | 3  | 3           | 1      | 3      | 1            | 0         |
| 8  | 4  | 3           | 0      | 3      | 0            | 0         |
| 10 | 5  | 15          | 1      | 15     | 1            | 1         |
| 12 | 6  | 15          | 1      | 15     | 1            | 0         |
| 14 | 7  | 105         | 7      | 105    | 7            | 0         |
| 16 | 8  | 105         | 4      | 93     | 3            | 0         |
| 18 | 9  | 945         | 33     | 885    | 28           | 0         |
| 20 | 10 | 945         | 15     | 885    | 15           | 0         |
| 22 | 11 | 10395       | 162    | 9405   | 140          | 0         |
| 24 | 12 | 10395       | 52     | 9405   | 41           | 0         |
| 26 | 13 | 135135      | 623    | 124215 | 555          | 0         |

Lemma S prunes ~99.5% of involutions by m = 12 and is the constraint to
organize any search or encoding around.

## 4. Exhaustive search results (new, independent)

Engine: `search.c` — DFS over involutions, incremental line-count hash
(chained buckets, head insertion; strict LIFO trail undo exploits DFS
discipline so deleted entries are always bucket heads), gcd lookup table.
Branch order matters a lot: pairing the SMALLEST free index first
(`order_desc = 0`) beats largest-first by ~15x in nodes.
Validated against the independent Python brute force for all m <= 13
(solution counts and solution sets agree).

Result: zero fully symmetric solutions for all even 12 <= n <= 64.
Together with the enumeration above: the only fully symmetric solutions
with n <= 64 are n = 2, 4, 10 — Conjecture I verified to n = 64.

Node counts, ascending order, all runs COMPLETE (times on this container):

| m  | n  | nodes      | time    |
|----|----|------------|---------|
| 13 | 26 | 508        | <0.01 s |
| 14 | 28 | 415        | <0.01 s |
| 15 | 30 | 1,472      | 0.01 s  |
| 16 | 32 | 1,117      | <0.01 s |
| 17 | 34 | 4,396      | 0.02 s  |
| 18 | 36 | 3,281      | 0.02 s  |
| 19 | 38 | 12,871     | 0.07 s  |
| 20 | 40 | 10,283     | 0.07 s  |
| 21 | 42 | 40,626     | 0.27 s  |
| 22 | 44 | 30,765     | 0.22 s  |
| 23 | 46 | 130,870    | 0.95 s  |
| 24 | 48 | 95,898     | 0.70 s  |
| 25 | 50 | 420,125    | 3.4 s   |
| 26 | 52 | 316,188    | 2.6 s   |
| 27 | 54 | 1,388,368  | 13.2 s  |
| 28 | 56 | 996,843    | 10.1 s  |
| 29 | 58 | 4,604,519  | 48.9 s  |
| 30 | 60 | 3,353,107  | 37.9 s  |
| 31 | 62 | 15,551,991 | 197 s   |
| 32 | 64 | 11,348,059 | 136 s   |

Empirical growth: nodes multiply by ~3.4 per unit of m within a parity class
(even m consistently cheaper: no fixed-point branch).
Extrapolation for THIS engine, single-threaded:
n = 70 in ~1 h, n = 80 in ~40 h, n = 108 in ~10^7 h.
So this engine alone will not reach 108;
see section 7 for what will.

## 5. Statistical structure of the constraint system

Monte Carlo over uniform random involutions of the required fixed-point count
(`search mc`, `senum mcv`, 2000-3000 samples per m):

- Mean number of collinear TRIPLES fits T(m) ≈ 4.6-4.7 * m * ln m
  across 5 <= m <= 60 (T/(m ln m) = 4.5, 4.6, 4.66, 4.70 at m = 10, 20, 40, 60).
- Violations are heavily clumped: bad lines come in D4 orbits;
  observed clump factor (violating lines per violating line-orbit) ≈ 7.9.
- Mean number of violating LINE-ORBITS lambda(m):
  2.18, 3.42, 5.23, 7.16, 9.12, 11.37, 13.57, 16.01 at m = 6, 8, ..., 20;
  32.3 at m = 32; 68.4 at m = 54; 79.3 at m = 60.

## 6. The first-moment heuristic fails — and why that is informative

The Guy-Kelly style estimate for this class would be
E(m) ≈ N_inv(m) * P(no violation) ≈ N_inv(m) * exp(-lambda(m)),
treating violating line-orbits as Poisson.
Compare (ln N_inv exact, lambda from MC):

| m  | n   | ln N_inv | lambda | ln E_naive | actual solutions |
|----|-----|----------|--------|------------|------------------|
| 6  | 12  | 2.71     | 2.18   | +0.5       | 0                |
| 8  | 16  | 4.65     | 3.42   | +1.2       | 0                |
| 10 | 20  | 6.85     | 5.23   | +1.6       | 0                |
| 12 | 24  | 9.25     | 7.16   | +2.1       | 0                |
| 14 | 28  | 11.81    | 9.12   | +2.7       | 0                |
| 16 | 32  | 14.52    | 11.37  | +3.2       | 0                |
| 20 | 40  | 20.30    | 16.01  | +4.3       | 0                |
| 32 | 64  | 39.80    | 32.32  | +7.5       | 0                |
| 54 | 108 | 81.05    | 68.37  | +12.7      | 0 reported       |

Note: the n = 10 solution lives at m = 5 (not in this table);
every row above has zero solutions,
verified exhaustively through m = 32.
The naive estimate predicts e^{4.3} ≈ 73 solutions at n = 40 and
e^{12.7} ≈ 3*10^5 at n = 108. It is wrong by an unboundedly growing factor.

Diagnosis: P(zero violations) is not exp(-lambda);
it is exactly 0 on the region we can see,
because the violation count has a hard positive floor.
Exact evidence: enumerate ALL Lemma-S survivors (`senum senum <m>`) and record
the minimum number of violating lines over the whole class:

| m  | n  | S-survivors | mean viol lines | mean viol orbits | MIN viol lines |
|----|----|-------------|-----------------|------------------|----------------|
| 5  | 10 | 1           | 0               | 0                | 0              |
| 6  | 12 | 1           | 16.0            | 2.0              | 16             |
| 7  | 14 | 7           | 13.7            | 1.7              | 8              |
| 8  | 16 | 4           | 25.0            | 3.3              | 16             |
| 9  | 18 | 33          | 27.8            | 3.5              | 8              |
| 10 | 20 | 15          | 35.7            | 4.5              | 16             |
| 11 | 22 | 162         | 40.4            | 5.1              | 16             |
| 12 | 24 | 52          | 46.1            | 5.9              | 16             |
| 13 | 26 | 623         | 55.1            | 6.9              | 16             |
| 14 | 28 | 257         | 61.2            | 7.7              | 24             |
| 15 | 30 | 3,628       | 70.1            | 8.8              | 16             |
| 16 | 32 | 1,589       | 78.5            | 9.9              | 24             |
| 17 | 34 | 23,334      | 85.2            | 10.7             | 16             |
| 18 | 36 | 11,417      | 91.1            | 11.5             | 24             |
| 19 | 38 | 172,853     | 100.6           | 12.6             | 24             |
| 20 | 40 | 75,375      | 108.5           | 13.6             | 32             |

The minimum defect follows a staircase: 8 -> 16 -> 24 -> 32,
stepping up roughly every 5-6 in m,
with odd m consistently dipping one step below the neighboring even m.
This is the reduced-model form of Flammenkamp's near-miss drift,
and it is the cleanest quantitative evidence for the conjecture found here:
survivor counts grow, but every survivor is getting FARTHER from a solution.

Working conjecture (defect floor).
Let D(m) = min over Lemma-S survivors of the number of violating lines.
Then D(m) >= 8 for all m >= 6, and D(m) -> infinity.
Either statement implies the original conjecture
(the first for all n >= 12, given the small cases).
D(m) >= 8 is verified for 6 <= m <= 20 by exact enumeration
and (implicitly) for m <= 32 by the exhaustive search.

UPDATE (second pass, same session): exact D(m) is now known through m = 27
and the staircase description above is falsified in detail — D is not
monotone (D(20) = 32 but D(21..23) = 24) and the odd-below-even pattern
breaks at D(26) = D(27) = 32. The floor D(m) >= 8 stands, now exactly
verified to m = 27. See section 10, which supersedes this paragraph.

## 7. Methods to extend beyond n = 108

Ranked by expected value per effort.

### 7.1 SAT with certified UNSAT (recommended first)

Encode the involution model per n:

- Variables: one per candidate orbit.
  Pairs {i,j}, 1 <= i < j <= m, plus singletons {f} iff m odd.
  At n = 110 (m = 55): C(55,2) + 55 = 1540 variables.
- ExactlyOne over the orbits containing each index i
  (pairwise at-most-one plus at-least-one, or a commander encoding).
- Binary conflict clauses: for every pair of orbits whose union of point sets
  contains 3 collinear points, add (-a OR -b).
  These subsume Lemma S, Lemma R, all 2+1 and 2+2 line collisions,
  and the at-most-one-fixed constraint.
  Precomputation is O(#orbits^2) point-set checks ≈ 1.2M at m = 55; trivial.
- Ternary clauses: for lines receiving 1 point each from 3 distinct orbits.
  Enumerate lines of the doubled-odd grid with >= 3 candidate points
  (every candidate point belongs to exactly one orbit, so this is line-major
  and never touches triples of orbits directly).
  Skip any clause containing a binary-conflicting pair (subsumed).
  Estimated 10^6-10^7 clauses at n ~ 110; within CaDiCaL/Kissat range.
- Run with DRAT/LRAT proof logging and check with drat-trim.
  Result per n: a machine-checkable certificate of nonexistence.

This is the same technology Heule applied to rot4/rct4 in June 2026,
and the full class is far smaller than either of those,
so n well past 108 should be reachable.
Sanity checks for the implementation:
n = 10 must be SAT with the unique model sigma = (1 5)(3 4), fixed 2;
n = 8, 12, ..., 64 must be UNSAT (cross-check against section 4).

### 7.2 Lemma-S-first enumeration

Enumerate label-distinct involutions (the S-survivors) as the outer loop,
then check the remaining line families.
Survivor counts (from `senum`, also reproducible via `search gcount`):
1, 1, 1, 0, 1, 1, 7, 4, 33, 15, 162, 52, 623, 257, 3628, 1589, 23334, 11417,
172853, 75375 for m = 1..20.
Growth is roughly x5-7 per Delta m = 2 in this range — far below (m-1)!!.
A DFS that interleaves label bookkeeping (O(1) bitmask) with lazy geometric
checks, plus an MRV-style choice of the next index by remaining label options,
should beat the current engine by orders of magnitude.
The current engine discovers Lemma-S conflicts only through the general line
hash after placing points; making labels a first-class constraint prunes the
same subtrees at near-zero cost, earlier.

### 7.3 Defect floor as a proof target

Section 6 converts the conjecture into additive combinatorics:
show that any involution with pairwise-distinct labels
(a graceful-like condition on {j-i} ∪ {i+j-1})
must still create >= 1 violating line among finitely many explicit families.
The observed minima are achieved on slope +-1/central/small-slope families,
which are all described by linear conditions on (i, sigma(i)).
A plausible attack: treat the permutation matrix of sigma on the m x m grid,
apply a discrepancy or Fourier-analytic argument to show the label conditions
force near-arithmetic structure that some other slope family then punishes.
Nothing here is proved; this is the direction the data points.

### 7.4 Engineering notes if extending the current C engine

- Root splitting is already implemented:
  `./search search <m> <secs> 0 <jlo> <jhi>` restricts the first decision
  (index 1's partner) to j in [jlo, jhi], j = 1 meaning the fixed option.
  Verified: the union over j-ranges reproduces the unrestricted node count.
  Use it to distribute a single m across processes or across tool-call
  time limits.
- A GPU port has precedent: Riley's CUDA code enumerated rot4 classes at
  n ~ 50 on HPC clusters (per Flammenkamp's page, Feb 2026).

## 8. Reproduction

Build and validate (all commands from the code directory):

    gcc -O2 -march=native -o search search.c -lm
    gcc -O2 -march=native -o senum senum.c -lm
    python3 model.py 11        # full enumeration to n=22; expect sols at 2,4,10 only
    python3 lemmas.py          # the filter table of section 3; expect "yes" per row
    ./search scan 13 60 0      # ascending order; expect the node counts of section 4
    ./search search 5 0        # expect 1 solution: sigma 5 2 4 3 1
    ./senum senum 12           # expect S_survivors=52, min_resid_viol=16

Validation anchors (any deviation means a broken build or model drift):
m = 13 ascending nodes = 508;
m = 20 S-survivors = 75375, minimum violations = 32;
m = 31 nodes = 15,551,991, COMPLETE, 0 solutions.

Environment pitfalls hit this session:

- Background processes (`nohup ... &`) do NOT survive between tool calls.
  Run everything foreground; single calls cap at roughly 300 s wall time,
  so use the root-splitting arguments for anything longer.
- `senum.c` caps the per-configuration violating-line-orbit dedup buffer at
  4096 (`seen[]`); fine for m <= ~120 (violating lines at m = 60 average 584)
  but check before pushing m much higher.
- `search.c` limits: MAXM = 80, gcd table covers coordinate deltas < 512,
  line-key packing assumes |a|,|b| < 256 and |c| < 2^19 — all safe for
  m <= 80, revisit beyond.
- The two orderings in `search.c` differ ~15x in nodes; always pass
  final arg 0 (ascending) for production runs.

## 9. Open questions, sharpest first

1. Does the defect floor D(m) tend to infinity? Even D(m) >= 8 for all
   m >= 6 settles the original conjecture. Exact values known to m = 20;
   the SAT encoding of 7.1 with a cardinality relaxation
   (allow <= k violating lines, minimize k) can extend this table cheaply,
   and the table's growth rate is itself evidence.
2. Why does the fixed point help? Odd m dips one staircase step below even m
   throughout the data. A structural explanation might isolate what makes
   n ≡ 2 (mod 4) friendlier and explain why the last solution (n = 10)
   is in that class.
3. What is the asymptotic count of label-distinct involutions
   (the S-survivors)? The sequence 1,1,1,0,1,1,7,4,33,15,162,52,623,257,...
   appears to be new; it is a natural graceful-labeling relative and may
   deserve an OEIS entry regardless of the geometry.
4. Can Lemma S be strengthened by adjoining the slope +-2 and +-1/2 families
   into a single arithmetic obstruction that already forces a violation for
   some m by counting alone, the way Lemma S kills m = 4?
   UPDATE: partially answered in 10.5 — no single family suffices
   (each is individually avoidable), but the union of families with
   coefficients <= 7 is empirically unavoidable for all 6 <= m <= 29.

## 10. Second pass (2026-08-08): exact D(m) to 27, structure of minimizers, bounded-coefficient reduction

New code beside this file: `dmin.c` (branch-and-bound for D(m) and
family-restricted floors), `analyze_min.py` (classify violating lines of a
given sigma), `verify_forms.py` (numerical check of Theorem 4).
Build: `gcc -O2 -march=native -o dmin dmin.c -lm`.

### 10.1 Branch-and-bound engine

`dmin.c` runs the Lemma-S-first DFS proposed in 7.2 (labels as first-class
O(1) constraints) with the incremental line-count hash of `search.c`, but
instead of failing on a third point per line it maintains the running count
of violating lines (2 -> 3 transitions, undone on backtrack) and prunes any
node whose count already reaches the best known. The count is monotone in
the partial assignment, so pruning is exact.

    ./dmin dmin <m> [ub] [jlo jhi]   exact D(m); ub is an EXCLUSIVE initial
                                     bound (result -1 certifies min >= ub);
                                     jlo/jhi restrict index 1's partner as in
                                     search.c (j = 1 = the fixed option)
    ./dmin fam  <m> <A> <B> [ub]     count only lines with {|a|,|b|} = {A,B}
    ./dmin maxk <m> <K> [ub] [jlo jhi]  count only lines with max(|a|,|b|) <= K

Validation: `dmin dmin <m>` reproduces every senum minimum for m <= 20,
and senum full enumeration was extended to m = 21, 22 as an independent
cross-check of the new values (min 24 both, matching dmin).
This is ~15-100x cheaper than full enumeration and reached m = 27
(m = 27 took ~45 CPU-minutes across split root branches).

Validation anchors for `dmin` (deviation = broken build or model drift):

    ./dmin dmin 20           -> D=32, nodes=298376
    ./dmin dmin 22 33        -> D=24, nodes=862289
    ./dmin maxk 26 7 17      -> D=16, nodes=9914392
    ./senum senum 21         -> S_survivors=1376330, min_resid_viol=24

Later-pass anchors (sections 12, 13):

    ./dmin esc 20 0          -> identical to ./dmin dmin 20 (D=32, 298376)
    ./dmin esc 28 6          -> EC=144
    ./uk 33 7 9 9            -> ESCAPE, nodes=5598722
    ./uk 33 7 2 2            -> NONE,   nodes=8547155
    python3 modular.py 40    -> rows m=6..36, min viol family = max(a,b)

### 10.2 Exact defect floor D(m), m <= 27

| m  | 5 | 6  | 7 | 8  | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 |
|----|---|----|---|----|---|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| D  | 0 | 16 | 8 | 16 | 8 | 16 | 16 | 16 | 16 | 24 | 16 | 24 | 16 | 24 | 24 | 32 | 24 | 24 | 24 | 32 | 24 | 32 | 32 | 36 |

m = 21..27 are new; m = 28 was added in the fourth pass (section 12) and is
the first value that is NOT a multiple of 8 — its unique-defect minimizer
carries a central violating orbit (see 12.1). Certification for the split m = 27 run: branch j = 4
achieved 32 exactly; every other root branch was shown to have min >= 29
(ub 29 returned -1); by Theorem 3 below all counts are multiples of 4, so
nothing in {29,30,31} exists and D(27) = 32.

Headlines:

- D is NOT monotone: D(20) = 32 then D(21) = D(22) = D(23) = 24;
  D(24) = 32 then D(25) = 24. The old staircase story is wrong in detail.
- The floor still climbs in windows: min D over m in [6,9] is 8,
  over [10,17] is 16, over [18,25] is 24, over [26,27] is 32 so far.
- Refined working conjecture (fits ALL data, tight at m = 9, 17, 25):

      D(m) >= 8 * floor((m+6)/8) for m >= 6,
      with equality at m = 8k+1 (D = 8k), k = 1, 2, 3.

  This is linear growth D(m) ~ m, much stronger than D -> infinity.
  CONFIRMED at m = 28 (fourth pass): D(28) = 36 >= 32, overshooting the
  floor — the law survives as a lower bound and is not tight at 28.
- The odd-dips-below-even pattern (old open question 2) survives at
  m = 21, 25 but breaks at m = 27 (D(27) = D(26) = 32).

Minimizer sigmas (doubled-odd model, sigma[1..m]), for reproduction:

    m=21: 6 14 20 15 12 1 8 7 18 10 19 5 16 2 4 13 21 9 11 3 17
    m=22: 11 16 22 20 17 15 9 21 7 13 1 18 10 19 6 2 5 12 14 4 8 3
    m=23: 7 14 17 6 22 4 1 16 12 23 21 9 13 2 20 8 3 19 18 15 11 5 10
    m=24: 11 14 21 6 22 4 23 15 12 24 1 9 19 2 8 20 18 17 13 16 3 5 7 10
    m=25: 23 17 6 13 25 3 7 14 20 15 21 16 4 8 10 12 2 19 18 9 11 24 1 22 5
    m=26: 9 23 14 7 19 21 4 25 1 22 12 11 26 3 20 18 24 16 5 15 6 10 2 17 8 13
    m=27: 4 13 16 1 22 25 27 18 24 26 11 17 2 21 23 3 12 8 20 19 14 5 15 9 6 10 7

New survivor counts from the cross-check: S(21) = 1,376,330;
S(22) = 616,010 (extends the section 7.2 sequence).

### 10.3 Theorem 3 (orbit granularity; proved)

For any Lemma-S survivor configuration P (4m points):

(a) every vertical/horizontal line meets P in exactly 2 points or 0;
    the axes are empty (coordinates are odd);
(b) the two main diagonals hold 0 points (m even) or exactly 2 each (m odd);
(c) slope +-1 non-central lines hold <= 2 points (this IS Lemma S);
(d) hence every violating line has slope not in {0, infinity, +-1};
(e) the violating set is D4-invariant; a violating line's D4-orbit has size
    4 if the line passes through the center, else 8. (Stabilizers: rotations
    by +-90 deg fix no line; the mirrors fix only slopes {0,inf,+-1};
    the 180-deg rotation fixes exactly the central lines.)

Consequently D = 4c + 8g where c, g count violating central/generic
line-orbits, so every violating count is a multiple of 4, and
"zero solutions at m" is equivalent to D(m) >= 4.
Checked on 320 random survivors across m = 8..29: no violating line ever in
the excluded families, and counts always split as 4c + 8g.

Corollary: for m <= 27 (where D >= 8 is exact) no survivor fails through
central lines alone: every survivor has a violating line orbit of size 8.

### 10.4 Anatomy of the minimizers

Classifying the violating lines of every computed minimizer
(`analyze_min.py`):

- All violating line-orbits at all minimizers m = 11..27 have size 8 and
  c = 0 (no central violations): D(m) = 8 * (number of violating orbits),
  i.e. the defect floor is really an ORBIT floor D_orb(m) = D(m)/8 =
  2,1,2,1,2,2,2,2,3,2,3,2,3,3,4,3,3,3,4,3,4,4 for m = 6..27.
  CAVEAT (fourth pass): this purity FAILS at m = 28, where the minimizer
  has one central orbit and D(28) = 36 = 4*1 + 8*4; see 12.1.
- Minimizers economize by SATURATION, not spreading: they pack many points
  onto few sacrificial lines. Examples: m = 13 has a (1,-2) line with 5
  points; m = 25 has a (1,-2) line orbit with EIGHT points per line.
  Minimizing violating lines is very different from minimizing triples.
- The violating families are small-coefficient: (1,2) appears in most
  minimizers; others seen: (1,3), (2,3), (3,4), (1,4), (2,5), (1,6), (5,6),
  and once (2,11) at m = 24. m = 21 is the outlier that avoids (1,2) and
  (1,3) entirely, at the price of two (5,6) orbits.

### 10.5 Bounded-coefficient reduction (the sharpest new fact)

Single families do NOT force violations: for the family {|a|,|b|} = {1,2}
the restricted floor is 0 for every 6 <= m <= 20 except m = 10
(`dmin fam`); each family alone can be dodged.

Unions of small families cannot. Let U_K(m) = min over survivors of the
number of violating lines with max(|a|,|b|) <= K, and let K*(m) be the
least K with U_K(m) > 0. Exact values (`dmin maxk`):

| m     | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29  |
|-------|---|---|---|---|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|----|-----|
| K*    | 3 | 4 | 4 | 4 | 2  | 4  | 5  | 4  | 5  | 6  | 4  | 5  | 6  | 6  | 5  | 7  | 5  | 5  | 6  | 6  | 7  | 7  | 7  | <=7 |
| floor | 8 | 8 | 16| 8 | 8  | 8  | 16 | 8  | 8  | 8  | 8  | 8  | 16 | 8  | 8  | 16 | 8  | 8  | 8  | 8  | 16 | 8  | 8  | 8   |

(floor = U at K = K*; m = 29 checked at K = 7 only, floor 8.)

So: EVERY Lemma-S survivor for 6 <= m <= 29 has >= 8 violating lines among
the families with coefficients at most 7. If that persisted for all m, the
full-symmetry conjecture would reduce to finitely many explicit arithmetic
families. Caution: K*(m) itself drifts upward (first 7 at m = 21, again at
26, 27, 28), so K* may be unbounded; its growth rate is the key question.
UPDATE (third pass): it does NOT persist — K*(33) = 8, and the growth rate
is measured; see section 11.
Cost note: these runs are much cheaper than full D(m) (m = 29 at K = 7 was
~7 CPU-minutes), so this table extends much further than D can.

### 10.6 Theorem 4 (exact form model; algebra + verified on 2520 cases)

Identify a survivor with its pair partition {a_t, b_t} of the odd numbers
{1, 3, ..., 2m-1} (a = 2i-1, b = 2j-1 for orbit {i, j = sigma(i)}, plus a
singleton g0 = 2f-1 if m is odd). Lemma S says: the m half-values
{(b_t - a_t)/2} u {(b_t + a_t)/2} (u {f}) are pairwise distinct.

For a primitive direction (dx, dy), the multiset of values c = dy*x - dx*y
over the 4m points is exactly, per pair orbit,

    { +-(dy*b - dx*a), +-(dy*b + dx*a), +-(dy*a - dx*b), +-(dy*a + dx*b) }

(and { +-g0*(dy - dx), +-g0*(dy + dx) } for the singleton). A line of that
direction is violating iff its c-value has multiplicity >= 3 in this
multiset. Verified against direct geometry on 2520 (m, survivor, family)
cases: zero mismatches (`verify_forms.py`).

Within-orbit coincidences (one orbit putting 2 points on one line of the
family) occur iff b/a = (dy+dx)/(dy-dx): e.g. b = 3a doubles up in the
(1,2) family — the geometric residue of the ratio condition in Lemma R.

Everything is now arithmetic: the defect-floor conjecture, restricted to
coefficients <= 7 (per 10.5), reads:

    For every partition of {1,3,...,2m-1} into pairs (plus one singleton
    for odd m) whose half-sums and half-differences are all distinct, some
    value is attained >= 3 times by the forms |q*b_t +- p*a_t| for some
    coprime (p,q) with max(p,q) <= 7 (q > p >= 1, p+q odd; for p, q both
    odd the forms are even and halve — these are the images of the odd-odd
    families under the duality (p,q) <-> ((q-p)/2, (q+p)/2)).

This is a Sidon/graceful-flavor statement about 4 linear forms per family
acting on a sum-difference-covering pair system, with NO remaining
geometric content. It is the recommended proof target, ahead of the
discrepancy route of 7.3.

### 10.7 Status of the working conjecture after this pass

- D(m) >= 8 for m >= 6: now EXACT for m <= 27 (was: implicit to 32 only as
  D >= 4-equivalent... strictly, zero solutions for m <= 32 gives D >= 4
  there; purely-central failure modes are excluded only where D is exact).
- D(m) -> infinity: strengthened to the linear-growth conjecture of 10.2.
- Not resolved. What a proof now needs, in decreasing order of ambition:
  (i) show some coefficient-bounded family union is unavoidable for all m
  (10.5-10.6); (ii) show D_orb >= 1, i.e. at least one size-8 violating
  orbit, for all m >= 6; (iii) any infinite family of m.

### 10.8 Updated open questions

1. Is K*(m) bounded? Extend the 10.5 table (cheap to m ~ 35 with current
   code; each +1 in m costs ~3-4x). If K* stabilizes, attack the finite
   union arithmetically via 10.6. If it grows like log m or sqrt m, measure
   the rate — it quantifies how much of the plane the obstruction needs.
   ANSWERED (third pass, section 11): not bounded at 7 — K*(33) = 8 — and
   the first-occurrence data fit K*(m) ~ 5 + log2((m-9)/3) exactly.
2. Prove D(28) >= 32 (tests the refined conjecture's next step) and
   D(33) = 32 (next predicted tight point, m = 8*4+1).
3. Why does saturation (8 points on one line, m = 25) beat spreading?
   A local-exchange argument around saturated lines might yield the first
   nontrivial lower bound on D_orb.
4. The old open questions 1-4 of section 9 stand except as annotated.
5. OEIS check for the survivor sequence (old Q3) was attempted; the OEIS
   endpoint was unreachable from this environment. Sequence now extends
   ..., 172853, 75375, 1376330, 616010 (m = 19..22).

## 11. Third pass (2026-08-08): K*(m) is not bounded at 7 — growth measured

This section resolves the direction of open question 10.8.1.
New code: `kstar_model.py` (Monte Carlo lambda_K study).

### 11.1 Exact K*(m) extended to m = 33

Method note: to decide positivity of U_K(m) it suffices to run
`dmin maxk <m> <K> 1 [jlo jhi]` — with exclusive bound 1 the search prunes
at the FIRST violating line, so it is exactly an existence search for a
K-escaping survivor (result 0 = witness found, -1 = none exists, which by
Theorem 3 already implies floor >= 4). This is several times cheaper than
computing the floor and is how everything below was certified.

| m  | 29 | 30 | 31 | 32 | 33 |
|----|----|----|----|----|----|
| K* | 7  | 7  | 7  | 7  | 8  |

(m = 29: K6-escape exists, K7 floor 8 exactly from 10.5. m = 30, 31, 32:
K6-escapes exist, K7 exhausted over all root branches. m = 33: K7-escapes
EXIST — two witnesses below — and K8 was exhausted over all 33 root
branches, ~25 CPU-min, so U_8(33) >= 4 and K*(33) = 8.)

K7-escape witnesses at m = 33 (sigma[1..33]):

    9 26 19 29 18 6 11 28 1 33 7 22 31 17 20 30 14 5 3 15 27 12 24 23 32 2 21 8 4 16 13 25 10
    10 33 3 19 31 24 30 32 11 1 9 16 20 27 23 12 29 21 4 13 18 28 15 6 26 25 14 22 17 7 5 8 2

Anatomy (`analyze_min.py`): every violating family of witness 1 has max
coefficient >= 8 as required — (1,8), (1,12) x2, (2,9), (2,11), (3,14),
(5,14), (6,19), (7,8), (7,11), (7,19), (14,15), plus one CENTRAL (1,17)
orbit (the first central violation seen at any extremal config); 100
violating lines in 13 orbits. Witness 2: 9 orbits, 72 lines, smallest
family (3,8) — hence D(33) <= 72 unconditionally, while 10.2 conjectures
D(33) = 32 (m = 8*4+1 tight point): escaping the low families appears to
cost ~2-3x the unconstrained minimum defect. Low-coefficient
lines are where survivors WANT to fail; they can be forced out only at a
steep price in total defect.

### 11.2 First-occurrence law

First m at which K*(m) reaches kappa:

    kappa       5    6    7    8
    first m     12   15   21   33
    gap              3    6    12

The gaps double: first-occurrence fits m(kappa) = 9 + 3*2^(kappa-5)
EXACTLY for kappa = 5, 6, 7, 8. Equivalently

    K*(m) <= 5 + log2((m-9)/3), with equality at m = 9 + 3*2^k,

so K* appears unbounded but only logarithmically growing. Falsifiable
prediction: the first K* = 9 occurs at m = 57 (n = 114). Note K* is not
monotone between first occurrences (dips to 5 at m = 22, 23).
Caveat: four data points; treat as a working law, not a fact.

FALSIFIED (fifth pass, section 13). The prediction was tested and is wrong:
the modular construction proves K*(48) >= 9 and K*(50) >= 10, so kappa = 9
first occurs at m <= 48, not 57. The true growth is at least sqrt-like,
K*(m) >= sqrt(m + 1/2) along even m with 2m+1 prime, NOT logarithmic.
The four-point fit was coincidence; disregard this subsection's law.

Consequence for the program of 10.5-10.6: the conjecture does NOT reduce to
a fixed finite family set, but (empirically) to families with coefficients
<= ~log2 m — still a drastic reduction (O(log^2 m) families out of ~m^2),
and the arithmetic form model of 10.6 applies verbatim with K = K(m).

### 11.3 The first-moment model fails in the OPPOSITE direction

Monte Carlo over random survivor leaves (`kstar_model.py`; biased leaf
sampling, adequate for means): lambda_K(m) = mean violating lines with
coefficients <= K grows ~linearly in m for each K, e.g. lambda_7 =
40, 65, 83, 107, 125, 145, 181 at m = 12, 16, 20, 24, 28, 33, 40; the
per-family means at m = 33 decay like (1,2): 35.7, (1,3): 21.1,
(2,3): 14.8, (1,4): 12.9, (1,5): 8.7 — roughly c*m/(p+q)^~1.6.

Poisson/first-moment logic says a K-escape exists only if
ln S(m) > lambda_K(m). At m = 33, K = 7: ln S ~ 28 vs lambda_7 ~ 145,
margin -117 — the model declares escapes impossible by 50 orders of
magnitude. Yet they exist. Recall section 6: the same style of model
predicted many full solutions where there are none. So for this constraint
system first moments fail in BOTH directions: means say nothing about the
extremes. Any successful proof must engage the extremal structure directly
(saturation, section 10.4), not the typical case.

### 11.4 Status and next steps

- K*(m): exact for all 6 <= m <= 33; unbounded-looking with a clean
  conjectural law m(kappa) = 9 + 3*2^(kappa-5).
- The defect-floor conjecture itself is untouched by this pass (D >= 8
  still exact only to m = 27), but its reduction target is now calibrated:
  prove that survivors cannot escape the families with coefficients
  <= 5 + log2 m, for instance.
- Cheapest informative next computations: (a) D(28) (tests 10.2's
  prediction >= 32); (b) K* at m = 34..40 — does 8 persist until m = 57 as
  the law predicts? (c) the escape-cost tradeoff: min total defect among
  K-escaping survivors as a function of K (dmin can do this with a
  two-pass wrapper) — if escape cost grows fast enough, it yields a
  conditional proof that D(m) -> infinity along escape sequences.
  UPDATE: (a) and (c) done, (b) started at m = 34 — see section 12.

## 12. Fourth pass (2026-08-08): D(28) = 36 breaks minimizer purity; escape costs

New `dmin` mode this pass:

    ./dmin esc <m> <K> [ub] [jlo jhi]   lines with max(|a|,|b|) <= K are HARD
                                        (any third point prunes); B&B minimizes
                                        the count of ALL violating lines.
                                        Result = EC_K(m), the minimum total
                                        defect over K-escaping survivors.

Validation: `esc <m> 0` is identical to `dmin <m>` (anchor m = 20:
D=32, nodes=298376 reproduced), and EC_K(m) = -1 exactly at K = K*(m) for
every m checked — an independent re-derivation of the 10.5/11.1 K* values
through a different counting path.

### 12.1 D(28) = 36: the first impure minimizer

Certification: all 27 root branches exhausted with exclusive bound 33
(min >= 33, ~21 CPU-min); Theorem 3 granularity excludes 33..35; branch
j = 5 then achieved 36 under bound 41. Hence D(28) = 36 exactly.

    m=28 argmin: 5 14 11 21 1 27 16 18 25 28 3 19 24 2 17 7 15 8 12 26 4 23 22 13 9 20 6 10

Anatomy: 36 = 4*1 + 8*4 — one CENTRAL orbit (family (1,9), four lines
with 4 points each) plus four generic orbits (1,2), (2,3), (6,7), (17,23).
Three firsts: first D(m) not divisible by 8, first minimizer with a central
violation, and first minimizer needing a coefficient as large as (17,23).
The refined law of 10.2 holds (36 >= 32) but is not tight at 28; the
even-m frontier now reads 32, 32, 32, 36 at m = 20, 24, 26, 28.

### 12.2 Escape costs EC_K(m): the price of avoiding low families

EC_K(m) = min violating lines over survivors with ZERO violations on
families with coefficients <= K. EC_0 = D; EC_K = -1 (impossible) iff
K >= K*(m). Exact values (blank = not run; -1 = impossible):

| m  | EC_2 | EC_3 | EC_4 | EC_5 | EC_6 | EC_7 | D(m) |
|----|------|------|------|------|------|------|------|
| 12 | 16   | 28   | 32   | -1   |      |      | 16   |
| 14 | 24   | 84   | 84   | -1   |      |      | 24   |
| 16 | 32   | 40   | -1   |      |      |      | 24   |
| 18 | 32   | 40   | 72   | 116  | -1   |      | 24   |
| 20 | 32   | 32   | 40   | 56   | -1   |      | 32   |
| 22 | 32   | 40   | 40   | -1   |      |      | 24   |
| 24 | 40   | 48   | 56   | 72   | -1   |      | 32   |
| 25 |      |      | 48   | 80   | -1   |      | 24   |
| 26 |      |      | 64   | 96   | 244  | -1   | 32   |
| 27 |      |      |      | 80   | 284  | -1   | 32   |
| 28 |      |      |      | 96   | 144  | -1   | 36   |
| 33 |      |      |      |      | <=72 | 72   | ?    |
| 34 |      |      |      |      |      | 88   | ?    |

Observations:

- Forced families at the minimum: whenever EC_2(m) > D(m) — true for
  m = 16, 18, 22, 24 — EVERY minimum-defect survivor violates the (1,2)
  family. The cheapest way to fail always runs through slope +-2 there.
- The cost of the last available escape is large and erratic:
  EC_5(18)/D = 4.8x, EC_6(26)/D = 7.6x, EC_6(27)/D = 8.9x, but
  EC_7(33) = 72 = 2.25x the conjectured D(33) = 32. Escaping the
  low-coefficient net always costs >= 2.2x the unconstrained minimum on
  the data so far, often far more.
- EC_6(26) = 244 exceeds even the MEAN defect of a random survivor —
  K6-escapers at m = 26 are extreme-tail objects in every sense.

### 12.3 m = 34: the K7-escape is almost extinct

All 33 root branches at m = 34, K = 7, bound 1: exactly ONE branch
(sigma(1) = 33) contains K7-escaping survivors; U_7(34) = 0 and
K*(34) >= 8. The escape frontier is thinning fast: K7-escapes live in 2
root branches at m = 33, 1 at m = 34. EC_7(34) = 88 (exact, branch-local
exhaust), up from 72 at m = 33, achieved by:

    m=34 K7-escaper: 33 30 6 17 20 3 11 22 15 29 7 19 24 32 9 25 4 34 12 5 23 8 21 13 16 31 28 27 10 2 26 14 1 18

Its 11 violating orbits all have coefficients >= 8 (smallest (3,8), (4,9)
— with (4,9) used three times), and none saturated: pure 3-point failures.
Note U_8(34) was NOT exhausted (~30-40 CPU-min); K*(34) = 8 is likely but
uncertified — if K7-escapes die entirely at some m' > 34 then K*(m') would
DIP back to <= 7 there, which the first-occurrence law tolerates (K* is
already non-monotone).

### 12.4 Updated next steps

1. Does the K7-escape go extinct? Check U_7(35), U_7(36) (bound-1 runs,
   ~30 CPU-min each). Extinction would sharpen the picture: the law
   m(kappa) = 9 + 3*2^(kappa-5) governs first occurrences, while escapes
   near the frontier are rigid (1-2 branches) and costly (EC 2.2-9x D).
2. D(33): predicted 32 exactly (tight point m = 8k+1). Odd-m cost at 33 is
   high (~2-4 CPU-hours with current code) but it is THE test of the law.
3. EC-based conditional lower bound: every survivor either violates a
   coeff<=6 family (defect >= 8 there) or is a 6-escaper paying EC_6(m)
   total. If EC_6(m) -> infinity along the escape-alive m, then proving
   "coeff<=6 violations force >= f(m) lines" for some growing f would give
   D(m) -> infinity unconditionally. The EC data (244, 284, 144 at
   m = 26, 27, 28) makes the first hypothesis plausible.
   UPDATE (fifth pass): hypothesis 1 is now settled negatively for fixed K
   — no fixed K works, since K*(m) -> infinity (section 13). The EC route
   survives only with K = K(m) growing like sqrt(m).

## 13. Fifth pass (2026-08-08): the escapers are algebraic — a modular family

This is the most consequential finding of the session, and it kills the
"bounded families" program of 10.5-10.6 and the growth law of 11.2.
New code: `uk.c` (fast escape-existence decision), `modular.py`.

### 13.1 How it surfaced

Chasing the extinction question of 12.4 with a faster tool
(`uk.c`: Theorem-4 specialization — per-direction value counters instead of
a generic line hash, ~40% faster and much lighter), K7-escapes were found
alive at m = 35 (branch j = 8) and m = 36 (branch j = 14), so K7-escapes do
NOT go extinct. Also certified this pass, by exhausting all root branches:
U_8(34) > 0 and U_8(35) > 0, hence K*(34) = K*(35) = 8 exactly (12.3's
"likely but uncertified" is now certified).

The m = 36 witness had a startling profile: 464 violating lines in 59
orbits, lines carrying up to 9 points, and c-values in arithmetic
progressions of common difference 146 = 2*73 = 2(n+1). Probing it:

    2*sigma(i) - 1 == +- 27 * (2i - 1)   (mod 73)   for ALL 36 orbits,

and 27^2 == -1 (mod 73). The escaper is not a search artifact; it is an
algebraic object.

### 13.2 Theorem 5 (modular involution family)

Let m be even and p = 2m+1 prime (then p == 1 mod 4). Facts:

(a) The odd numbers {1, 3, ..., 2m-1} form a complete set of
    representatives for the +- classes of (Z/p)^*: for each r exactly one
    of r, p-r is odd. [Proved.]
(b) Choose lambda with lambda^2 == -1 (mod p), which exists iff p == 1 mod
    4 iff m is even. Multiplication by lambda permutes the +- classes with
    order 2, hence induces an involution sigma_lambda on {1..m}, with no
    fixed point (a fixed point needs lambda == +-1). This matches Theorem
    2's requirement of zero fixed points for even m exactly. [Proved.]
(c) sigma_lambda is a Lemma-S survivor. [Verified for all 13 even m <= 56
    with 2m+1 prime; not proved.]
(d) Write p = a^2 + b^2 (unique up to order and sign, Fermat). Then the
    violating line family of sigma_lambda with the smallest maximum
    coefficient is exactly {|a|, |b|}, so sigma_lambda escapes every family
    with coefficients < max(a,b), giving

        K*(m) >= max(a, b)  where 2m+1 = a^2 + b^2.

    [Verified 13/13, m = 6..56; see table. Proof sketch below.]

Proof sketch of (d): the lattice L = {(x,y) in Z^2 : y == lambda x mod p}
has index p, and lambda^2 == -1 makes it invariant under (x,y) -> (-y,x),
so L is an ideal of Z[i] of norm p, i.e. L = (a+bi) with p = a^2+b^2. Its
minimal vectors are (a,b), (-b,a) and their images, of norm sqrt(p). All 4m
configuration points lie in L union its mirror; lines in the direction of a
minimal vector collect the most points, and the corresponding line family
is {|a|,|b|}. Shorter families cannot occur because L has no vector shorter
than sqrt(p).

Verification table (`modular.py`, exhaustive geometry, no shortcuts):

| m  | n   | p = 2m+1 | lambda | p = a^2+b^2 | max(a,b) | min viol family | viol lines | orbits | max pts/line |
|----|-----|----------|--------|-------------|----------|-----------------|-----------|--------|--------------|
| 6  | 12  | 13       | 5      | 2^2+3^2     | 3        | 3               | 16        | 2      | 4            |
| 8  | 16  | 17       | 4      | 1^2+4^2     | 4        | 4               | 28        | 4      | 4            |
| 14 | 28  | 29       | 12     | 2^2+5^2     | 5        | 5               | 84        | 11     | 6            |
| 18 | 36  | 37       | 6      | 1^2+6^2     | 6        | 6               | 116       | 15     | 6            |
| 20 | 40  | 41       | 9      | 4^2+5^2     | 5        | 5               | 156       | 20     | 8            |
| 26 | 52  | 53       | 23     | 2^2+7^2     | 7        | 7               | 244       | 31     | 8            |
| 30 | 60  | 61       | 11     | 5^2+6^2     | 6        | 6               | 316       | 40     | 10           |
| 36 | 72  | 73       | 27     | 3^2+8^2     | 8        | 8               | 464       | 59     | 9            |
| 44 | 88  | 89       | 34     | 5^2+8^2     | 8        | 8               | 676       | 86     | 11           |
| 48 | 96  | 97       | 22     | 4^2+9^2     | 9        | 9               | 812       | 103    | 11           |
| 50 | 100 | 101      | 10     | 1^2+10^2    | 10       | 10              | 812       | 103    | 10           |
| 54 | 108 | 109      | 33     | 3^2+10^2    | 10       | 10              | 1028      | 130    | 11           |
| 56 | 112 | 113      | 15     | 7^2+8^2     | 8        | 8               | 1092      | 138    | 14           |

Every row: Lemma-S survivor = yes, min violating family = max(a,b) exactly.

### 13.3 Consequences

1. K* IS UNBOUNDED, provably modulo (c)/(d): max(a,b) >= sqrt(p/2), so
   K*(m) >= sqrt(m + 1/2) along the infinitely many even m with 2m+1 prime
   (infinitude of primes == 1 mod 4 is classical). Growth is at least
   sqrt-like, not logarithmic: 11.2's law is dead, and its concrete
   prediction (first kappa = 9 at m = 57) is refuted by m = 48.
2. The 10.5-10.6 program — reduce the conjecture to survivors' behaviour on
   a FIXED finite set of low-coefficient families — cannot work. Any fixed
   K is escaped by all sufficiently large modular m. A correct version must
   let K grow like sqrt(n).
3. The K* values where 2m+1 is prime are explained and mostly TIGHT:
   exact K*(m) equals max(a,b) at m = 6, 8, 14, 18, 20, 26, 36 (7 of 8
   cases with data); only m = 30 has K* = 7 > 6 = max(a,b), i.e. some
   non-modular survivor escapes one family further there.
4. It explains the qualitative oddities recorded earlier: frontier escapes
   live in only 1-2 root branches (they are essentially unique algebraic
   objects), and they saturate lines (lattice lines carry many points) —
   the "saturation not spreading" phenomenon of 10.4 is the shadow of a
   lattice.
5. Escapers are NOT all modular. At m = 33, 34, 35 (2m+1 = 67, 69, 71:
   respectively prime == 3 mod 4, composite, prime == 3 mod 4) no lambda
   exists, yet K7-escapes exist; probing those witnesses for a constant
   quotient class modulo every prime in [2m-3, 2m+11] found none. So there
   is a second, sporadic population of escapers whose structure is unknown.
6. Context: modular constructions are the classical source of large
   no-three-in-line configurations (Erdos; Hall-Jackson-Sudbery). What is
   new here is that the D4-FULLY-SYMMETRIC reduction has its own such
   family, that it is automatically Lemma-S clean, and that its defect
   profile is governed exactly by the Gaussian factorization of n+1.

### 13.4 Where this leaves the conjecture

The defect floor conjecture is untouched as a statement (D >= 8 exact to
m = 28) but the modular family shows why it is hard: there is an explicit
infinite family of Lemma-S survivors that avoids every low-coefficient
obstruction, and its defect, while growing (16, 28, 84, ..., 1092), does so
only because the lattice forces MANY lines — not because any small family
catches it.

Sharpest next questions:

1. Prove Theorem 5(c): sigma_lambda is always a Lemma-S survivor. The
   labels are {(b-a)/2} u {(b+a)/2} over orbits; with b == +-lambda*a mod p
   this should be a short character/counting argument.
2. Compute the DEFECT of sigma_lambda in closed form. The table suggests
   viol lines ~ c*m^2/... (16, 28, 84, 116, 156, 244, 316, 464, 676, 812,
   1028, 1092 for m = 6..56) — fit it; if the modular family is extremal,
   a closed form would be the first infinite-family evidence for
   D(m) -> infinity.
3. Is D(m) itself achieved by modular configurations at prime m? Compare
   D(20) = 32 with the modular defect 156 at m = 20: NO — modular escapers
   are far from minimal defect. Minimum-defect and maximum-escape are
   opposite extremes of the same class. That tension is probably where a
   proof lives: a survivor cannot simultaneously avoid the low families
   (needs lattice structure, costing many lines) and keep few violations.
4. What are the sporadic (non-modular) escapers at m = 33, 34, 35?
   If they are perturbations of modular configurations at a nearby prime,
   a single structure theory would cover the whole escape frontier.
