#!/usr/bin/env node
"use strict";

const path = require("node:path");

const alphabet =
  "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&@?!()[]<>{}=*+|-/~^_:;,.";
const projectRoot = path.resolve(__dirname, "..");
require(path.join(projectRoot, "configuration-codec.js"));
const codec = globalThis.NoThreeLineCodec;

function gcd(first, second) {
  first = Math.abs(first);
  second = Math.abs(second);
  while (second) [first, second] = [second, first % second];
  return first;
}

function lineKey([firstRow, firstColumn], [secondRow, secondColumn]) {
  let a = secondRow - firstRow;
  let b = firstColumn - secondColumn;
  let c = -(a * firstColumn + b * firstRow);
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

function independentCheck(code) {
  if (!code.startsWith("o") || (code.length - 1) % 2 !== 0) {
    throw new Error("Expected a compact rot4 code with two columns per row.");
  }
  const n = (code.length - 1) / 2;
  if (n < 6 || n > 90 || n % 2 !== 0) throw new Error(`Unsupported even grid size ${n}.`);

  const cells = [];
  const cellSet = new Set();
  for (let row = 0; row < n; row++) {
    for (let slot = 0; slot < 2; slot++) {
      const column = alphabet.indexOf(code[1 + 2 * row + slot]);
      const key = `${row},${column}`;
      if (column < 0 || column >= n || cellSet.has(key)) {
        throw new Error(`Invalid or duplicate cell in row ${row}.`);
      }
      cells.push([row, column]);
      cellSet.add(key);
    }
  }

  const rotated = cells.every(([row, column]) =>
    cellSet.has(`${column},${n - 1 - row}`),
  );
  const m = n / 2;
  const arcs = cells.filter(([row, column]) => row < m && column < m);
  const degrees = Array(m).fill(0);
  for (const [first, second] of arcs) {
    if (first === second) degrees[first] += 2;
    else {
      degrees[first]++;
      degrees[second]++;
    }
  }
  const rowPerfectFactor =
    arcs.length === m && degrees.every((degree) => degree === 2);

  const lines = new Map();
  for (let first = 0; first < cells.length; first++) {
    for (let second = first + 1; second < cells.length; second++) {
      const key = lineKey(cells[first], cells[second]);
      let members = lines.get(key);
      if (!members) {
        members = new Set();
        lines.set(key, members);
      }
      members.add(first);
      members.add(second);
    }
  }
  let violatingLines = 0;
  let triples = 0;
  for (const members of lines.values()) {
    const count = members.size;
    if (count < 3) continue;
    violatingLines++;
    triples += (count * (count - 1) * (count - 2)) / 6;
  }
  return { n, points: cells.length, rotated, rowPerfectFactor, violatingLines, triples };
}

function applicationCheck(code) {
  const decoded = codec.decodeConfiguration(code);
  const index = new codec.LineIndex(decoded.size);
  for (const point of decoded.cells) index.add(...point);
  return {
    n: decoded.size,
    points: decoded.cells.length,
    symmetryGroup: decoded.symmetryGroup,
    violatingLines: index.getViolationLines().length,
  };
}

try {
  const code = process.argv[2];
  if (!code) throw new Error("Usage: validate-rot4-code.js CODE");
  const research = independentCheck(code);
  const application = applicationCheck(code);
  const valid =
    research.rotated &&
    research.rowPerfectFactor &&
    research.violatingLines === 0 &&
    application.symmetryGroup === "rot4" &&
    application.points === 2 * application.n &&
    application.violatingLines === 0 &&
    application.n === research.n;
  console.log(JSON.stringify({ valid, research, application }, null, 2));
  process.exitCode = valid ? 0 : 1;
} catch (error) {
  console.error(JSON.stringify({ valid: false, error: error.message }, null, 2));
  process.exitCode = 2;
}
