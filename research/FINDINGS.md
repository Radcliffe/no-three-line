# Finding optimal no-three-in-line configurations with rot4 symmetry

Research snapshot: August 8, 2026.

## Scope and current target

The ordinary no-three-in-line problem asks for the largest subset of an
`n × n` integer grid containing no collinear triple. Since each row contains
at most two selected points, `2n` is an upper bound. Finding a valid `2n`-point
configuration therefore proves optimality without a separate optimization
run.

The public database updated July 21, 2026 lists `n=74` as the largest known
configuration, in symmetry class `rot4`. It contains no `n=76` solution, so
`n=76` is the next even record target at the time of this snapshot [1].

True quarter-turn symmetry cannot give `2n` points when `n` is odd. Off-center
orbits have size four and the center orbit has size one, while `2n` is two
modulo four. Odd record searches instead use the modified `rct4` class.

## The quotient 2-factor formulation

Let `n = 2m`, and let

```text
rho(r, c) = (c, n - 1 - r)
```

be a quarter turn. Every cell orbit meets the top-left `m × m` quadrant once.
The representative `(i, j)` expands to

```text
(i, j)
(j, n - 1 - i)
(n - 1 - i, n - 1 - j)
(n - 1 - j, i).
```

Associate `(i, j)` with a directed arc `i -> j` on vertices
`0, ..., m - 1`. When `i != j`, its orbit contributes one point to row `i`
and one to row `j` in the top/bottom row pair. A loop `(i, i)` contributes two
points to that row pair. Thus a `2n`-point rot4 configuration is exactly a set
of `m` arcs satisfying

```text
2 y[v,v] + sum(j != v) (y[v,j] + y[j,v]) = 2
```

for every `v`. Ignoring arc directions, the result is a degree-two multigraph:
its components are loops, digons formed by both opposite arcs, and cycles of
length at least three. Arc directions still matter geometrically, because
`(i,j)` and `(j,i)` are different quarter-turn orbits.

This is related to the general row-column cycle decomposition described by
Flammenkamp and Prellberg [2], but it specializes the structure to rot4 orbit
variables and supplies degree-preserving neighborhoods for search. The
published CP-SAT model contains equivalent row equations but searches Boolean
orbit assignments rather than making the factor itself the state [3,4].

### Search-space effect

For `n=76`, `m=38`. There are `m²=1,444` orbit variables and exactly 38 must be
selected. The unrestricted fixed-cardinality space has

```text
choose(1444, 38) ~= 10^75.132
```

candidates. Counting labeled oriented 2-factors gives approximately
`10^55.062` candidates. A structural generator therefore removes about
`10^20` fixed-cardinality assignments that fail the row equations.

This does not magically reduce the logical model by that factor: a strong
cardinality solver propagates the same equations. It matters most for local
search, Monte Carlo search, custom branching, and large-neighborhood repair,
because those methods never spend an iteration outside the row-perfect space.

### Why not use a permutation?

Requiring one incoming and one outgoing arc at every quotient vertex would
make the top-left quadrant a permutation matrix. Under rot4, all four
quadrants would then be permutation matrices. The four-corner permutation
conjecture says this is impossible beyond the known small exceptions, and it
has been computationally checked through the stated range [5]. The catalog
measurements below also show that known large solutions mix balanced vertices
with sources and sinks. A permutation-only formulation is therefore an
attractive but likely empty subproblem.

## Measurements on known rot4 solutions

`analyze-rot4-factors.js` was run on the complete catalog files for
`n=44,48,52,54,56` available from the public database [6].

| n | Catalog entries | One component | Contains a loop | Mean balanced vertices |
|---:|---:|---:|---:|---:|
| 44 | 1,016 | 20.28% | 49.51% | 46.74% |
| 48 | 2,124 | 17.70% | 53.53% | 47.37% |
| 52 | 5,062 | 17.36% | 53.54% | 46.95% |
| 54 | 7,696 | 17.06% | 52.14% | 47.05% |
| 56 | 10,441 | 16.49% | 51.40% | 46.99% |

Here “one component” means a Hamiltonian quotient cycle. “Balanced” means one
incoming and one outgoing selected arc at a vertex.

Consequences:

1. A Hamiltonian-cycle search is a useful fast lane, retaining roughly one in
   six cataloged solutions at these sizes.
2. A production search must also support cycle split/merge and loop moves.
3. Arc orientations look broadly mixed; forcing coherent cycle orientations
   discards too much of the observed solution space.

The single bundled representatives for `n=44` through `74` have a mean of
2.125 quotient components, and their largest component contains about 87.6%
of the quotient vertices on average. This suggests prioritizing a giant cycle
plus a small number of short components, without making it a hard constraint.

## Reduced line-hypergraph structure at n=76

After identifying quarter-turn-equivalent line inequalities by their orbit
incidence vector, the enumeration in `rot4-lazy-z3.py` finds:

```text
orbit variables                              1,444
distinct reduced line-incidence inequalities 352,122
mean inequality arity                           3.801
arity-three inequalities                     228,381
inequalities containing a coefficient two        687
```

Thirty-eight of the long inequalities are row inequalities and can be
replaced by the quotient degree equalities. Most constraints are therefore
small. An orbit-aware SAT encoding should use direct clauses for the common
arity-three case and compact at-most-two encodings only for longer lines.

The coefficient of an orbit on a line is at most two. A coefficient-two orbit
and any coefficient-one orbit on the same line form a binary conflict. Lines
with all coefficients one give ordinary at-most-two hyperedges.

## Prototype experiments

These are exploratory single-machine measurements, not controlled performance
claims. The random seed, compiler, and exact command should be recorded in any
future comparison. Every reported solution code was checked independently
with `configuration-codec.js` and `LineIndex`.

### Factor-preserving local search

`rot4-factor-search.cpp` starts from a random Hamiltonian quotient cycle. Its
neighborhood contains:

