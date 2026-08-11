#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.resolve(__dirname, "..");
require(path.join(projectRoot, "configuration-codec.js"));
const codec = globalThis.NoThreeLineCodec;

function parseArguments(argv) {
  const options = {
    sourceSize: 74,
    targetSize: 76,
    samples: 1000,
    seed: 20260807,
  };
  for (let i = 0; i < argv.length; i++) {
    const option = argv[i];
    if (!option.startsWith("--")) throw new Error(`Unknown argument: ${option}`);
    if (i + 1 >= argv.length) throw new Error(`Missing value after ${option}`);
    const value = argv[++i];
    if (option === "--source-size") options.sourceSize = Number(value);
    else if (option === "--target-size") options.targetSize = Number(value);
    else if (option === "--samples") options.samples = Number(value);
    else if (option === "--seed") options.seed = Number(value);
    else throw new Error(`Unknown argument: ${option}`);
  }
  if (
    !Number.isInteger(options.sourceSize) ||
    !Number.isInteger(options.targetSize) ||
    options.sourceSize % 2 !== 0 ||
    options.targetSize !== options.sourceSize + 2
  ) {
    throw new Error("This experiment requires even sizes with target = source + 2.");
  }
  if (!Number.isInteger(options.samples) || options.samples < 1) {
    throw new Error("--samples must be a positive integer.");
  }
  if (!Number.isInteger(options.seed)) throw new Error("--seed must be an integer.");
  return options;
}

function loadBundledSolutions() {
  const source = fs.readFileSync(
    path.join(projectRoot, "optimal-solutions.generated.js"),
    "utf8",
  );
  const context = {};
  vm.createContext(context);
  vm.runInContext(`${source}\nthis.solutions = optimalSolutions;`, context);
  return context.solutions;
}

function makeRandom(seed) {
  let state = seed >>> 0;
  return function random() {
    state += 0x6d2b79f5;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function arcsFromCode(n, code) {
  const m = n / 2;
  return codec
    .decodeConfiguration(code)
    .cells.filter(([row, column]) => row < m && column < m);
}

function orbit(n, [from, to]) {
  return [
    [from, to],
    [to, n - 1 - from],
    [n - 1 - from, n - 1 - to],
    [n - 1 - to, from],
  ];
}

function gcd(a, b) {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b) [a, b] = [b, a % b];
  return a;
}

function lineKey([row1, column1], [row2, column2]) {
  let a = row2 - row1;
  let b = column1 - column2;
  let c = -(a * column1 + b * row1);
  const divisor = gcd(gcd(a, b), c);
  a /= divisor;
  b /= divisor;
  c /= divisor;
  if (a < 0 || (a === 0 && b < 0)) {
    a *= -1;
    b *= -1;
    c *= -1;
  }
  return `${a},${b},${c}`;
}

function energy(n, arcs) {
  const points = arcs.flatMap((arc) => orbit(n, arc));
  const lines = new Map();
  for (let first = 0; first < points.length; first++) {
    for (let second = first + 1; second < points.length; second++) {
      const key = lineKey(points[first], points[second]);
      let members = lines.get(key);
      if (!members) {
        members = new Set();
        lines.set(key, members);
      }
      members.add(first);
      members.add(second);
    }
  }

  let triples = 0;
  let violatingLines = 0;
  let maxLine = 0;
  for (const members of lines.values()) {
    const count = members.size;
    if (count < 3) continue;
    violatingLines++;
    triples += (count * (count - 1) * (count - 2)) / 6;
    maxLine = Math.max(maxLine, count);
  }
  return { triples, violatingLines, maxLine };
}

function randomHamiltonian(m, random) {
  const order = Array.from({ length: m }, (_, index) => index);
  for (let index = m - 1; index > 0; index--) {
    const other = Math.floor(random() * (index + 1));
    [order[index], order[other]] = [order[other], order[index]];
  }
  const arcs = [];
  for (let index = 0; index < m; index++) {
    const from = order[index];
    const to = order[(index + 1) % m];
    arcs.push(random() < 0.5 ? [from, to] : [to, from]);
  }
  return arcs;
}

function generateLifts(oldArcs, newVertex) {
  const candidates = [
    { kind: "add-loop", arcs: [...oldArcs, [newVertex, newVertex]] },
  ];
  for (let edge = 0; edge < oldArcs.length; edge++) {
    const [from, to] = oldArcs[edge];
    const unchanged = oldArcs.filter((_, index) => index !== edge);
    if (from === to) {
      candidates.push({
        kind: `loop-to-digon:${from}`,
        arcs: unchanged.concat([
          [from, newVertex],
          [newVertex, from],
        ]),
      });
      continue;
    }
    for (let mask = 0; mask < 4; mask++) {
      const first = mask & 1 ? [newVertex, from] : [from, newVertex];
      const second = mask & 2 ? [to, newVertex] : [newVertex, to];
      candidates.push({
        kind: `subdivide:${from}-${to}:${mask}`,
        arcs: unchanged.concat([first, second]),
      });
    }
  }
  return candidates;
}

const options = parseArguments(process.argv.slice(2));
const solutions = loadBundledSolutions();
const code = solutions[options.sourceSize];
if (!code || !code.startsWith("o")) {
  throw new Error(`No bundled rot4 solution exists at n=${options.sourceSize}.`);
}

const oldArcs = arcsFromCode(options.sourceSize, code);
const candidates = generateLifts(oldArcs, options.sourceSize / 2);
for (const candidate of candidates) {
  candidate.energy = energy(options.targetSize, candidate.arcs);
}
candidates.sort((a, b) => a.energy.triples - b.energy.triples);
const liftEnergies = candidates
  .map((candidate) => candidate.energy.triples)
  .sort((a, b) => a - b);

const random = makeRandom(options.seed);
const randomEnergies = [];
for (let sample = 0; sample < options.samples; sample++) {
  randomEnergies.push(
    energy(
      options.targetSize,
      randomHamiltonian(options.targetSize / 2, random),
    ).triples,
  );
}
randomEnergies.sort((a, b) => a - b);
const percentile = (values, p) => values[Math.floor(p * (values.length - 1))];
const mean = (values) =>
  values.reduce((sum, value) => sum + value, 0) / values.length;
const randomMinimum = randomEnergies[0];

console.log(
  JSON.stringify(
    {
      sourceSize: options.sourceSize,
      targetSize: options.targetSize,
      seed: options.seed,
      lifts: candidates.length,
      liftEnergy: {
        min: liftEnergies[0],
        p05: percentile(liftEnergies, 0.05),
        median: percentile(liftEnergies, 0.5),
        mean: mean(liftEnergies),
        p95: percentile(liftEnergies, 0.95),
        max: liftEnergies[liftEnergies.length - 1],
      },
      bestLifts: candidates.slice(0, 10).map(({ kind, energy: result }) => ({
        kind,
        ...result,
      })),
      randomHamiltonian: {
        samples: randomEnergies.length,
        min: randomMinimum,
        p05: percentile(randomEnergies, 0.05),
        median: percentile(randomEnergies, 0.5),
        mean: mean(randomEnergies),
        p95: percentile(randomEnergies, 0.95),
        max: randomEnergies[randomEnergies.length - 1],
      },
      liftFractionBelowRandomMinimum:
        candidates.filter((candidate) => candidate.energy.triples < randomMinimum)
          .length / candidates.length,
    },
    null,
    2,
  ),
);
