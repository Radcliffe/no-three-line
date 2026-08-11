# rot4 no-three-in-line research

This folder records experiments on finding `2n`-point no-three-in-line
configurations with quarter-turn (`rot4`) symmetry. It is deliberately
separate from the browser application: the app remains dependency-free, while
the research programs may use a compiler and optional Python packages.

The main finding is that the row constraints have a useful graph
interpretation. For `n = 2m`, identify a representative `(i, j)` in the
top-left `m × m` quadrant with a directed arc `i -> j`. A selection has two
points in every row exactly when

```text
2 y[v,v] + sum(j != v) (y[v,j] + y[j,v]) = 2
```

for every quotient vertex `v`. The selected arcs are therefore an oriented
2-factor: a union of loops, digons, and cycles. Searching with moves that
preserve this structure avoids ever visiting a row-infeasible state.

See [FINDINGS.md](FINDINGS.md) for the derivation, catalog measurements,
prototype results, limitations, and recommended next steps.

## Programs

| File | Purpose |
|---|---|
| `analyze-rot4-factors.js` | Extract quotient 2-factors from bundled solutions or downloaded rot4 catalogs and summarize their cycle structure. |
| `evaluate-factor-lifts.js` | Compare row-perfect `n -> n+2` lifts with deterministic random Hamiltonian seeds. |
| `rot4-factor-search.cpp` | Multithreaded factor search with incremental line counts, breakout weights, configurable factor-preserving moves, portfolio starts, and worker incumbent exchange. |
| `rot4-sat-repair.py` | Native CNF repair using incremental SAT, assumptions, core-guided neighborhood expansion, optional SBVA search preprocessing, and independently checked CaDiCaL proof production. |
| `cadical-proof-bridge.cpp` | Minimal C ABI that keeps a proof-tracing CaDiCaL shadow solver in process and accepts clauses in batches. |
| `rot4-lazy-z3.py` | Exact lazy solver and assumption-based large-neighborhood repair endpoint. |
| `run-hybrid-search.py` | Run one or more incumbent-carrying local phases, schedule exact repair between or after them, and validate any solution end to end. |
| `benchmark-factor-search.py` | Run a deterministic seed portfolio and report time-to-zero plus censored energy curves. |
| `benchmark-repair-backends.py` | Compare raw SAT, optional SBVA+SAT, and Z3 on identical emitted incumbents and validate their reported energies. |
| `benchmark-cadical-proof.py` | Compare verified CaDiCaL proofs with and without bounded variable addition on a structured UNSAT formula. |
| `benchmark-shadow-sync.py` | Compare eager, per-candidate, and proof-boundary synchronization of retained lazy cuts with the in-process CaDiCaL shadow. |
| `benchmark-neighborhood-policies.py` | Compare initial conflict-cover and UNSAT-core expansion policies on matched incumbent, seed, solver, and time-limit tuples. |
| `benchmark-neighborhood-sizes.py` | Cross cover lanes with halo sizes and UNSAT-core expansion widths, or run an explicit list of size configurations. |
| `benchmark-iterated-hybrid.py` | Compare matched local/repair round counts and repair placement under fixed total budgets. |
| `benchmarks/sbva-2026-08-07.json` | Reproducibility record for the matched SBVA experiments, including exact incumbents and the best validated near-miss. |
| `benchmarks/sat-portfolio-2026-08-07.json` | Independent-incumbent comparison of CaDiCaL and Glucose, with and without SBVA. |
| `benchmarks/proof-checker-2026-08-07.json` | Exact drat-trim and CakeLPR builds plus positive/negative certificate regressions. |
| `benchmarks/cadical-proof-preprocessing-2026-08-07.json` | Exact CaDiCaL factorization timing and proof-size comparison. |
| `benchmarks/shadow-sync-2026-08-07.json` | Clause-stream and matched-repair measurements for buffered shadow synchronization on recorded `n=76` near-misses. |
| `benchmarks/neighborhood-incumbents-2026-08-07.json` | Eight fresh two-second, single-thread `n=76` local-search incumbents used for neighborhood comparisons. |
| `benchmarks/neighborhood-policy-pilot-2026-08-07.json` | Twelve-policy pilot separating initial-cover and core-expansion effects. |
| `benchmarks/neighborhood-policy-glucose-2026-08-07.json` | Four-cover comparison on eight fresh incumbents with Glucose 4.2. |
| `benchmarks/neighborhood-policy-core-2026-08-07.json` | Core score, marginal coverage, and random expansion crossed with the two strongest cover lanes. |
| `benchmarks/neighborhood-policy-cadical-2026-08-07.json` | Deterministic greedy, randomized greedy, and exact-minimum cover comparison with CaDiCaL 1.9.5. |
| `benchmarks/neighborhood-size-pilot-2026-08-07.json` | Full 18-lane halo/expansion pilot on three recorded near-misses. |
| `benchmarks/neighborhood-size-glucose-2026-08-07.json` | Targeted size confirmation on eight incumbents with Glucose 4.2. |
| `benchmarks/neighborhood-size-cadical-2026-08-07.json` | Cross-solver confirmation of the selected size-diversity lanes. |
| `benchmarks/iterated-hybrid-pilot-2026-08-07.json` | One-, two-, and four-round feedback pilot on three incumbents. |
| `benchmarks/iterated-hybrid-confirmation-2026-08-07.json` | Independent-seed one-versus-four-round confirmation on eight incumbents. |
| `benchmarks/iterated-hybrid-ablation-2026-08-07.json` | Interleaved-versus-final-only exact-repair ablation with four local segments. |
| `benchmarks/iterated-hybrid-cadence-pilot-2026-08-07.json` | Two-, four-, and eight-segment restart-cadence pilot. |
| `benchmarks/iterated-hybrid-cadence-confirmation-2026-08-07.json` | Two-versus-eight-segment cadence confirmation on eight incumbents. |
| `benchmarks/adaptive-restart-pilot-2026-08-08.json` | Four-incumbent pilot comparing fixed cadence with two- and three-second stagnation triggers. |
| `benchmarks/adaptive-restart-confirmation-2026-08-08.json` | Fresh-seed confirmation of fixed cadence and the selected adaptive trigger. |
| `benchmarks/focused-discovery-2026-08-08.json` | A 120-round, eight-thread `n=76` continuation from energy 92 that reached energy 88. |
| `benchmarks/focused-discovery-continuation-2026-08-08.json` | An independent 180-round continuation from energy 88 that reached energy 76. |
| `benchmarks/focused-discovery-final-2026-08-08.json` | A final 240-round plateau check from energy 76, with a 60-second exact tail. |
| `benchmarks/four-edge-perturbation-pilot-2026-08-08.json` | Four-way pilot crossing incumbent perturbation width with a 10% four-edge move rate. |
| `benchmarks/four-edge-perturbation-confirmation-2026-08-08.json` | Eight-incumbent confirmation of wider perturbations and a light 2% four-edge lane. |
| `benchmarks/four-edge-focused-discovery-2026-08-08.json` | A 240-round direct test of the selected wider/four-edge neighborhood on the energy-76 incumbent. |
| `validate-rot4-code.js` | Check a code independently and again with the application's `LineIndex`. |
| `check-unsat-trace.py` | Semantically verify every addition in an emitted DRUP trace with an independent SAT engine. |
| `test-sat-encoding.py` | Exhaustively check CNF semantics, line enumeration, dual-CNF retention, SAT refusal, and the DRAT-to-LRAT proof chain. |
| `requirements.txt` | Optional dependency for the lazy solver. |