- reversal of a directed arc while retaining its undirected edge;
- a two-edge switch that reconnects four endpoints and may split or merge
  cycles;
- stochastic acceptance with periodic reheating;
- bias toward arcs participating in collinear triples;
- independent threads with different seeds.

The energy is the exact number of selected collinear triples. It is updated by
temporarily adding or removing the four points of an orbit and grouping the
normalized directions from each changed point to the other selected points.

Observed behavior included:

- valid, independently checked rot4 solutions for `n=20`, `24`, and `30`;
- one `n=30` run solving in under one second, while another five-second run
  stopped at energy four;
- an `n=44` five-second, eight-thread run reducing mean initial energy 186 to
  a best energy of 12;
- an `n=76` twenty-second, eight-thread run reaching energy 44 from a random
  seed.

The variance is the important result: the search has useful neighborhoods but
strong heavy tails. Constraint weighting, loop/digon moves, three-edge
reconnection, and exact repair should be added before spending large compute
budgets.

### Factor lifting from n=74 to n=76

Adding one quotient vertex permits row-perfect lifts of the bundled `n=74`
factor by:

- adding a loop on the new vertex;
- replacing an old loop by a digon with the new vertex;
- subdividing a non-loop cycle edge through the new vertex, with four choices
  of arc directions.

There are 146 such one-vertex lifts for the bundled solution. The deterministic
experiment in `evaluate-factor-lifts.js` found:

```text
best lifted seed                         260 triples
lifted-seed median                       308 triples
lifted-seed mean                         about 306 triples
random Hamiltonian seeds sampled       1,000
random minimum                           280 triples
random median                            444 triples
random mean                              about 450 triples
lifts below the random sample minimum    about 4.8%
```

Lifting clearly improves typical initial energy: its median is 136 triples
below the random Hamiltonian median. In one equal-time local-search
comparison, however, a lifted seed reached energy 56 and a random seed reached
44. Lifting is therefore useful for portfolio diversity, not sufficient as a
standalone search strategy. This differs from simply embedding all old board
points into a larger board, a warm-start strategy reported to stall in the
CP-SAT experiments [3].

### Lazy exact solving

`rot4-lazy-z3.py` initially asserts only the quotient degree equalities. It
then repeats:

1. request a complete oriented 2-factor;
2. find its actually violated geometric lines;
3. construct the full orbit-incidence inequality for each such line;
4. add previously unseen inequalities and solve again.

With deterministic seed 1:

| n | Result | Time | Candidate models | Distinct cuts |
|---:|---|---:|---:|---:|
| 20 | solved | 0.22 s | 60 | 323 |
| 24 | solved | 3.34 s | 133 | 783 |
| 30 | best eight bad lines | 30 s cutoff | 210 | 1,786 |

Lazy generation saves model construction and can expose a small conflict core,
but the unstructured succession of complete factors begins to plateau by
`n=30`. The stronger use is inside large-neighborhood search, where most of a
good incumbent is fixed and lazy cuts repair only a conflict neighborhood.

## Evaluation of approaches

### 1. Factor-space local search plus exact large-neighborhood repair

**Priority: highest.**

Maintain a complete oriented 2-factor at all times. When local search stalls,
collect vertices belonging to high-weight violated lines, unfreeze their
incident arcs plus a randomized halo, and solve the residual degree and line
constraints exactly. Run several neighborhood sizes in parallel.

This combines the cheap motion of local search with clause learning where it
is most useful. It also avoids asking an exact solver to rediscover the entire
factor after each restart.

### 2. Factor-aware native SAT and cube-and-conquer

**Priority: high.**

Use Boolean arc variables, native encodings of the degree-two constraints,
direct small line clauses, and compact cardinality encodings for long lines.
Branch on quotient vertices with the smallest residual degree domain. Partition
large runs by a short prefix of cycle construction or by a partial cycle
skeleton, then solve cubes independently.

SAT has already produced the `n=70` and `n=72` records [1]. For a construction,
an independently checked model suffices because `2n` is the elementary upper
bound. For an unsatisfiability claim, use proof-producing solvers and retain
checkable DRAT/LRAT-style certificates.

### 3. GPU factor local search

**Priority: medium-high.**

Batch thousands of oriented factors. The quotient state is small, and
candidate flips and switches can be scored independently. Use breakout or
dynamic clause weights rather than plain unweighted annealing. GPU code has
already been effective for enumeration and record searches in this problem
[1], although the available public descriptions do not give enough detail to
reproduce the newest implementation.

### 4. Factor lifting and catalog-derived priors

**Priority: medium, as initialization only.**

Use all available `n-2` factors, not just the bundled representative, and
generate loop, digon, subdivision, and small cycle-surgery lifts. Preserve a
diverse pool by cycle type and line-slope profile. The measured initial-energy
advantage justifies inclusion, but existing CP-SAT experiments caution against
overly strong warm-start commitment [3].

### 5. Lazy global constraint generation

**Priority: medium-low alone; useful inside repair.**

The prototype is exact and simple but learns constraints reactively and loses
momentum by `n=30`. It should be combined with incumbents, assumptions, and
neighborhood fixing rather than scaled directly to `n=76`.

### 6. Transformer, PPO, and direct MCTS approaches

**Priority: low for the exact `2n` target.**

The reported transformer and PPO experiments reached optimal configurations
only through `n=14` and `n=10`, respectively [7]. Geometry-aware MCTS scales to
larger boards and obtains roughly `1.8n` points, but that remains below the
`2n` feasibility cliff needed here [8]. MCTS rollout scores or learned arc
priors may help choose factor moves, but replacing the exact repair layer with
these methods is not supported by current evidence.

## Implemented next stage

The recommended hybrid stage is now represented by executable research code:

1. `rot4-factor-search.cpp` maintains canonical line multiplicities, exact
   triple energy, and persistent breakout weights incrementally. It no longer
   has to reconstruct all selected triples after a factor move.
