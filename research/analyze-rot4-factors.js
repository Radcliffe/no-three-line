#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.resolve(__dirname, "..");
require(path.join(projectRoot, "configuration-codec.js"));
const codec = globalThis.NoThreeLineCodec;

function loadBundledSolutions() {
  const filename = path.join(projectRoot, "optimal-solutions.generated.js");
  const source = fs.readFileSync(filename, "utf8");
  const context = {};
  vm.createContext(context);
  vm.runInContext(`${source}\nthis.solutions = optimalSolutions;`, context);
  return context.solutions;
}

function factorStats(n, code) {
  const decoded = codec.decodeConfiguration(code);
  if (decoded.size !== n || decoded.symmetryGroup !== "rot4" || n % 2 !== 0) {
    throw new Error(`${code.slice(0, 20)} is not a rot4 code of even size ${n}.`);
  }

  const m = n / 2;
  const arcs = decoded.cells.filter(([row, column]) => row < m && column < m);
  const degrees = Array(m).fill(0);
  const indegrees = Array(m).fill(0);
  const outdegrees = Array(m).fill(0);
  const adjacency = Array.from({ length: m }, () => []);

  for (let edge = 0; edge < arcs.length; edge++) {
    const [from, to] = arcs[edge];
    outdegrees[from]++;
    indegrees[to]++;
    if (from === to) {
      degrees[from] += 2;
      adjacency[from].push([from, edge], [from, edge]);
    } else {
      degrees[from]++;
      degrees[to]++;
      adjacency[from].push([to, edge]);
      adjacency[to].push([from, edge]);
    }
  }

  if (arcs.length !== m || degrees.some((degree) => degree !== 2)) {
    throw new Error(`The quotient at n=${n} is not a degree-two factor.`);
  }

  const seenEdges = new Set();
  const componentLengths = [];
  for (let firstEdge = 0; firstEdge < arcs.length; firstEdge++) {
    if (seenEdges.has(firstEdge)) continue;
    const [start, other] = arcs[firstEdge];
    if (start === other) {
      seenEdges.add(firstEdge);
      componentLengths.push(1);
      continue;
    }

    let current = start;
    let edge = firstEdge;
    let length = 0;
    while (!seenEdges.has(edge)) {
      seenEdges.add(edge);
      length++;
      const [from, to] = arcs[edge];
      const nextVertex = current === from ? to : from;
      const next = adjacency[nextVertex].find(([, candidate]) => !seenEdges.has(candidate));
      current = nextVertex;
      if (!next) break;
      edge = next[1];
    }
    componentLengths.push(length);
  }

  componentLengths.sort((a, b) => b - a);
  const balanced = indegrees.filter(
    (degree, vertex) => degree === 1 && outdegrees[vertex] === 1,
  ).length;
  return {
    n,
    components: componentLengths.length,
    cycles: componentLengths.join("+"),
    longest: componentLengths[0],
    loops: componentLengths.filter((length) => length === 1).length,
    digons: componentLengths.filter((length) => length === 2).length,
    balanced,
  };
}

function summarizeCatalog(n, codes) {
  const stats = codes.map((code) => factorStats(n, code));
  const componentHistogram = new Map();
  for (const row of stats) {
    componentHistogram.set(
      row.components,
      (componentHistogram.get(row.components) || 0) + 1,
    );
  }
  const Hamiltonian = stats.filter((row) => row.components === 1).length;
  const withLoops = stats.filter((row) => row.loops > 0).length;
  return {
    n,
    solutions: stats.length,
    componentHistogram: Object.fromEntries(
      [...componentHistogram].sort(([a], [b]) => a - b),
    ),
    Hamiltonian,
    HamiltonianFraction: Hamiltonian / stats.length,
    withLoopsFraction: withLoops / stats.length,
    meanBalancedFraction:
      stats.reduce((sum, row) => sum + row.balanced / (n / 2), 0) /
      stats.length,
  };
}

function inferCatalogSize(filename) {
  const match = path.basename(filename).match(/n(\d+)_rot4/);
  if (!match) {
    throw new Error(`Cannot infer a grid size from catalog filename ${filename}.`);
  }
  return Number(match[1]);
}

const bundledRows = Object.entries(loadBundledSolutions())
  .map(([n, code]) => [Number(n), code])
  .filter(([n, code]) => n % 2 === 0 && code.startsWith("o"))
  .map(([n, code]) => factorStats(n, code));

console.log("Bundled rot4 representatives");
console.log("n  components  cycles  longest  loops  digons  balanced");
for (const row of bundledRows) {
  console.log(
    [
      String(row.n).padStart(2),
      String(row.components).padStart(10),
      row.cycles.padStart(12),
      String(row.longest).padStart(8),
      String(row.loops).padStart(6),
      String(row.digons).padStart(7),
      String(row.balanced).padStart(9),
    ].join("  "),
  );
}

const large = bundledRows.filter((row) => row.n >= 44);
console.log("\nBundled n >= 44 summary");
console.log(
  JSON.stringify(
    {
      representatives: large.length,
      Hamiltonian: large.filter((row) => row.components === 1).length,
      meanComponents:
        large.reduce((sum, row) => sum + row.components, 0) / large.length,
      meanLongestFraction:
        large.reduce((sum, row) => sum + row.longest / (row.n / 2), 0) /
        large.length,
      meanBalancedFraction:
        large.reduce((sum, row) => sum + row.balanced / (row.n / 2), 0) /
        large.length,
    },
    null,
    2,
  ),
);

for (const filename of process.argv.slice(2)) {
  const n = inferCatalogSize(filename);
  const codes = fs.readFileSync(filename, "utf8").trim().split(/\s+/);
  console.log(`\nComplete catalog ${filename}`);
  console.log(JSON.stringify(summarizeCatalog(n, codes), null, 2));
}

