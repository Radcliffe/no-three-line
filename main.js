const MIN_SIZE = 3;
const MAX_SIZE = NoThreeLineCodec.ALPHABET.length;

const gridSizeSelect = document.getElementById("gridSize");
const grid = document.getElementById("grid");
const activeCountEl = document.getElementById("activeCount");
const lineWarning = document.getElementById("lineWarning");
const clearBtn = document.getElementById("clearBtn");
const solutionBtn = document.getElementById("solutionBtn");
const targetCount = document.getElementById("targetCount");
const symmetrySelect = document.getElementById("symmetry");
const configurationCode = document.getElementById("configurationCode");
const loadCodeBtn = document.getElementById("loadCodeBtn");
const codeStatus = document.getElementById("codeStatus");

let size = 3;
let activeCells = new Set();
let cellsByKey = new Map();
let symmetry = "iden";

function key(row, col) {
  return `${row},${col}`;
}

function parseKey(cellKey) {
  return cellKey.split(",").map(Number);
}

function gcd(a, b) {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b > 0) {
    const temp = b;
    b = a % b;
    a = temp;
  }
  return a;
}

function canonicalLine(row, col, dRow, dCol) {
  const divisor = gcd(dRow, dCol);
  let stepRow = dRow / divisor;
  let stepCol = dCol / divisor;

  if (stepRow < 0 || (stepRow === 0 && stepCol < 0)) {
    stepRow *= -1;
    stepCol *= -1;
  }

  let maxBack = Infinity;

  if (stepRow > 0) {
    maxBack = Math.min(maxBack, Math.floor(row / stepRow));
  } else if (stepRow < 0) {
    maxBack = Math.min(maxBack, Math.floor((size - 1 - row) / -stepRow));
  }

  if (stepCol > 0) {
    maxBack = Math.min(maxBack, Math.floor(col / stepCol));
  } else if (stepCol < 0) {
    maxBack = Math.min(maxBack, Math.floor((size - 1 - col) / -stepCol));
  }

  const startRow = row - maxBack * stepRow;
  const startCol = col - maxBack * stepCol;

  return `${startRow},${startCol}|${stepRow},${stepCol}`;
}

function findLineViolations() {
  const active = Array.from(activeCells).map(parseKey);
  const lines = new Map();
  const badCells = new Set();

  for (let i = 0; i < active.length; i++) {
    for (let j = i + 1; j < active.length; j++) {
      const [r1, c1] = active[i];
      const [r2, c2] = active[j];
      const lineKey = canonicalLine(r1, c1, r2 - r1, c2 - c1);

      if (!lines.has(lineKey)) {
        lines.set(lineKey, new Set());
      }
      lines.get(lineKey).add(key(r1, c1));
      lines.get(lineKey).add(key(r2, c2));
    }
  }

  for (const lineCells of lines.values()) {
    if (lineCells.size >= 3) {
      for (const cellKey of lineCells) {
        badCells.add(cellKey);
      }
    }
  }

  return badCells;
}

function cellSizeForGrid(n) {
  const availableWidth = Math.min(window.innerWidth - 80, 1060);
  const gap = n <= 18 ? 3 : n <= 40 ? 2 : 1;
  const raw = Math.floor((availableWidth - gap * (n + 1)) / n);
  return Math.max(7, Math.min(42, raw));
}

function renderGrid() {
  activeCells.clear();
  cellsByKey.clear();
  grid.innerHTML = "";
  grid.style.setProperty("--size", size);
  grid.style.setProperty("--cell-size", `${cellSizeForGrid(size)}px`);
  grid.style.setProperty(
    "--gap-size",
    size <= 18 ? "3px" : size <= 40 ? "2px" : "1px",
  );
  grid.style.setProperty(
    "--cell-radius",
    size <= 18 ? "7px" : size <= 40 ? "4px" : "2px",
  );

  const fragment = document.createDocumentFragment();
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      const button = document.createElement("button");
      const cellKey = key(row, col);
      button.type = "button";
      button.className = "cell";
      button.dataset.row = String(row);
      button.dataset.col = String(col);
      button.setAttribute("role", "gridcell");
      button.setAttribute(
        "aria-label",
        `Row ${row + 1}, column ${col + 1}, inactive`,
      );
      button.title = `(${row}, ${col})`;
      cellsByKey.set(cellKey, button);
      fragment.appendChild(button);
    }
  }

  grid.appendChild(fragment);
  updateSolutionButton();
  updateDisplay();
}

function updateDisplay() {
  const badCells = findLineViolations();

  for (const [cellKey, cell] of cellsByKey.entries()) {
    const isActive = activeCells.has(cellKey);
    const isBad = badCells.has(cellKey);
    const [row, col] = parseKey(cellKey);

    cell.classList.toggle("active", isActive);
    cell.classList.toggle("line-hit", isBad);
    cell.setAttribute(
      "aria-label",
      `Row ${row + 1}, column ${col + 1}, ${isActive ? "active" : "inactive"}${isBad ? ", on a line with three or more active cells" : ""}`,
    );
  }

  activeCountEl.textContent = String(activeCells.size);
  lineWarning.classList.toggle("visible", badCells.size > 0);
  updateConfigurationCode();
}

function activeCellCoordinates() {
  return Array.from(activeCells, parseKey);
}