2. Its reversible neighborhood contains arc flips, two-edge switches,
   loop-to-cycle splicing and collapse, and three-edge reconnection. Two-edge
   switches create and remove digons, so loops, digons, and ordinary cycles are
   all reachable component types.
3. Both exact backends free a greedy vertex cover of the incumbent's violated
   lines, a random halo, and a configurable minimum quotient fraction.
   `rot4-sat-repair.py` fixes outside arcs with native SAT assumptions and uses
   unsatisfiable cores to choose expansions. `rot4-lazy-z3.py` retains the
   pseudo-Boolean reference implementation.
4. Search workers mix Hamiltonian and general random 2-factors. With
   `--lift-from`, all one-vertex lifts are scored and retained in each worker's
   restart pool. Global near-misses are published with timestamps and adopted
   by other workers after perturbation.
5. `benchmark-factor-search.py` records every global-best event and reports
   time-to-zero distributions and censored energy curves across deterministic
   seed ranges.
6. `validate-rot4-code.js` verifies every claimed solution with a standalone
   brute-force line calculation and again with the application's independent
   `LineIndex`. Both the hybrid runner and benchmark harness call it
   automatically for zero-energy outputs.

Initial integration smoke tests illustrate the intended division of labor:

| n | Local phase | Repair phase | Outcome |
|---:|---|---|---|
| 20 | seed 10, 1 s, one thread: energy 4 | 0.30 s, eight free quotient vertices | solved and dual-validated |
| 30 | seed 2, 1 s, one thread: energy 28 | 10 s, neighborhood expanded from 8 to 10 vertices | energy 8 |

These are functional checks, not comparative benchmarks. Controlled seed
portfolios remain necessary because the local and exact phases are both
heavy-tailed.

As a harness smoke test, five local-search runs at `n=20` used seeds 20–24,
two threads, and a three-second cutoff. Two solved, the median final energy was
four, and the two observed times to zero were 23 ms and 2,342 ms. The wide
spread is precisely why the harness retains censored runs and reports curves
instead of only successful timings.

### Native incremental SAT stage

`rot4-sat-repair.py` implements the next performance step through PySAT [9].
It uses the original low-level SAT engines through a common incremental API:

- quotient degree equations use sequential-counter CNF, with a loop literal
  selecting between degree zero and degree two among the other incident arcs;
- all-coefficient-one line cuts of small arity become direct ternary clauses,
  while longer cuts use sequential at-most-two counters;
- an orbit with coefficient two conflicts through binary clauses with every
  other orbit on its line;
- fixed arcs are passed as assumptions rather than permanent unit clauses;
- an unsatisfiable assumption core scores which quotient vertices should be
  freed next, while learned clauses remain in the same solver instance.

`test-sat-encoding.py` exhaustively checks all 512 assignments at `n=6` and
confirms that the CNF degree equations exactly match the quotient equation.
Repeating the check with a coefficient-two diagonal cut and an all-one ternary
cut confirms both specialized line encodings as well.

Single-incumbent comparisons, using identical neighborhoods and seeds, gave:

| n | Initial energy | Limit | Native SAT | Z3 reference |
|---:|---:|---:|---|---|
| 20 | 4 | 1 s | solved in 0.039 s | solved in 0.25 s |
| 30 | 28 | 5 s | energy 4 | energy 8 |
| 76 | 152 | 5 s | energy 124 with Glucose 4.2 | energy 152 |

The resulting `n=20` codes were dual-validated. The `n=30` and `n=76`
near-miss energies were also recomputed independently and their violating-line
counts agreed with the application's `LineIndex`. These remain exploratory
single-seed results; `benchmark-repair-backends.py` now supports controlled
comparisons over arbitrary incumbent sets.

CaDiCaL 1.9.5 was fastest in the small repair, while Glucose 4.2 made more
progress in the short `n=76` run. Kissat is excluded: its PySAT interface does
not honor assumptions [9]. `run-hybrid-search.py --repair-backend portfolio`
runs native SAT and Z3 concurrently; `--sat-solver` selects the SAT engine,
and the optional SBVA worker described below adds a third trajectory.

### Linear line incidence and structured reencoding

Two subsequent performance experiments target CNF construction and solver
trajectory separately.

First, a reduced line incidence no longer scans all `n²` cells. For a
canonical equation `a x + b y + c = 0`, it scans the `n` rows and solves for
the one possible integral column (with a direct horizontal-line case). The
test harness compares this enumerator with the old brute-force definition on
all 938 distinct lines induced by pairs of cells at `n=8`. On the 148 initial
cuts of a representative `n=76` incumbent, repeated timings fell
from 28.10 ms to 1.64 ms per batch, a 17.2× construction speedup.

Second, the native backend can run the installed Structured Bounded Variable
Addition preprocessor before its first solve. SBVA introduces auxiliary
variables to expose useful structure and may reduce clauses, but its authors
emphasize that its gains are not explained by formula size alone [10]. The
integration preserves original arc identifiers, allocates later sequential-
counter variables above the transformed range, charges preprocessing to the
same time limit, and reports all size changes. Exhaustively fixing all 512
original assignments at `n=6` produced the same answers before and after SBVA.

The observed effect is complementary rather than uniformly faster:

| Case | Raw SAT | SBVA+SAT | Z3 | SBVA size change |
|---|---:|---:|---:|---|
| `n=30`, initial energy 20, seed 30, 3 s | 4 | 8 | 12 | 1,867 vars / 3,741 clauses unchanged |
| `n=76`, initial energy 148, three seeds, 3 s mean | 137.3 | 136.0 | 148.0 | 13,838 vars / 28,350 clauses to 13,849 / 28,337 |

For the three `n=76` seeds, raw SAT won once, SBVA+SAT won once, and they tied
once; their mean measured wall times were 3.196 s and 3.176 s. A five-second
seed-76 run reached energy 112 with SBVA versus 144 raw. Solver interruption
is cooperative, so the actual wall times (5.16 s and 6.10 s in that trial),
not only the requested limits, are retained when interpreting results.

