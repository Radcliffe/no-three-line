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
const disableBlockedCellsInput = document.getElementById("disableBlockedCells");

let size = 3;
let activeCells = new Set();
let cellsByKey = new Map();
let lineIndex = new NoThreeLineCodec.LineIndex(size);
let symmetry = "iden";
let disableBlockedCells =
  NoThreeLineCodec.DEFAULT_OPTIONS.disableBlockedCells;

disableBlockedCellsInput.checked = disableBlockedCells;

function key(row, col) {
  return `${row},${col}`;
}

function parseKey(cellKey) {
  return cellKey.split(",").map(Number);
}

function cellSizeForGrid(n) {
  const availableWidth = Math.min(window.innerWidth - 80, 1060);
  const gap = n <= 18 ? 3 : n <= 40 ? 2 : 1;
  const raw = Math.floor((availableWidth - gap * (n + 1)) / n);
  return Math.max(7, Math.min(42, raw));
}

function renderGrid() {
  activeCells.clear();
  lineIndex = new NoThreeLineCodec.LineIndex(size);
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
  const badCells = lineIndex.getViolationCells();
  const blockedCells = disableBlockedCells
    ? lineIndex.getBlockedCells()
    : new Set();

  for (const [cellKey, cell] of cellsByKey.entries()) {
    const isActive = activeCells.has(cellKey);
    const isBad = badCells.has(cellKey);
    const isBlocked = !isActive && blockedCells.has(cellKey);
    const [row, col] = parseKey(cellKey);

    cell.classList.toggle("active", isActive);
    cell.classList.toggle("line-hit", isBad);
    cell.classList.toggle("blocked", isBlocked);
    cell.disabled = isBlocked;
    cell.title = isBlocked
      ? `(${row}, ${col}) — selecting this cell would make three in a line`
      : `(${row}, ${col})`;
    cell.setAttribute(
      "aria-label",
      `Row ${row + 1}, column ${col + 1}, ${isActive ? "active" : "inactive"}${isBad ? ", on a line with three or more active cells" : ""}${isBlocked ? ", unavailable because it would make three in a line" : ""}`,
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
  lineIndex.clear();
  for (const [row, col] of cells) {
    if (
      Number.isInteger(row) &&
      Number.isInteger(col) &&
      row >= 0 &&
      row < size &&
      col >= 0 &&
      col < size
    ) {
      addActiveCell(key(row, col));
    }
  }
  updateDisplay();
}

function clearGrid() {
  activeCells.clear();
  lineIndex.clear();
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

disableBlockedCellsInput.addEventListener("change", () => {
  disableBlockedCells = disableBlockedCellsInput.checked;
  updateDisplay();
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
}

function addActiveCell(cellKey) {
  if (activeCells.has(cellKey)) return;
  const [row, col] = parseKey(cellKey);
  lineIndex.add(row, col);
  activeCells.add(cellKey);
}

function deleteActiveCell(cellKey) {
  if (!activeCells.has(cellKey)) return;
  const [row, col] = parseKey(cellKey);
  lineIndex.remove(row, col);
  activeCells.delete(cellKey);
}

function toggleCell(row, col) {
  const cellKey = key(row, col);
  if (activeCells.has(cellKey)) {
    updateCell(row, col, deleteActiveCell);
  } else {
    updateCell(row, col, addActiveCell);
  }
}

function makeGridSymmetric() {
  const copy = new Set(activeCells);
  for (let cellKey of copy) {
    const [row, col] = parseKey(cellKey);
    updateCell(row, col, addActiveCell);
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

const queryCode = new URLSearchParams(window.location.search).get("code");
if (queryCode !== null) {
  configurationCode.value = queryCode;
  loadConfigurationCode();
}