function updateConfigurationCode() {
  try {
    configurationCode.value = NoThreeLineCodec.encodeConfiguration(
      activeCellCoordinates(),
      size,
      symmetry,
    );
  } catch {
    configurationCode.value = "";
  }
  codeStatus.textContent = "";
  codeStatus.classList.remove("error");
}

function setActiveCells(cells) {
  activeCells.clear();
  for (const [row, col] of cells) {
    if (
      Number.isInteger(row) &&
      Number.isInteger(col) &&
      row >= 0 &&
      row < size &&
      col >= 0 &&
      col < size
    ) {
      activeCells.add(key(row, col));
    }
  }
  updateDisplay();
}

function clearGrid() {
  activeCells.clear();
  symmetrySelect.value = "iden";
  symmetry = "iden";
  updateDisplay();
}

function updateSolutionButton() {
  solutionBtn.disabled = !optimalSolutions?.[size];
}

function showOptimalSolution() {
  const code = optimalSolutions[size];
  if (!code) return;
  const solution = NoThreeLineCodec.decodeConfiguration(code, size);
  symmetry = solution.symmetryGroup;
  symmetrySelect.value = symmetry;
  setActiveCells(solution.cells);
}

function loadConfigurationCode() {
  try {
    const solution = NoThreeLineCodec.decodeConfiguration(configurationCode.value);
    if (solution.size < MIN_SIZE || solution.size > MAX_SIZE) {
      throw new Error(`The app supports grid sizes from ${MIN_SIZE} to ${MAX_SIZE}.`);
    }
    size = solution.size;
    gridSizeSelect.value = String(size);
    targetCount.textContent = String(size * 2);
    symmetry = solution.symmetryGroup;
    symmetrySelect.value = symmetry;
    renderGrid();
    setActiveCells(solution.cells);
    codeStatus.textContent = `Loaded ${size} × ${size} configuration.`;
  } catch (error) {
    codeStatus.textContent = error.message;
    codeStatus.classList.add("error");
  }
}

function populateSizeSelect() {
  for (let n = MIN_SIZE; n <= MAX_SIZE; n++) {
    const option = document.createElement("option");
    option.value = String(n);
    option.textContent = `${n} × ${n}`;
    if (n === size) option.selected = true;
    gridSizeSelect.appendChild(option);
  }
}

grid.addEventListener("click", (event) => {
  const cell = event.target.closest(".cell");
  if (!cell) return;
  toggleCell(cell.dataset.row, cell.dataset.col);
  updateDisplay();
});

gridSizeSelect.addEventListener("change", () => {
  size = Number(gridSizeSelect.value);
  targetCount.textContent = String(size * 2);
  symmetry = "iden";
  symmetrySelect.value = symmetry;
  renderGrid();
});

symmetrySelect.addEventListener("change", () => {
  symmetry = symmetrySelect.value;
  makeGridSymmetric();
});

function updateCell(row, col, method) {
  const cellKey = key(row, col);
  method(cellKey);
  // (r, c) -> (c, r)
  if (symmetry === "dia1" || symmetry === "dia2" || symmetry === "full") {
    method(key(col, row));
  }
  // (r, c) -> (c, s-r-1)
  if (symmetry === "rot4" || symmetry === "rct4" || symmetry === "full") {
    method(key(col, size - row - 1));
  }
  // (r, c) -> (s-r-1, c)
  if (symmetry === "ort1" || symmetry === "ort2" || symmetry === "full") {
    method(key(size - row - 1, col));
  }
  // (r, c) -> (s-r-1, s-c-1)
  if (
    symmetry === "rot2" ||
    symmetry === "rot4" ||
    symmetry === "rct4" ||
    symmetry === "ort2" ||
    symmetry === "dia2" ||
    symmetry === "full"
  ) {
    method(key(size - row - 1, size - col - 1));
  }
  // (r, c) -> (s-c-1, s-r-1)
  if (symmetry === "dia2" || symmetry === "full") {
    method(key(size - col - 1, size - row - 1));
  }
  // (r, c) -> (c, s-r-1), (r, c) -> (s-c-1, r)
  if (symmetry === "rot4" || symmetry === "rct4" || symmetry === "full") {
    method(key(col, size - row - 1));
    method(key(size - col - 1, row));
  }
  // (r, c) -> (r, s-c-1)
  if (symmetry === "ort2" || symmetry === "full") {
    method(key(row, size - col - 1));
  }
  updateDisplay();
}

function toggleCell(row, col) {
  const cellKey = key(row, col);
  if (activeCells.has(cellKey)) {
    updateCell(row, col, (k) => activeCells.delete(k));
  } else {
    updateCell(row, col, (k) => activeCells.add(k));
  }
  updateDisplay();
}

function makeGridSymmetric() {
  const copy = new Set(activeCells);
  for (let cellKey of copy) {
    const [row, col] = parseKey(cellKey);
    updateCell(row, col, (k) => activeCells.add(k));
  }
  updateDisplay();
}

clearBtn.addEventListener("click", clearGrid);
solutionBtn.addEventListener("click", showOptimalSolution);
loadCodeBtn.addEventListener("click", loadConfigurationCode);

window.addEventListener("resize", () => {
  grid.style.setProperty("--cell-size", `${cellSizeForGrid(size)}px`);
});

populateSizeSelect();
renderGrid();