Raising the direct-clause threshold exposed more structure—SBVA removed 47
clauses at threshold 8 and 161 at threshold 10—but worsened seed-76 energy to
132 and 136 versus 112 at the normal threshold. Clause reduction alone is
therefore not a suitable selection rule. SBVA remains opt-in. When
`--repair-backend portfolio` and `--sat-sbva` are combined, the hybrid runner
now launches raw SAT, SBVA+SAT, and Z3 concurrently and keeps the best result.

These mixed results motivate the controlled CaDiCaL/Glucose/raw/SBVA portfolio
over independently generated incumbents below.

### Multi-solver SAT portfolio

The hybrid runner and comparison harness now accept repeated `--sat-solver`
arguments. In portfolio mode, each requested engine is run both raw and with
SBVA when `--sat-sbva` is supplied; Z3 remains a reference worker in the
end-to-end runner. Backend names retain the engine, such as
`sat-cadical195-sbva`, so results cannot be conflated. The controlled harness
can read `benchmark-factor-search.py` JSON directly and reports both individual
backend statistics and the best result a concurrent portfolio would retain.

An independent experiment generated three `n=76` incumbents with two-second,
single-thread local searches at seeds 80–82. Their energies were 120, 148, and
156. Repair used unrelated seeds 180–182 and three nominal seconds per backend,
running variants sequentially to avoid CPU contention:

| Backend | Energies | Mean | Unique wins |
|---|---|---:|---:|
| CaDiCaL | 120, 140, 156 | 138.7 | 0 |
| CaDiCaL + SBVA | 120, 140, 156 | 138.7 | 0 |
| Glucose | 120, 144, 156 | 140.0 | 0 |
| Glucose + SBVA | 120, 128, 156 | 134.7 | 1 |

All four tied twice; Glucose+SBVA uniquely improved the middle incumbent from
148 to 128. Mean measured wall times were tightly grouped between 3.158 and
3.183 seconds. This small sample favors Glucose+SBVA but does not justify
discarding raw SAT: the earlier matched experiment contained a raw-SAT win.
The actionable conclusion is to spend spare cores on solver/reencoding
diversity rather than select a backend from clause reduction alone. Exact
incumbents and results are recorded in
`benchmarks/sat-portfolio-2026-08-07.json`.

### Global UNSAT proof boundary

Proof capture is now explicitly separated from neighborhood repair. An UNSAT
call with fixed outside arcs certifies only that neighborhood and never writes
a global artifact. The solver now retains the original CNF while SBVA replaces
only the search solver; subsequent lazy cuts are added to both formulas. This
allows preprocessing to guide neighborhood discovery without making SBVA's
transformation part of the trusted proof chain.

There are three global routes. The basic fallback discards the transformed
solver, rebuilds Glucose 4.2 from the retained original clauses, and emits text
DRUP. The command-line CaDiCaL route independently re-solves the original CNF
with proof-producing bounded variable addition (`--factor`) [13]. Exit code 20,
the exact `s UNSATISFIABLE` marker, and a nonempty proof are all required.

The new in-process route creates a CaDiCaL 3.0.1 shadow before SBVA and starts
binary proof tracing before importing any clause. Initial clauses are loaded
in one batch; every later lazy cut is sent both to the transformed search
solver, the retained Python clause list, and the shadow. The C++ bridge
explicitly declares every incoming variable range so CaDiCaL's bounded
variable addition cannot collide with later user variables. At the global
boundary, it only needs to call `solve`: there is no solver process startup or
DIMACS parse. A C++ deadline terminator returns UNKNOWN safely. SAT, timeout,
bridge error, or missing trace is retained as a diagnostic failure and cannot
become a global claim. The command-line and library routes remain independent
options and emit byte-identical DRAT on the regression.

`check-unsat-trace.py` checks every added proof clause by asking a second SAT
engine whether its negation is inconsistent with the accumulated formula.
Ignoring deletion lines is sound because it retains a stronger collection of
already validated clauses. The regression formula emits seven Glucose proof
additions, all accepted by CaDiCaL, and the artifact API refuses a nonempty
assumption list. This is a semantic cross-solver checker rather than a fast
formally verified DRAT implementation; large publication-grade artifacts
should also be processed by a dedicated checker.

The artifact writer can now invoke the official `drat-trim` implementation
directly [11]. Success requires both exit code zero and an `s VERIFIED` marker;
otherwise the command fails but preserves the CNF, trace, and metadata for
diagnosis. Metadata records the checker path, SHA-256 binary hash, elapsed
time, exit status, and bounded output. The official source was built at commit
`2e3b2dc0ecf938addbd779d42877b6ed69d9a985`. It accepted the seven-line
Glucose trace and returned `NOT VERIFIED` with a nonzero exit status for a
deliberately corrupt trace.

The verified DRUP trace can now be converted to LRAT in the same `drat-trim`
run and passed to a second checker. The 13-line regression certificate was
accepted by both the C `lrat-check` bundled with `drat-trim` and CakeLPR [12].
CakeLPR was built from the official ARMv8 assembly at commit
`a36874a8b750b43fe4b385b8ddbf5b033e46a3fa`; that assembly is generated from
the formally verified CakeML/HOL4 checker. Both checkers rejected a certificate
with its final line removed. CakeLPR nevertheless returned process status zero
for that negative case, so the integration requires its exact
`s VERIFIED UNSAT` marker rather than accepting exit status alone. Exact
sources, hashes, markers, and negative-test results are retained in
`benchmarks/proof-checker-2026-08-07.json`.

The full discovery-to-certification regression now starts from an SBVA formula
with 64 clauses while retaining the original 70 clauses. The transformed
solver reports UNSAT; CaDiCaL re-solves the original, emits a 46-byte binary
DRAT trace, `drat-trim` verifies and converts it, and CakeLPR accepts the LRAT.
A separate SAT original formula is deliberately sent to the artifact writer;
CaDiCaL returns SAT and the writer refuses certification. This exercises the
most important mismatch failure, not merely the successful path.