All programs use zero-based coordinates internally and the same compact
configuration alphabet as the application.

Commands using an exact backend assume `research/requirements.txt` is
installed. If using the isolated environment shown below, replace `python3`
with `/tmp/no-three-line-research/bin/python` in those commands.

## Reproduce the bundled-solution analysis

From the repository root:

```sh
node research/analyze-rot4-factors.js
node research/evaluate-factor-lifts.js
```

The first command analyzes the one representative bundled for each grid size.
The second defaults to the bundled `74 -> 76` lift experiment, with 1,000
random Hamiltonian seeds and deterministic seed `20260807`.

The complete-catalog statistics in the report use the `n44_rot4`, `n48_rot4`,
`n52_rot4`, `n54_rot4`, and `n56_rot4` files from Achim Flammenkamp's
[rot4 download directory](https://wwwhomes.uni-bielefeld.de/achim/no3in/download/solutions_by_symmetry/rot4/).
After downloading them, pass their paths to the analyzer:

```sh
node research/analyze-rot4-factors.js \
  /path/to/n44_rot4 \
  /path/to/n48_rot4 \
  /path/to/n52_rot4 \
  /path/to/n54_rot4 \
  /path/to/n56_rot4
```

External catalogs are not copied into this repository.

## Build and run the factor search

```sh
clang++ -O3 -std=c++17 -pthread \
  research/rot4-factor-search.cpp \
  -o /tmp/rot4-factor-search

/tmp/rot4-factor-search 30 10 8 --seed 1
```

Arguments are grid size, time limit in seconds, and thread count. The grid
size must be even. Every run prints a `best_code`, including an unsolved
near-miss, plus timestamped global-best events. A successful run also prints
the same code as `solution`.

The maintained state is always an oriented 2-factor. Its exact and weighted
energies are updated through a map from canonical line identifiers to current
point multiplicities. Breakout updates increase the weights of violated
lines. The move portfolio contains arc reversal, two-edge switching,
loop-to-cycle surgery and its inverse, and three-edge reconnection. Two-edge
switches can create or remove digons. `--four-edge-percent P` assigns `P`
percent of move attempts to a wider reconnection of four pairwise-disjoint
factor edges. It defaults to zero, preserving the original search distribution.

To initialize `n=76` from all one-vertex lifts of the bundled `n=74`
solution:

```sh
/tmp/rot4-factor-search 76 30 8 \
  --seed 1 \
  --lift-from 74 \
  --solutions optimal-solutions.generated.js
```

With `--lift-from`, every one-vertex lift is scored and stored in each worker's
portfolio. The top-ranked lifts are distributed across workers, while later
restarts cycle through lifts, random Hamiltonian cycles, general 2-factors,
and shared near-misses. The search is stochastic; use the benchmark harness
below rather than treating one run as representative.

To resume or diversify around any emitted near-miss, pass
`--incumbent 'PASTE_BEST_CODE_HERE'`. Worker zero starts exactly at that
factor; the remaining workers start from independently perturbed copies.

`--stagnation-ms N` optionally restarts a trajectory from a perturbed copy of
the shared incumbent after `N` milliseconds without improving its best energy.
The August 8 matched experiments found this useful as a diagnostic but not as
the preferred short-budget policy: unconditional one-second incumbent-carrying
rounds were stronger than the selected three-second stagnation trigger.
`--perturb-step N` controls the additional perturbation moves assigned to each
successive worker (default 3). The hybrid runner exposes these settings as
`--local-four-edge-percent` and `--local-perturb-step`.

## Run the hybrid local-search and exact-repair workflow

The orchestrator feeds the local search's `best_code` directly into an exact
repair neighborhood. It frees a greedy cover of all currently violated lines,
a random halo, and at least the requested fraction of quotient vertices. All
other arc values are fixed by solver assumptions. An unsatisfiable
neighborhood is enlarged without discarding learned clauses or line cuts. The
initial cover can instead be an exact minimum hitting set; randomized greedy
and conflict-score tie-breaking are also available.

Native SAT with CaDiCaL is the default repair backend. Choose `z3` for the
pseudo-Boolean reference or `portfolio` to run SAT and Z3 concurrently and
retain the better result. If `--sat-sbva [PATH]` is present, a portfolio also
runs raw SAT and SBVA+SAT as separate workers; outside portfolio mode the flag
preprocesses the one SAT worker. Repeat `--sat-solver` to add engines to a
portfolio. For example, the full tested portfolio is:

```sh
python3 research/run-hybrid-search.py /tmp/rot4-factor-search 76 \
  --local-seconds 20 \
  --repair-seconds 20 \
  --repair-backend portfolio \
  --sat-solver cadical195 \
  --sat-solver glucose42 \
  --sat-sbva /usr/local/bin/sbva
```

This launches raw and SBVA-preprocessed variants of both SAT engines, plus Z3.
Cover policies and neighborhood sizes form additional portfolio dimensions.
`--sat-lane SOLVER:COVER:HALO:EXPAND` selects only measured combinations and
avoids a large Cartesian product. The four strongest complementary raw-SAT
lanes from the size experiment are:

```sh
python3 research/run-hybrid-search.py /tmp/rot4-factor-search 76 \
  --local-seconds 20 \
  --repair-seconds 20 \
  --repair-backend portfolio \
  --sat-lane glucose42:minimum:4:2 \
  --sat-lane glucose42:greedy-random:0:4 \
  --sat-lane cadical195:greedy-random:4:2 \
  --sat-lane cadical195:minimum:0:4
```

Repeated solver, cover, and SBVA options form their Cartesian product, so add
them only when enough cores are available. Explicit lanes are raw SAT and
cannot be combined with those repeated options; Z3 remains an additional
portfolio worker.

`--rounds` forces several local trajectories while carrying the best code
forward. `--local-seconds` and `--repair-seconds` are total budgets, not
per-round budgets. With the default `--repair-schedule each`, repair time is
split equally across rounds. `--repair-schedule final` runs no intermediate
repairs and spends the entire exact budget after the last local phase. The
matched `n=76` experiments favor segmented local search but find no energy
advantage from rebuilding the exact portfolio after every segment, so the
best-supported short-budget schedule is:

```sh
python3 research/run-hybrid-search.py /tmp/rot4-factor-search 76 \
  --initial-incumbent 'PASTE_BEST_CODE_HERE' \
  --local-seconds 4 --repair-seconds 4 \
  --rounds 4 --repair-schedule final \
  --repair-backend portfolio \
  --sat-lane glucose42:minimum:4:2 \
  --sat-lane glucose42:greedy-random:0:4 \
  --sat-lane cadical195:greedy-random:4:2 \
  --sat-lane cadical195:minimum:0:4
```

The local budget must provide at least one whole second per round. A fresh-seed
adaptive restart experiment favored eight one-second segments at mean energy
117.5, versus 123.5 for two four-second segments and 122.5 for one eight-second
run with a three-second stagnation trigger.

```sh
python3 research/run-hybrid-search.py /tmp/rot4-factor-search 30 \
  --local-seconds 10 \
  --repair-seconds 20 \
  --repair-backend sat \
  --threads 4 \
  --seed 1 \
  --core-vertices 6 \
  --halo-vertices 2 \
  --free-fraction 0.15 \
  --expand-by 2
```

For the record target, add `--lift-from 74`; `--sat-solver glucose42` is also
worth including in an external portfolio. With the installed binary, add
`--sat-sbva /usr/local/bin/sbva` to explore the complementary preprocessed SAT
trajectory. The final JSON includes both phases and, when solved, the two
independent validation results.

## Run the exact repair backends

The application does not need this dependency. Install it in an isolated
environment if necessary:

```sh
python3 -m venv /tmp/no-three-line-research
/tmp/no-three-line-research/bin/pip install -r research/requirements.txt
/tmp/no-three-line-research/bin/python research/rot4-sat-repair.py 30 \
  --seconds 20 \
  --seed 1 \
  --incumbent 'PASTE_BEST_CODE_HERE'
```

The SAT model uses sequential counters for quotient degree equations and long
at-most-two line constraints. Small line constraints become direct ternary
clauses; coefficient-two incidences become binary conflicts. Fixed arcs are
assumption literals, and unsatisfiable cores choose the next vertices to free.
`--initial-cover-policy minimum` solves the small violated-line hitting-set
problem exactly before repair; `greedy`, `greedy-conflict`, and
`greedy-random` retain cheaper alternatives. Core expansion supports `score`,
`marginal`, and `random`; controlled results favor the default `score` policy.
For matched experiments, `--split-rng-streams` prevents a policy's random
choices from changing halo priorities or later lazy-cut order.
The default solver is CaDiCaL 1.9.5 through
[PySAT](https://pysathq.github.io/). PySAT's Kissat wrapper must not be used
because it does not support assumptions.

Global UNSAT proof output is available only after every fixing assumption has
been removed. Set `--free-fraction 1` to start globally unfixed and provide a
new or empty `--proof-dir`. On macOS, build the optional in-process bridge
against CaDiCaL 3.0.1 with:

```sh
clang++ -std=c++17 -O3 -fPIC -dynamiclib \
  research/cadical-proof-bridge.cpp \
  -I/path/to/cadical/src \
  /path/to/cadical/build/libcadical.a \
  -o /tmp/libno3cadical.dylib
```

Use `-shared` and a `.so` suffix on Linux. Then run:

```sh
/tmp/no-three-line-research/bin/python research/rot4-sat-repair.py 76 \
  --solver cadical195 \
  --sbva /usr/local/bin/sbva \
  --proof-dir /tmp/rot4-n76-proof \
  --proof-cadical-library /tmp/libno3cadical.dylib \
  --proof-cadical-seconds 3600 \
  --proof-checker /path/to/drat-trim \
  --proof-lrat \
  --lrat-checker /path/to/cake_lpr \
  --free-fraction 1 \
  --seconds 3600 \
  --incumbent 'PASTE_BEST_CODE_HERE'
```

The SBVA search formula and the original formula are kept separately. Every
later lazy geometric cut is added to both. With `--proof-cadical-library`, the
original clauses are also batch-synchronized to an in-process, proof-tracing
CaDiCaL shadow before SBVA runs. Later cuts are retained immediately in the
original CNF and, by default, flushed to the shadow once at the global proof
boundary. `--proof-shadow-sync candidate` instead flushes after every SAT
candidate, while `--proof-shadow-sync eager` retains the old per-clause path
for regression and measurement. When the transformed search formula reports
globally unfixed UNSAT, any pending clauses are flushed before the shadow
solves, without spawning a process or parsing DIMACS. Bounded variable addition
is enabled, and variables are explicitly reserved before each imported batch
to satisfy CaDiCaL 3's extension-variable contract.

`--proof-cadical /path/to/cadical` remains a command-line fallback. It starts a
fresh process and re-solves the same retained original CNF with `--factor`.
Both routes write byte-identical binary `proof.drat` in the regression. An
UNSAT status and nonempty proof are required; a SAT result, timeout, malformed
result, or missing proof causes a hard failure and preserves diagnostic
metadata instead of making a claim. The two CaDiCaL options are mutually
exclusive.

Without `--proof-cadical`, the program discards the transformed solver at the
global boundary and restarts the retained original CNF with `--proof-solver`
(Glucose 4.2 by default), producing text `proof.drup`. Thus SBVA can accelerate
neighborhood discovery in either mode without entering the proof's trusted
base. Only a globally unfixed result can reach either artifact writer.

With `--proof-checker [PATH]`, proof emission also runs `drat-trim`; failed or
timed-out verification makes the command fail while retaining the artifacts
and failure metadata. The record includes the checker binary hash, exit code,
elapsed time, and output. Neighborhood UNSAT, SAT, and timeout results write no
claim.

`--proof-lrat` asks the same successful `drat-trim` run to convert the DRAT/DRUP
trace into `proof.lrat`. `--lrat-checker [PATH]` then verifies that certificate
with either the bundled `lrat-check` executable or
[CakeLPR](https://github.com/tanyongkiam/cake_lpr), whose generated checker is
formally verified through CakeML/HOL4. The wrapper requires an explicit
positive marker (`c VERIFIED` or `s VERIFIED UNSAT`) as well as exit code zero.
That marker check matters because CakeLPR can report an invalid proof while
still returning zero. LRAT path, size, hash, checker binary hash, marker, and
bounded checker output are saved in `metadata.json`.

For the fallback text-DRUP route, the included cross-solver semantic checker
validates every proof addition and the final empty clause:

```sh
python3 research/check-unsat-trace.py \
  /tmp/rot4-n76-proof/formula.cnf \
  /tmp/rot4-n76-proof/proof.drup \
  --solver cadical195
```

This semantic checker is for the text DRUP route; binary CaDiCaL proofs go
directly through `drat-trim`. The checker is intentionally simple and retains
deletion clauses. The
external integration was tested with the official
[drat-trim](https://github.com/marijnheule/drat-trim) source at the commit
recorded in `benchmarks/proof-checker-2026-08-07.json`: it accepted the valid
seven-line regression proof and rejected a deliberately corrupt trace. The
converted 13-line LRAT certificate was accepted independently by both
`lrat-check` and CakeLPR, and both rejected a version missing its final line.
No global `n=76` UNSAT certificate has been produced by these runs.

CaDiCaL's certified factorization was also tested independently on the
9-pigeon/8-hole formula. Across ten warm-cache runs it reduced mean
proof-production time from 0.320 to 0.0158 seconds (20.3x) and binary proof
size from 1,665,899 to 67,949 bytes (about 24.5x smaller). The synchronized
library reduced the final solve boundary again to 0.0121 seconds: 1.30x faster
than the factor-enabled process, or 1.22x including its one-time 0.0008-second
setup. Every proof passed `drat-trim`, and process/library proofs were
byte-identical. This is a structured mechanism test, not evidence of the same
speedup at `n=76`. Reproduce it with:

```sh
/tmp/no-three-line-research/bin/python research/benchmark-cadical-proof.py \
  --cadical /path/to/cadical \
  --library /tmp/libno3cadical.dylib \
  --checker /path/to/drat-trim \
  --repetitions 10
```

Buffered synchronization was measured separately on the three recorded
`n=76` near-misses in `benchmarks/sat-portfolio-2026-08-07.json`. Their 406
violating geometric lines reduced to 102 new orbit-incidence cuts and 8,969
CNF clauses. Across 21 interleaved repetitions, proof-boundary deferral reduced
1,072 eager bridge calls to one, made shadow insertion 2.14x faster, and made
the complete cut update 1.13x faster. Matched short repairs followed identical
candidate and cut trajectories in every mode. Reproduce both parts with:

```sh
/tmp/no-three-line-research/bin/python research/benchmark-shadow-sync.py \
  --library /tmp/libno3cadical.dylib \
  --repetitions 21 \
  --repair-seconds 3 \
  --repair-seed 280 \
  --output /tmp/rot4-shadow-sync.json
```

SBVA preprocessing is deliberately opt-in because the measured benefit is
instance- and seed-dependent. Its runtime counts against `--seconds`, the
transformed solver is still updated incrementally with later lazy cuts, and
the JSON reports the exact input/output variable and clause counts:

```sh
/tmp/no-three-line-research/bin/python research/rot4-sat-repair.py 76 \
  --solver glucose42 \
  --sbva /usr/local/bin/sbva \
  --seconds 20 \
  --incumbent 'PASTE_BEST_CODE_HERE'
```

The Z3 implementation remains the reference and can also solve globally:

```sh
python3 research/rot4-lazy-z3.py 24 \
  --seconds 20 \
  --seed 1
```

Add `--incumbent CODE` to use its equivalent large-neighborhood mode. Add
`--constraint-stats` to count the complete reduced line model instead of
solving it. At `n=76` this enumeration takes several seconds and uses
substantially more memory than the small smoke cases.

## Benchmark across seeds

```sh
python3 research/benchmark-factor-search.py \
  /tmp/rot4-factor-search 30 \
  --seconds 10 \
  --threads 4 \
  --runs 20 \
  --seed 1 \
  --output /tmp/rot4-n30-benchmark.json
```

The report contains each run, independently validates every zero-energy code,
and aggregates final-energy distributions, time-to-zero, and best-energy
curves for runs that remain censored at the cutoff.

To compare repair backends fairly, save one or more `best_code` values in a
text file and give both backends the same limit, seed, and neighborhood:

```sh
python3 research/benchmark-repair-backends.py 30 \
  --incumbents /tmp/n30-incumbents.txt \
  --seconds 10 \
  --seed 1 \
  --sbva /usr/local/bin/sbva \
  --output /tmp/rot4-n30-repair-comparison.json
```

With `--sbva`, the comparison runs raw SAT, SBVA+SAT, and Z3. It checks every
returned code against the independent triple count and the application's line
count, including nonzero near-misses.

`--sat-solver` is repeatable here too. A local-search benchmark can feed its
incumbents directly into a four-way SAT-only comparison, avoiding manual code
copying and using independent repair seeds:

```sh
python3 research/benchmark-repair-backends.py 76 \
  --factor-benchmark /tmp/rot4-n76-local.json \
  --seed 180 \
  --seconds 3 \
  --sat-solver cadical195 \
  --sat-solver glucose42 \
  --sbva /usr/local/bin/sbva \
  --skip-z3 \
  --output /tmp/rot4-n76-sat-portfolio.json
```

The report includes each backend, unique wins, and the hypothetical concurrent
portfolio's best energy and wall time per instance.

To reproduce the neighborhood-policy comparison, first generate the eight
independent incumbents, then run the four initial covers with the fixed raw
core score:

```sh
python3 research/benchmark-factor-search.py \
  /tmp/rot4-factor-search 76 \
  --seconds 2 --threads 1 --runs 8 --seed 90 \
  --output /tmp/n76-neighborhood-incumbents.json

python3 research/benchmark-neighborhood-policies.py 76 \
  --factor-benchmark /tmp/n76-neighborhood-incumbents.json \
  --seconds 2 --seed 480 --solver glucose42 \
  --core-policy score \
  --output /tmp/n76-neighborhood-glucose.json

python3 research/benchmark-neighborhood-policies.py 76 \
  --factor-benchmark /tmp/n76-neighborhood-incumbents.json \
  --seconds 2 --seed 480 --solver cadical195 \
  --initial-policy greedy --initial-policy greedy-random \
  --initial-policy minimum \
  --core-policy score \
  --output /tmp/n76-neighborhood-cadical.json
```

Every emitted near-miss is checked independently and through the application's
line index before it enters the report.

The size confirmation can be reproduced without rerunning the full pilot grid:

```sh
python3 research/benchmark-neighborhood-sizes.py 76 \
  --factor-benchmark /tmp/n76-neighborhood-incumbents.json \
  --seconds 2 --seed 780 --solver glucose42 \
  --configuration 0:1 --configuration 0:2 \
  --configuration 0:4 --configuration 2:2 \
  --configuration 4:2 \
  --output /tmp/n76-neighborhood-size-glucose.json

python3 research/benchmark-neighborhood-sizes.py 76 \
  --factor-benchmark /tmp/n76-neighborhood-incumbents.json \
  --seconds 2 --seed 780 --solver cadical195 \
  --configuration 0:4 --configuration 2:2 \
  --configuration 4:2 \
  --output /tmp/n76-neighborhood-size-cadical.json
```

To reproduce the local-segmentation and repair-placement ablation with the
selected four-lane portfolio plus Z3:

```sh
python3 research/benchmark-iterated-hybrid.py \
  /tmp/rot4-factor-search 76 \
  --factor-benchmark /tmp/n76-neighborhood-incumbents.json \
  --configuration 4:each --configuration 4:final \
  --local-seconds 4 --repair-seconds 4 \
  --threads 1 --seed 960 \
  --output /tmp/n76-iterated-hybrid-ablation.json
```

Without explicit `--configuration` values, the harness compares one, two, and
four interleaved rounds. It rotates strategy order by incumbent and checks
every final near-miss with both line implementations.

The small exhaustive encoding check is:

```sh
python3 research/test-sat-encoding.py
```

## Validation

A printed compact code is checked both by a standalone brute-force research
checker and by the application's line index:

```sh
node research/validate-rot4-code.js 'PASTE_CODE_HERE'
```

Expected output for a solution has `valid: true`, `points: 2 * n`, and zero
violations and triples in both checks.
