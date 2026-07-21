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
    SYMMETRY_CHARACTER,
    SYMMETRY_GROUP,
    decodeConfiguration,
    encodeConfiguration,
  });
})(globalThis);