On a larger structured regression (9 pigeons, 8 holes), CaDiCaL factorization
reduced mean process proof-production time over ten warm-cache runs from
0.319634 to 0.015753 seconds, a 20.290x speedup. The deterministic binary proof
shrunk from 1,665,899 to 67,949 bytes, a ratio of 0.041. The in-process shadow
then reduced the final solve boundary to 0.012135 seconds, 1.298x faster than
the process route; charging its 0.000788-second one-time setup still gives a
1.219x improvement. Every proof was accepted by `drat-trim`, and the command
and library traces had the same SHA-256 hash. This confirms that certified
variable addition and in-process synchronization can pay for themselves on
the intended kind of cardinality-heavy formula, but it is not an `n=76`
performance result. Exact runs are in
`benchmarks/cadical-proof-preprocessing-2026-08-07.json`.

### Buffered proof-shadow synchronization

The next experiment removed a Python-to-C call pattern left in the first
in-process implementation. Although the bridge accepted flat clause batches,
direct small line encodings still called it once per clause. The retained
original CNF now serves as the queue: an integer cursor records the clauses
already mirrored by the shadow. Three policies remain available for controlled
comparison:

- `eager` mirrors every clause or counter batch and reproduces the old path;
- `candidate` flushes once after all cuts from one SAT candidate;
- `deferred`, now the default, flushes once immediately before global proof
  production.

All search clauses continue to enter both the active solver and retained
original CNF immediately. Deferral affects only the dormant proof shadow. The
artifact writer flushes the cursor before calling CaDiCaL, so the certified
formula is unchanged. The exhaustive test gives all three policies the same
CNF. A live deferred regression queued 22 clauses, flushed to 70 total clauses
at the proof boundary, and produced the same 46-byte CaDiCaL proof artifact.

A controlled `n=76` clause-stream benchmark used the three independently
generated near-misses at energies 120, 148, and 156 from the SAT portfolio.
Their 406 violating geometric lines reduced to 102 distinct orbit-incidence
cuts and 8,969 added CNF clauses. Twenty-one repetitions were interleaved
across modes on CaDiCaL 3.0.1:

| Synchronization | Median bridge calls | Median shadow-add time | Median complete update |
|---|---:|---:|---:|
| no shadow | 0 | 0 ms | 22.208 ms |
| eager | 1,072 | 9.962 ms | 32.179 ms |
| per candidate | 3 | 6.167 ms | 28.644 ms |
| proof boundary | 1 | 4.646 ms | 28.509 ms |

Thus proof-boundary batching reduced calls by 1,072x, shadow-add time by 2.14x,
and the full cut-update time by 1.13x relative to eager synchronization. Three
matched repair regressions, capped at three seconds and stopped at the first
UNSAT neighborhood, produced identical candidate counts, cut counts, and
energies in all modes. Their median process wall time fell from 0.298 seconds
eager to 0.280 seconds deferred, a 1.06x improvement. The sample is too small
for a general runtime claim, but it verifies that buffering does not perturb
the solver trajectory and removes unnecessary work when a repair terminates
without reaching the global certification boundary. Exact interleaved runs,
codes, hashes, and instrumentation are in
`benchmarks/shadow-sync-2026-08-07.json`.

### Exact conflict covers and neighborhood diversity

Every initially violated line must contain a selected arc incident to at least
one free quotient vertex. Otherwise all three or more points on that line stay
fixed and the repair neighborhood is immediately UNSAT. Initial-neighborhood
selection is therefore a small hitting-set problem on 38 vertices, with one
hyperedge per violated line.

The original initializer used a deterministic greedy cover, then added a
two-vertex random halo. Three alternatives are now selectable: greedy ties
broken by total conflict count, randomized greedy ties, and an exact minimum
cover. The exact path encodes every conflict hyperedge as a clause over 38
temporary vertex variables and tries sequential-cardinality upper bounds from
a counting lower bound through the greedy cover size. Randomly permuting the
temporary variable identifiers gives deterministic seed-controlled diversity
among multiple minimum covers. This optimizer affects only neighborhood
selection; it is not part of the geometric SAT model or any proof claim.

UNSAT-core expansion was separated at the same time. The old `score` rule
ranks vertices by raw occurrences as endpoints of core arc assumptions. A new
`marginal` rule greedily maximizes newly covered core assumptions, while
`random` is a baseline. Cover construction, halo selection, core expansion,
and lazy-cut shuffling can use four split random streams. This prevents a
policy's random-number consumption from silently changing either the halo or
the later clause order in matched experiments.

A one-second Glucose pilot crossed all four initial covers with all three core
rules on the earlier energy-120, 148, and 156 incumbents. Across the four
initial-cover variants, raw scoring improved one of 12 runs and reduced energy
by 1.0 point on average, marginal coverage improved two and reduced by 2.67,
and random expansion improved one and reduced by 1.67. The contradictory tiny
sample is retained as a warning rather than used to choose a rule.

The broader comparison generated eight fresh `n=76` incumbents with two-second,
single-thread local searches at seeds 90 through 97. Initial energies were 160,
168, 140, 176, 164, 164, 136, and 164. Each Glucose repair then received two
seconds with seed 480 through 487:

| Initial cover | Mean cover size | Final energies | Mean improvement |
|---|---:|---|---:|
| deterministic greedy | 7.500 | 160, 160, 140, 172, 164, 160, 136, 144 | 4.5 |
| conflict-tie greedy | 7.625 | 160, 164, 140, 152, 164, 156, 124, 164 | 6.0 |
| randomized greedy | 7.375 | 160, 164, 128, 136, 160, 124, 136, 164 | 12.5 |
| exact minimum | 6.625 | 132, 168, 140, 168, 160, 160, 136, 148 | 7.5 |

