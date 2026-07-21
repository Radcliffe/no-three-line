(function (root) {
  "use strict";

  const ALPHABET =
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&@?!()[]<>{}=*+|-/~^_:;,.";

  const SYMMETRY_CHARACTER = Object.freeze({
    iden: ".",
    rot2: ":",
    dia1: "/",
    ort1: "-",
    rot4: "o",
    rct4: "c",
    dia2: "x",
    ort2: "+",
    full: "*",
  });

  const SYMMETRY_GROUP = Object.freeze(
    Object.fromEntries(
      Object.entries(SYMMETRY_CHARACTER).map(([group, character]) => [
        character,
        group,
      ]),
    ),
  );

  const DEFAULT_OPTIONS = Object.freeze({
    disableBlockedCells: true,
  });

  function gcd(a, b) {
    a = Math.abs(a);
    b = Math.abs(b);
    while (b > 0) {
      const remainder = a % b;
      a = b;
      b = remainder;
    }
    return a;
  }

  function cellKey(row, column) {
    return `${row},${column}`;
  }

  function lineThrough(row, column, otherRow, otherColumn, size) {
    let stepRow = otherRow - row;
    let stepColumn = otherColumn - column;
    const divisor = gcd(stepRow, stepColumn);
    stepRow /= divisor;
    stepColumn /= divisor;

    if (stepRow < 0 || (stepRow === 0 && stepColumn < 0)) {
      stepRow *= -1;
      stepColumn *= -1;
    }

    let startRow = row;
    let startColumn = column;
    while (
      startRow - stepRow >= 0 &&
      startRow - stepRow < size &&
      startColumn - stepColumn >= 0 &&
      startColumn - stepColumn < size
    ) {
      startRow -= stepRow;
      startColumn -= stepColumn;
    }

    return {
      key: `${startRow},${startColumn}|${stepRow},${stepColumn}`,
      startRow,
      startColumn,
      stepRow,
      stepColumn,
    };
  }

  class LineIndex {
    constructor(size) {
      if (!Number.isInteger(size) || size < 1 || size > ALPHABET.length) {
        throw new Error(`Grid size must be between 1 and ${ALPHABET.length}.`);
      }
      this.size = size;
      this.clear();
    }

    clear() {
      this.selectedCells = new Map();
      this.lines = new Map();
      this.pointLines = new Map();
      this.blockedCounts = new Map();
      this.blockedLineKeys = new Map();
      this.badCounts = new Map();
      this.blockedCells = new Set();
      this.badCells = new Set();
    }

    validateCell(row, column) {
      if (
        !Number.isInteger(row) ||
        !Number.isInteger(column) ||
        row < 0 ||
        row >= this.size ||
        column < 0 ||
        column >= this.size
      ) {
        throw new Error("The configuration contains a cell outside the grid.");
      }
    }

    changeBadCount(key, change) {
      const count = (this.badCounts.get(key) || 0) + change;
      if (count > 0) {
        this.badCounts.set(key, count);
        this.badCells.add(key);
      } else {
        this.badCounts.delete(key);
        this.badCells.delete(key);
      }
    }

    changeBlockedLine(line, change) {
      let row = line.startRow;
      let column = line.startColumn;
      while (
        row >= 0 &&
        row < this.size &&
        column >= 0 &&
        column < this.size
      ) {
        const key = cellKey(row, column);
        const count = (this.blockedCounts.get(key) || 0) + change;
        let lineKeys = this.blockedLineKeys.get(key);
        if (change > 0) {
          if (!lineKeys) {
            lineKeys = new Set();
            this.blockedLineKeys.set(key, lineKeys);
          }
          lineKeys.add(line.key);
        } else if (lineKeys) {
          lineKeys.delete(line.key);
          if (lineKeys.size === 0) this.blockedLineKeys.delete(key);
        }
        if (count > 0) {
          this.blockedCounts.set(key, count);
          if (!this.selectedCells.has(key)) {
            this.blockedCells.add(key);
          }
        } else {
          this.blockedCounts.delete(key);
          this.blockedCells.delete(key);
        }
        row += line.stepRow;
        column += line.stepColumn;
      }
    }

    add(row, column) {
      this.validateCell(row, column);
      const key = cellKey(row, column);
      if (this.selectedCells.has(key)) return false;

      const existingCells = Array.from(this.selectedCells.entries());
      this.selectedCells.set(key, [row, column]);
      this.pointLines.set(key, new Set());
      this.blockedCells.delete(key);

      const affectedLines = new Map();
      for (const [otherKey, [otherRow, otherColumn]] of existingCells) {
        const line = lineThrough(row, column, otherRow, otherColumn, this.size);
        if (!affectedLines.has(line.key)) {
          affectedLines.set(line.key, { line, otherKey });
        }
      }

      for (const { line, otherKey } of affectedLines.values()) {
        let record = this.lines.get(line.key);
        if (!record) {
          record = { ...line, points: new Set([otherKey, key]) };
          this.lines.set(line.key, record);
          this.pointLines.get(otherKey).add(line.key);
          this.pointLines.get(key).add(line.key);
          this.changeBlockedLine(record, 1);
          continue;
        }

        const previousCount = record.points.size;
        record.points.add(key);
        this.pointLines.get(key).add(line.key);
        if (previousCount === 2) {
          for (const pointKey of record.points) {
            this.changeBadCount(pointKey, 1);
          }
        } else {
          this.changeBadCount(key, 1);
        }
      }
      return true;
    }

    remove(row, column) {
      this.validateCell(row, column);
      const key = cellKey(row, column);
      if (!this.selectedCells.has(key)) return false;

      const incidentLines = Array.from(this.pointLines.get(key));
      for (const lineKey of incidentLines) {
        const record = this.lines.get(lineKey);
        const previousCount = record.points.size;

        if (previousCount === 3) {
          for (const pointKey of record.points) {
            this.changeBadCount(pointKey, -1);
          }
        } else if (previousCount > 3) {
          this.changeBadCount(key, -1);
        }

        record.points.delete(key);
        if (previousCount === 2) {
          this.changeBlockedLine(record, -1);
          for (const remainingKey of record.points) {
            this.pointLines.get(remainingKey).delete(lineKey);
          }
          this.lines.delete(lineKey);
        }
      }

      this.pointLines.delete(key);
      this.selectedCells.delete(key);
      this.badCounts.delete(key);
      this.badCells.delete(key);
      if (this.blockedCounts.has(key)) {
        this.blockedCells.add(key);
      }
      return true;
    }

    getBlockedCells() {
      return this.blockedCells;
    }

    getViolationCells() {
      return this.badCells;
    }

    describeLine(line, extraCells = []) {
      const points = new Map();
      if (line.points) {
        for (const pointKey of line.points) {
          const point = this.selectedCells.get(pointKey);
          if (point) points.set(pointKey, point);
        }
      }
      for (const [row, column] of extraCells) {
        points.set(cellKey(row, column), [row, column]);
      }
      return {
        key: line.key,
        startRow: line.startRow,
        startColumn: line.startColumn,
        stepRow: line.stepRow,
        stepColumn: line.stepColumn,
        points: Array.from(points.values()),
      };
    }

    getBlockingLines(row, column) {
      this.validateCell(row, column);
      const lineKeys = this.blockedLineKeys.get(cellKey(row, column));
      if (!lineKeys) return [];
      return Array.from(lineKeys, (lineKey) =>
        this.describeLine(this.lines.get(lineKey)),
      );
    }

    getViolationLines() {
      const violations = [];
      for (const line of this.lines.values()) {
        if (line.points.size >= 3) violations.push(this.describeLine(line));
      }
      return violations;
    }

    findViolationLinesAfterAdding(cells) {
      const candidates = new Map();
      for (const [row, column] of cells) {
        this.validateCell(row, column);
        const key = cellKey(row, column);
        if (!this.selectedCells.has(key)) candidates.set(key, [row, column]);
      }

      const candidateCells = Array.from(candidates.values());
      const violations = new Map();
      const addIfViolation = (line) => {
        if (violations.has(line.key)) return;
        const points = [];
        let row = line.startRow;
        let column = line.startColumn;
        while (
          row >= 0 &&
          row < this.size &&
          column >= 0 &&
          column < this.size
        ) {
          const key = cellKey(row, column);
          if (this.selectedCells.has(key) || candidates.has(key)) {
            points.push([row, column]);
          }
          row += line.stepRow;
          column += line.stepColumn;
        }
        if (points.length >= 3) {
          violations.set(line.key, this.describeLine(line, points));
        }
      };

      for (const [row, column] of candidateCells) {
        const lineKeys = this.blockedLineKeys.get(cellKey(row, column));
        if (!lineKeys) continue;
        for (const lineKey of lineKeys) addIfViolation(this.lines.get(lineKey));
      }

      for (let first = 0; first < candidateCells.length; first++) {
        for (let second = first + 1; second < candidateCells.length; second++) {
          const [firstRow, firstColumn] = candidateCells[first];
          const [secondRow, secondColumn] = candidateCells[second];
          addIfViolation(
            lineThrough(
              firstRow,
              firstColumn,
              secondRow,
              secondColumn,
              this.size,
            ),
          );
        }
      }

      return Array.from(violations.values());
    }
  }

  function findBlockedCells(cells, size) {
    if (!Number.isInteger(size) || size < 1 || size > ALPHABET.length) {
      throw new Error(`Grid size must be between 1 and ${ALPHABET.length}.`);
    }
    const index = new LineIndex(size);
    for (const [row, column] of cells) {
      index.add(row, column);
    }
    return new Set(index.getBlockedCells());
  }

  function readCode(value) {
    const match = String(value).match(/^(\S+)(?:[\t\n\r ]|$)/);
    if (!match) {
      throw new Error("Enter one configuration code.");
    }
    return match[1];
  }

  function decodeConfiguration(value, expectedSize) {
    const code = readCode(value);
    const symmetryGroup = SYMMETRY_GROUP[code[0]];
    if (!symmetryGroup) {
      throw new Error("The code starts with an unknown symmetry character.");
    }

    const payload = code.slice(1);
    const size = expectedSize ?? payload.length / 2;
    if (!Number.isInteger(size) || size < 1 || size > ALPHABET.length) {
      throw new Error("The code does not describe a supported square grid.");
    }
    if (payload.length !== size * 2) {
      throw new Error(`A ${size} × ${size} configuration needs ${size * 2} column characters.`);
    }

    const cells = [];
    for (let row = 0; row < size; row++) {
      const first = ALPHABET.indexOf(payload[row * 2]);
      const second = ALPHABET.indexOf(payload[row * 2 + 1]);
      if (first < 0 || second < 0) {
        throw new Error("The code contains a character outside the 90-character alphabet.");
      }
      if (first >= size || second >= size) {
        throw new Error(`The code selects a column outside its ${size} × ${size} grid.`);
      }
      if (first >= second) {
        throw new Error("Each row must contain two distinct columns in left-to-right order.");
      }
      cells.push([row, first], [row, second]);
    }

    return { code, size, symmetryGroup, cells };
  }

  function encodeConfiguration(cells, size, symmetryGroup) {
    if (!Number.isInteger(size) || size < 1 || size > ALPHABET.length) {
      throw new Error(`Grid size must be between 1 and ${ALPHABET.length}.`);
    }
    const symmetryCharacter = SYMMETRY_CHARACTER[symmetryGroup];
    if (!symmetryCharacter) {
      throw new Error(`Unknown symmetry group: ${symmetryGroup}`);
    }

    const columnsByRow = Array.from({ length: size }, () => []);
    for (const [row, column] of cells) {
      if (
        !Number.isInteger(row) ||
        !Number.isInteger(column) ||
        row < 0 ||
        row >= size ||
        column < 0 ||
        column >= size
      ) {
        throw new Error("The configuration contains a cell outside the grid.");
      }
      columnsByRow[row].push(column);
    }

    let payload = "";
    for (const columns of columnsByRow) {
      columns.sort((a, b) => a - b);
      if (columns.length !== 2 || columns[0] === columns[1]) {
        throw new Error("A coded configuration must select exactly two cells in every row.");
      }
      payload += ALPHABET[columns[0]] + ALPHABET[columns[1]];
    }
    return symmetryCharacter + payload;
  }

  root.NoThreeLineCodec = Object.freeze({
    ALPHABET,
    DEFAULT_OPTIONS,
    LineIndex,
    SYMMETRY_CHARACTER,
    SYMMETRY_GROUP,
    decodeConfiguration,
    encodeConfiguration,
    findBlockedCells,
  });
})(globalThis);
