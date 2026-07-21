const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

require("../configuration-codec.js");

const {
  ALPHABET,
  DEFAULT_OPTIONS,
  LineIndex,
  SYMMETRY_CHARACTER,
  SYMMETRY_GROUP,
  decodeConfiguration,
  encodeConfiguration,
  findBlockedCells,
} = globalThis.NoThreeLineCodec;

function sorted(values) {
  return [...values].sort();
}

function key(row, column) {
  return `${row},${column}`;
}

function collinear(a, b, c) {
  return (
    (b[0] - a[0]) * (c[1] - a[1]) ===
    (b[1] - a[1]) * (c[0] - a[0])
  );
}

function bruteForceState(selected, size) {
  const points = [...selected].map((value) => value.split(",").map(Number));
  const violations = new Set();
  const blocked = new Set();

  for (let first = 0; first < points.length; first++) {
    for (let second = first + 1; second < points.length; second++) {
      for (let row = 0; row < size; row++) {
        for (let column = 0; column < size; column++) {
          const candidateKey = key(row, column);
          if (
            !selected.has(candidateKey) &&
            collinear(points[first], points[second], [row, column])
          ) {
            blocked.add(candidateKey);
          }
        }
      }

      for (let third = second + 1; third < points.length; third++) {
        if (collinear(points[first], points[second], points[third])) {
          violations.add(key(...points[first]));
          violations.add(key(...points[second]));
          violations.add(key(...points[third]));
        }
      }
    }
  }

  return { blocked, violations };
}

function makeRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
}

test("the extended alphabet contains 90 unique printable characters", () => {
  assert.equal(ALPHABET.length, 90);
  assert.equal(new Set(ALPHABET).size, 90);
  assert.match(ALPHABET, /^[!-~]+$/);
});

test("symmetry characters form a reversible mapping", () => {
  assert.equal(Object.keys(SYMMETRY_CHARACTER).length, 9);
  for (const [group, character] of Object.entries(SYMMETRY_CHARACTER)) {
    assert.equal(SYMMETRY_GROUP[character], group);
  }
});

test("encoding sorts each row and round-trips every symmetry class", () => {
  const cells = [
    [0, 2], [0, 0],
    [1, 2], [1, 1],
    [2, 1], [2, 0],
  ];

  for (const group of Object.keys(SYMMETRY_CHARACTER)) {
    const code = encodeConfiguration(cells, 3, group);
    const decoded = decodeConfiguration(`${code}\nignored`);
    assert.equal(decoded.size, 3);
    assert.equal(decoded.symmetryGroup, group);
    assert.deepEqual(decoded.cells, [
      [0, 0], [0, 2],
      [1, 1], [1, 2],
      [2, 0], [2, 1],
    ]);
  }
});

test("codec supports the final column in the 90-character alphabet", () => {
  const cells = [];
  for (let row = 0; row < 90; row++) {
    cells.push([row, 0], [row, 89]);
  }
  const code = encodeConfiguration(cells, 90, "iden");
  assert.equal(code.length, 181);
  assert.equal(code.slice(1, 3), `0${ALPHABET[89]}`);
  assert.deepEqual(decodeConfiguration(code).cells, cells);
});

test("codec rejects malformed and ambiguous configurations", () => {
  assert.throws(() => decodeConfiguration(""), /Enter one configuration code/);
  assert.throws(() => decodeConfiguration("q010212"), /unknown symmetry/);
  assert.throws(() => decodeConfiguration(".01021"), /supported square grid/);
  assert.throws(() => decodeConfiguration(".200112", 3), /left-to-right order/);
  assert.throws(() => decodeConfiguration(".030112", 3), /outside its 3/);
  assert.throws(
    () => encodeConfiguration([[0, 0]], 1, "iden"),
    /exactly two cells/,
  );
  assert.throws(
    () => encodeConfiguration([[0, 0], [0, 1]], 2, "unknown"),
    /Unknown symmetry group/,
  );
});

test("blocked and violating cells update when points are added and removed", () => {
  const index = new LineIndex(5);
  index.add(0, 0);
  index.add(2, 2);

  assert.deepEqual(sorted(index.getBlockedCells()), ["1,1", "3,3", "4,4"]);
  assert.deepEqual(sorted(index.getViolationCells()), []);

  index.add(4, 4);
  assert.deepEqual(sorted(index.getViolationCells()), ["0,0", "2,2", "4,4"]);
  assert.deepEqual(sorted(index.getBlockedCells()), ["1,1", "3,3"]);

  index.remove(2, 2);
  assert.deepEqual(sorted(index.getViolationCells()), []);
  assert.deepEqual(sorted(index.getBlockedCells()), ["1,1", "2,2", "3,3"]);
});

test("incremental line index matches brute force through random edits", () => {
  for (let seed = 1; seed <= 12; seed++) {
    const random = makeRandom(seed);
    const size = 3 + (seed % 5);
    const index = new LineIndex(size);
    const selected = new Set();

    for (let step = 0; step < 150; step++) {
      const row = Math.floor(random() * size);
      const column = Math.floor(random() * size);
      const cellKey = key(row, column);
      if (selected.has(cellKey)) {
        assert.equal(index.remove(row, column), true);
        selected.delete(cellKey);
      } else {
        assert.equal(index.add(row, column), true);
        selected.add(cellKey);
      }

      const expected = bruteForceState(selected, size);
      assert.deepEqual(sorted(index.getBlockedCells()), sorted(expected.blocked));
      assert.deepEqual(
        sorted(index.getViolationCells()),
        sorted(expected.violations),
      );
    }
  }
});

test("findBlockedCells agrees with a directly populated index", () => {
  const cells = [[0, 0], [1, 2], [3, 1], [4, 4]];
  const index = new LineIndex(5);
  for (const [row, column] of cells) index.add(row, column);
  assert.deepEqual(
    sorted(findBlockedCells(cells, 5)),
    sorted(index.getBlockedCells()),
  );
  assert.equal(DEFAULT_OPTIONS.disableBlockedCells, true);
});

test("every bundled optimal solution decodes and has no three in line", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "..", "optimal-solutions.generated.js"),
    "utf8",
  );
  const context = vm.createContext({});
  vm.runInContext(`${source}\nthis.solutions = optimalSolutions;`, context);

  assert.equal(Object.keys(context.solutions).length, 70);
  for (const [sizeText, code] of Object.entries(context.solutions)) {
    const size = Number(sizeText);
    const decoded = decodeConfiguration(code, size);
    const index = new LineIndex(size);
    for (const [row, column] of decoded.cells) index.add(row, column);

    assert.equal(decoded.cells.length, size * 2, `size ${size}`);
    assert.equal(index.getViolationCells().size, 0, `size ${size}`);
    assert.equal(encodeConfiguration(decoded.cells, size, decoded.symmetryGroup), code);
  }
});