Exact cover construction took 16.9 ms on average and at most 38.5 ms. Its
smaller neighborhood was useful but not dominant: randomized greedy was the
best single Glucose lane. CaDiCaL changed the ranking again, with mean
improvements of 11.5 for deterministic greedy, 9.5 for exact minimum, and 5.5
for randomized greedy. Pooling both solvers leaves the three policies close:
mean improvements are 8.0, 8.5, and 9.0 for deterministic, minimum, and
randomized covers, respectively. The operative result is solver-dependent
diversity, not a universal replacement for greedy cover.

The eight-incumbent core-policy cross used the two stronger cover lanes. Raw
score improved energy by 10.0 points on average across their 16 runs, random
expansion by 7.25, and marginal coverage by 5.75. Raw scoring therefore remains
the default despite the marginal rule's appealing set-cover interpretation.

The cover variants remain complementary. On the Glucose experiment, a
two-worker exact-minimum plus randomized-greedy portfolio improved energy by
18.0 points on average and ended at mean energy 141.0. Keeping all four cover
lanes improved by 20.5 and ended at 138.5, compared with 4.5 and 154.5 for the
old single greedy lane. `run-hybrid-search.py` now accepts repeated
`--sat-initial-cover-policy` options and names each worker separately. Exact
runs, independently checked codes, expansions, cores, and solver statistics
are retained in `benchmarks/neighborhood-policy-pilot-2026-08-07.json`,
`benchmarks/neighborhood-policy-glucose-2026-08-07.json`, and
`benchmarks/neighborhood-policy-cadical-2026-08-07.json`; the expanded core
comparison is in `benchmarks/neighborhood-policy-core-2026-08-07.json`.

### Halo size and core-expansion width

The initial cover fixes which incumbent conflicts may change. The random halo
adds unconstrained quotient vertices beyond that cover, and each UNSAT core
then expands the free set by a fixed width. Both parameters trade a smaller,
easier SAT neighborhood against the ability to escape the incumbent's local
basin.

The size benchmark crosses exact-minimum and randomized-greedy covers while
holding raw core scoring fixed. It supports either a complete halo/width grid
or explicit `HALO:EXPAND` pairs, uses the four split random streams, and dual-
validates every emitted near-miss. A one-second, three-incumbent pilot tested
all 18 combinations for halos 0, 2, and 4 and widths 1, 2, and 4. It favored
randomized greedy with halo 0 and width 2, at mean energy 130.67. The result did
not survive the broader sample, another warning against tuning on three heavy-
tailed runs.

The confirmation used the eight fresh incumbents above, two seconds per
Glucose lane, and repair seeds 780 through 787. The strongest individual
settings were:

| Solver | Cover | Halo | Width | Mean final energy | Mean improvement |
|---|---|---:|---:|---:|---:|
| Glucose | exact minimum | 4 | 2 | 143.5 | 15.5 |
| Glucose | randomized greedy | 2 | 2 | 146.0 | 13.0 |
| CaDiCaL | randomized greedy | 4 | 2 | 150.0 | 9.0 |
| CaDiCaL | exact minimum | 0 | 4 | 151.5 | 7.5 |

The Glucose tail lane using randomized greedy, halo 0, and width 4 was weak on
average at energy 153.0, but uniquely reached energy 120 on one incumbent. In
combination with the best exact-minimum lane it formed the best Glucose pair,
ending at mean energy 138.0. CaDiCaL again preferred a different pair:
randomized greedy at halo 4/width 2 plus exact minimum at halo 0/width 4 ended
at 147.0.

A hypothetical four-worker portfolio containing those solver-specific pairs
ended at energies 128, 140, 140, 124, 164, 132, 136, and 120: mean 135.5 and
mean improvement 23.5. Using both cover policies with the old halo 2/width 2
setting on both solvers ended at mean 142.0 and improved by 17.0. Size-aware
lane selection therefore gained another 6.5 energy points in this matched
sample, but the pilot reversal and solver-dependent rankings argue for a
portfolio rather than a new global default.

`run-hybrid-search.py` now accepts repeated explicit
`--sat-lane SOLVER:COVER:HALO:EXPAND` specifications, names every worker with
all four fields, and automatically uses split random streams. This makes the
four selected raw-SAT lanes operational without launching the full solver ×
cover × size product. Exact runs and validations are in
`benchmarks/neighborhood-size-pilot-2026-08-07.json`,
`benchmarks/neighborhood-size-glucose-2026-08-07.json`, and
`benchmarks/neighborhood-size-cadical-2026-08-07.json`.

### Iterated incumbent carry and restart cadence

The hybrid runner can now divide fixed total local and exact budgets across
multiple rounds. Every local phase starts from the best code found so far,
round seeds advance deterministically, and an improving repair result can seed
the next local phase. One round remains the compatibility default. Repair can
run after every local phase or use its entire budget only after the final
phase; the latter separates local restart effects from exact-to-local
feedback.

A three-incumbent pilot compared one, two, and four interleaved rounds with
four total local seconds and four total repair seconds. The four-round result
won all three cases and reduced mean final energy from 132.0 to 117.33. An
independent-seed confirmation on all eight recorded incumbents gave:

| Schedule | Final energies | Mean | Median | Mean improvement | Mean wall time |
|---|---|---:|---:|---:|---:|
| one 4 s local + one 4 s repair | 104, 132, 128, 144, 144, 128, 136, 136 | 131.5 | 134 | 27.5 | 8.41 s |
| four × (1 s local + 1 s repair) | 112, 132, 100, 128, 108, 100, 120, 116 | 114.5 | 114 | 44.5 | 9.16 s |

Four rounds beat one on six incumbents, tied one, and lost one. The nominal
budgets are equal; the extra 0.75 seconds is process and model-construction
overhead. All 16 final codes were independently recomputed by both validators.

This result alone does not establish that exact feedback caused the gain.
Across the four-round confirmation, local phases improved 15 of 32 times,
whereas exact phases improved only five. A separate eight-incumbent ablation
therefore held four one-second local segments fixed and changed only repair
placement:

| Repair placement | Final energies | Mean | Median | Mean wall time |
|---|---|---:|---:|---:|
| 1 s after every segment | 128, 108, 112, 136, 112, 116, 116, 104 | 116.5 | 114 | 9.74 s |
| one final 4 s repair | 124, 108, 112, 116, 140, 116, 116, 96 | 116.0 | 116 | 8.63 s |

Final-only repair won three cases, lost one, and tied four. It is statistically
indistinguishable on energy in this small heavy-tailed sample and avoids three
extra exact-model startups. The supported conclusion is therefore that
*incumbent-carrying local segmentation* is valuable; frequent exact-to-local
feedback is not yet supported. Exact repair still occasionally makes large
jumps and remains useful as a final portfolio stage.

A restart-cadence pilot with eight total local seconds favored eight one-second
segments only narrowly over two four-second segments. The eight-incumbent
confirmation likewise ended at means 120.5 versus 122.5, with equal median
122 and a 3–3 win/loss split. Thus the evidence supports forcing more than one
local trajectory, but does not identify a universal one-second cutoff.

At that stage the lowest new near-miss had energy 92 and 92 violating lines. It
came from the eight-segment cadence pilot and is dual-validated in
`benchmarks/iterated-hybrid-cadence-pilot-2026-08-07.json`. Full pilot,
confirmation, feedback-ablation, and cadence records are in the five
`benchmarks/iterated-hybrid-*-2026-08-07.json` artifacts.

### Wall-clock stagnation restart experiment

The next controlled experiment replaced fixed process cadence with an internal
wall-clock stagnation trigger. `rot4-factor-search.cpp --stagnation-ms N`
restarts a worker from a perturbed copy of the shared incumbent after `N`
milliseconds without a new best energy. With the option absent or zero, the
old iteration-based behavior is unchanged. The hybrid runner exposes the same
setting as `--local-stagnation-ms`.

A four-incumbent pilot used eight total local seconds, one final four-second
repair portfolio, and fresh seeds beginning at 960:

| Schedule | Final energies | Mean | Median |
|---|---|---:|---:|
| two × 4 s, final repair | 132, 124, 112, 112 | 120.0 | 118 |
| eight × 1 s, final repair | 120, 96, 104, 108 | 107.0 | 106 |
| 2 s stagnation, final repair | 128, 136, 120, 112 | 124.0 | 124 |
| 3 s stagnation, final repair | 108, 136, 120, 112 | 119.0 | 116 |

The three-second trigger was retained for an eight-incumbent, fresh-seed
confirmation. All schedules again used eight local seconds and one final
four-second repair portfolio:

| Schedule | Final energies | Mean | Median | Mean improvement |
|---|---|---:|---:|---:|
| two × 4 s | 124, 112, 120, 120, 132, 128, 132, 120 | 123.5 | 122 | 35.5 |
| eight × 1 s | 120, 124, 92, 128, 116, 104, 128, 128 | 117.5 | 122 | 41.5 |
| 3 s stagnation | 124, 140, 100, 116, 116, 132, 116, 136 | 122.5 | 120 | 36.5 |

Eight one-second rounds beat the adaptive trigger five times, lost twice, and
tied once, improving mean energy by 5.0. The adaptive lane allowed late
improvements, and exact repair improved four of its eight results, but this did
not compensate for the lost trajectory diversity. The experiment therefore
rejects wall-clock continuation on improvement as the default at this budget;
unconditional short incumbent-carrying restarts remain preferred. Complete
dual-validated records are in `adaptive-restart-pilot-2026-08-08.json` and
`adaptive-restart-confirmation-2026-08-08.json`.

The confirmation's energy-92 code seeded a larger discovery run with 120
one-second rounds, eight local-search workers per round, and a final 30-second
five-worker exact portfolio. Local round 14 reached a new energy-88 near-miss:

```text
oFQZshuX$hj5)c&eoRrCr6VGv3@EOY#q{u%PgBt2GIQ1d89FUb#7wt{T?VdYm4ql&24H]kz7>LS6pO(ls1!ET3w[<ASN[Rfai8k0KH!Dcjy@?a>nvx<K%XoBJ0NDfpz9]Ixi(M$MmPZAb5)UWCgJWLeny
```

Both the standalone validator and the application's independent `LineIndex`
confirm 152 points, rot4 symmetry, a row-perfect quotient factor, and exactly
88 violating lines/triples. None of the four SAT lanes or Z3 improved it in
the final repair stage. The complete trajectory and solver records are in
`focused-discovery-2026-08-08.json`.

An independent continuation from that code used 180 further one-second rounds,
eight workers per round, seeds beginning at 1400, and a final 60-second exact
portfolio. Round 6 reduced the energy from 88 to 76:

```text
oFQZshuX$Pj5)c&WeRrCr6VGv3@EiY#q{J%PgBt2xIQ1d89FUblw[t{T?OdYm4qD&2!H]kz7>LS6pO(ls1!ET3w7<A#N[Rfap8k0K4HScjy@?a>nvG<K%XoBu0NDfVz9]Ixi(M$MmZhAb5)UoCgJWLeny
```

The two validators agree on all 76 remaining violating lines/triples. No later
local round or exact lane improved it. The full continuation record is in
`focused-discovery-continuation-2026-08-08.json`.

A final independent block used 240 more one-second, eight-worker rounds from
the energy-76 code, followed by another 60-second exact portfolio. It produced
no improvement. Together with rounds 7–180 of the preceding continuation, the
incumbent survived 414 consecutive post-improvement restart rounds and two
exact tails unchanged. `focused-discovery-final-2026-08-08.json` records this
plateau check. Further compute should therefore change the move or repair
neighborhood rather than repeat the same short-restart distribution.

### Wider perturbations and four-edge reconnection

The next move experiment added two disabled-by-default controls. A worker's
initial perturbation distance is now `thread_index * perturb_step`, with the
legacy step of 3 retained by default. The optional four-edge move chooses four
pairwise-disjoint non-loop factor edges, randomly pairs their eight distinct
endpoints, and independently orients the resulting arcs. Every quotient
vertex therefore retains its degree, so the move stays inside the oriented
2-factor space. Existing duplicate-arc checks reject invalid pairings.

A four-incumbent pilot crossed perturbation steps 3 and 12 with four-edge rates
0% and 10%. Each lane used four local workers, eight one-second rounds, and a
final four-second exact portfolio:

| Perturbation / four-edge rate | Final energies | Mean | Median |
|---|---|---:|---:|
| step 3 / 0% | 112, 104, 96, 112 | 106.0 | 108 |
| step 12 / 0% | 120, 112, 96, 96 | 106.0 | 104 |
| step 3 / 10% | 128, 96, 108, 132 | 116.0 | 118 |
| step 12 / 10% | 120, 96, 104, 124 | 111.0 | 112 |

Ten percent displaced too many productive legacy moves. The confirmation kept
the wider perturbation and reduced four-edge sampling to 2%, again against the
legacy baseline on all eight recorded incumbents with fresh seeds:

| Perturbation / four-edge rate | Final energies | Mean | Median | Mean improvement |
|---|---|---:|---:|---:|
| step 3 / 0% | 116, 120, 124, 104, 132, 112, 132, 96 | 117.0 | 118 | 42.0 |
| step 12 / 0% | 104, 124, 124, 128, 120, 132, 112, 124 | 121.0 | 124 | 38.0 |
| step 12 / 2% | 108, 120, 112, 124, 96, 116, 136, 84 | 112.0 | 114 | 47.0 |

The combined lane beat baseline four times, lost three times, and tied once,
lowering mean energy by 5.0 and median by 4. Wider perturbation alone regressed
by 4.0 mean points, so the evidence is for an interaction: wider starts make
rare four-edge basin jumps useful, while either an aggressive four-edge rate
or wider starts alone are weaker. All pilot and confirmation codes pass both
validators; full records are in `four-edge-perturbation-pilot-2026-08-08.json`
and `four-edge-perturbation-confirmation-2026-08-08.json`.

The selected step-12/2% lane was then run directly from the energy-76
incumbent for 240 one-second rounds with eight workers per round, followed by a
60-second exact portfolio. It produced no improvement; both validators again
recomputed energy 76. Thus the new neighborhood improves average short-run
quality but does not yet break this specific basin. The full negative result is
in `four-edge-focused-discovery-2026-08-08.json`.

No `n=76` solution or global UNSAT result was obtained, and none is claimed.
Search preprocessing, an in-process proof-producing solver, DRAT checking,
LRAT conversion, and a formally verified endpoint are exercised end to end on
regression formulas. Buffered synchronization remains the proof default. For
search, the best-supported workflow now carries the incumbent through several
short local phases and then runs the solver-, cover-, and size-diverse repair
portfolio once. Wall-clock stagnation continuation has now been tested and
rejected at the short budget. Wider perturbations plus rare four-edge moves are
the new selected general-search neighborhood, but the energy-76 incumbent now
needs a conflict-biased multi-edge move rather than uniformly chosen companion
edges. Exact repair should be invoked selectively when conflict-cover and
neighborhood statistics predict a tractable move.

## References

1. Achim Flammenkamp, [The No-Three-in-Line Problem](https://wwwhomes.uni-bielefeld.de/achim/no3in/readme.html), current database and 2025–2026 chronology.
2. Achim Flammenkamp and Thomas Prellberg, [Four-cycles in no-three-in-line configurations](https://wwwhomes.uni-bielefeld.de/achim/no3in/four_cycle_decomposition_note.html), June 30, 2026.
3. Thomas Prellberg, [Constraint Satisfaction Programming for the No-three-in-line Problem](https://arxiv.org/html/2602.07751), 2026.
4. Thomas Prellberg, [CP-SAT reference implementation](https://github.com/ThomasPrellberg/no-three-in-line---CP-SAT).
5. Thomas Prellberg, [Four-corner permutation tests for no-three-in-line configurations](https://wwwhomes.uni-bielefeld.de/achim/no3in/four_corner_permutation_note.html), June 27, 2026.
6. Achim Flammenkamp, [rot4 solution downloads](https://wwwhomes.uni-bielefeld.de/achim/no3in/download/solutions_by_symmetry/rot4/).
7. Pranav Ramanathan et al., [Three Methods, One Problem: Classical and AI Approaches to No-Three-in-Line](https://arxiv.org/html/2512.11469), 2025.
8. Luoning Zhang et al., [Geometry-Aware MCTS for Extremal Problems in Combinatorial Geometry](https://arxiv.org/html/2606.26399), 2026.
9. Alexey Ignatiev, Antonio Morgado, and Joao Marques-Silva, [PySAT documentation](https://pysathq.github.io/docs/html/api/solvers.html), assumption-based incremental solver API, accessed August 7, 2026.
10. Andrew Haberlandt, Harrison Green, and Marijn J. H. Heule, [Effective Auxiliary Variables via Structured Reencoding](https://www.cs.cmu.edu/~mheule/publications/SAT23-SBVA.pdf), SAT 2023, DOI 10.4230/LIPIcs.SAT.2023.10.
11. Marijn J. H. Heule and Nathan Wetzler, [The DRAT format and DRAT-trim checker](https://github.com/marijnheule/drat-trim), official implementation and format documentation.
12. Yong Kiam Tan, Marijn J. H. Heule, and Magnus O. Myreen, [CakeLPR](https://github.com/tanyongkiam/cake_lpr), formally verified LPR/LRAT proof checker generated with CakeML and HOL4.
13. Armin Biere et al., [CaDiCaL SAT Solver](https://github.com/arminbiere/cadical), official source and command-line proof interface.
