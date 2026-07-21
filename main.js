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
const undoBtn = document.getElementById("undoBtn");
const redoBtn = document.getElementById("redoBtn");
const copyLinkBtn = document.getElementById("copyLinkBtn");
const lineExplanation = document.getElementById("lineExplanation");

const HISTORY_LIMIT = 100;
const LINE_EXPLANATION_HELP =
  "Hover over a gray or red cell to see the responsible line.";

let size = 3;
let activeCells = new Set();
let cellsByKey = new Map();
let lineIndex = new NoThreeLineCodec.LineIndex(size);
let symmetry = "iden";
let disableBlockedCells =
  NoThreeLineCodec.DEFAULT_OPTIONS.disableBlockedCells;
let undoStack = [];
let redoStack = [];
let urlSyncEnabled = false;
let cellLineExplanations = new Map();
let explainedCellKeys = new Set();

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

function renderGrid(initialCells = []) {
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
  for (const [row, col] of initialCells) {
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
  updateSolutionButton();
  updateDisplay();
}

function updateDisplay() {
  clearLineExplanation();
  const badCells = lineIndex.getViolationCells();
  const blockedState = computeBlockedState();
  const blockedCells = blockedState.cells;
  cellLineExplanations = blockedState.explanations;

  for (const line of lineIndex.getViolationLines()) {
    for (const [row, col] of line.points) {
      const cellKey = key(row, col);
      if (activeCells.has(cellKey)) addLineExplanations(cellKey, [line]);
    }
  }

  for (const [cellKey, cell] of cellsByKey.entries()) {
    const isActive = activeCells.has(cellKey);
    const isBad = badCells.has(cellKey);
    const isBlocked = !isActive && blockedCells.has(cellKey);
    const isOrbitBlocked = blockedState.orbitCells.has(cellKey);
    const [row, col] = parseKey(cellKey);

    cell.classList.toggle("active", isActive);
    cell.classList.toggle("line-hit", isBad);
    cell.classList.toggle("blocked", isBlocked);
    cell.disabled = isBlocked;
    cell.title = isBlocked
      ? `(${row}, ${col}) — selecting ${isOrbitBlocked ? "this symmetry orbit" : "this cell"} would make three in a line`
      : `(${row}, ${col})`;
    cell.setAttribute(
      "aria-label",
      `Row ${row + 1}, column ${col + 1}, ${isActive ? "active" : "inactive"}${isBad ? ", on a line with three or more active cells" : ""}${isBlocked ? `, unavailable because ${isOrbitBlocked ? "its symmetry orbit" : "it"} would make three in a line` : ""}`,
    );
  }

  activeCountEl.textContent = String(activeCells.size);
  lineWarning.classList.toggle("visible", badCells.size > 0);
  updateConfigurationCode();
}

function addLineExplanations(cellKey, lines) {
  let explanations = cellLineExplanations.get(cellKey);
  if (!explanations) {
    explanations = new Map();
    cellLineExplanations.set(cellKey, explanations);
  }
  for (const line of lines) explanations.set(line.key, line);
}

function computeBlockedState() {
  const cells = new Set();
  const orbitCells = new Set();
  const explanations = new Map();
  if (!disableBlockedCells) return { cells, orbitCells, explanations };

  cellLineExplanations = explanations;
  if (symmetry === "iden") {
    for (const blockedKey of lineIndex.getBlockedCells()) {
      cells.add(blockedKey);
      const [row, col] = parseKey(blockedKey);
      addLineExplanations(blockedKey, lineIndex.getBlockingLines(row, col));
    }
    return { cells, orbitCells, explanations };
  }

  const processed = new Set();
  for (const cellKey of cellsByKey.keys()) {
    if (activeCells.has(cellKey) || processed.has(cellKey)) continue;
    const [row, col] = parseKey(cellKey);
    const orbit = symmetricCellKeys(row, col);
    const candidates = [];
    for (const orbitKey of orbit) {
      processed.add(orbitKey);
      if (!activeCells.has(orbitKey)) candidates.push(parseKey(orbitKey));
    }
    const lines = lineIndex.findViolationLinesAfterAdding(candidates);
    if (lines.length === 0) continue;
    for (const [candidateRow, candidateCol] of candidates) {
      const candidateKey = key(candidateRow, candidateCol);
      cells.add(candidateKey);
      orbitCells.add(candidateKey);
      addLineExplanations(candidateKey, lines);
    }
  }
  return { cells, orbitCells, explanations };
}

function clearLineExplanation() {
  for (const cellKey of explainedCellKeys) {
    const cell = cellsByKey.get(cellKey);
    cell?.classList.remove(
      "line-explained",
      "line-source",
      "orbit-explained",
    );
  }
  explainedCellKeys.clear();
  lineExplanation.textContent = LINE_EXPLANATION_HELP;
  lineExplanation.classList.remove("visible");
}

function showLineExplanation(cell) {
  clearLineExplanation();
  const cellKey = key(cell.dataset.row, cell.dataset.col);
  const explanationMap = cellLineExplanations.get(cellKey);
  if (!explanationMap || explanationMap.size === 0) return;

  const lines = Array.from(explanationMap.values());
  const orbit = symmetricCellKeys(cell.dataset.row, cell.dataset.col);
  if (cell.classList.contains("blocked") && orbit.size > 1) {
    for (const orbitKey of orbit) {
      cellsByKey.get(orbitKey)?.classList.add("orbit-explained");
      explainedCellKeys.add(orbitKey);
    }
  }
  for (const line of lines) {
    let row = line.startRow;
    let col = line.startColumn;
    while (row >= 0 && row < size && col >= 0 && col < size) {
      const lineCellKey = key(row, col);
      cellsByKey.get(lineCellKey)?.classList.add("line-explained");
      explainedCellKeys.add(lineCellKey);
      row += line.stepRow;
      col += line.stepColumn;
    }
    for (const [pointRow, pointCol] of line.points) {
      const pointKey = key(pointRow, pointCol);
      if (activeCells.has(pointKey)) {
        cellsByKey.get(pointKey)?.classList.add("line-source");
        explainedCellKeys.add(pointKey);
      }
    }
  }

  const lineCount = lines.length;
  if (cell.classList.contains("blocked")) {
    lineExplanation.textContent = `${orbit.size > 1 ? "The outlined symmetry orbit" : "This move"} would create three in a line${lineCount > 1 ? ` on ${lineCount} highlighted lines` : " on the highlighted line"}.`;
  } else {
    lineExplanation.textContent = `This point belongs to ${lineCount > 1 ? `${lineCount} violating lines` : "a violating line"}; ${lineCount > 1 ? "they are" : "it is"} highlighted.`;
  }
  lineExplanation.classList.add("visible");
}

function activeCellCoordinates() {
  return Array.from(activeCells, parseKey);
}

function updateConfigurationCode() {
  let code = "";
  try {
    code = NoThreeLineCodec.encodeConfiguration(
      activeCellCoordinates(),
      size,
      symmetry,
    );
  } catch {}
  configurationCode.value = code;
  copyLinkBtn.disabled = !code;
  if (urlSyncEnabled) synchronizeUrl(code);
  codeStatus.textContent = "";
  codeStatus.classList.remove("error");
}

function synchronizeUrl(code) {
  const url = new URL(window.location.href);
  if (code) url.searchParams.set("code", code);
  else url.searchParams.delete("code");
  if (url.href !== window.location.href) {
    window.history.replaceState(null, "", url);
  }
}

function snapshotState() {
  return {
    size,
    symmetry,
    cells: activeCellCoordinates().sort(
      ([rowA, colA], [rowB, colB]) => rowA - rowB || colA - colB,
    ),
  };
}

function statesEqual(first, second) {
  return JSON.stringify(first) === JSON.stringify(second);
}

function updateHistoryButtons() {
  undoBtn.disabled = undoStack.length === 0;
  redoBtn.disabled = redoStack.length === 0;
}

function commitHistory(previousState) {
  if (statesEqual(previousState, snapshotState())) return;
  undoStack.push(previousState);
  if (undoStack.length > HISTORY_LIMIT) undoStack.shift();
  redoStack = [];
  updateHistoryButtons();
}

function restoreState(state) {
  const sizeChanged = size !== state.size;
  size = state.size;
  symmetry = state.symmetry;
  gridSizeSelect.value = String(size);
  targetCount.textContent = String(size * 2);
  symmetrySelect.value = symmetry;
  if (sizeChanged) renderGrid(state.cells);
  else setActiveCells(state.cells);
}

function undo() {
  if (undoStack.length === 0) return;
  redoStack.push(snapshotState());
  restoreState(undoStack.pop());
  updateHistoryButtons();
}

function redo() {
  if (redoStack.length === 0) return;
  undoStack.push(snapshotState());
  restoreState(redoStack.pop());
  updateHistoryButtons();
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
  const previousState = snapshotState();
  activeCells.clear();
  lineIndex.clear();
  symmetrySelect.value = "iden";
  symmetry = "iden";
  updateDisplay();
  commitHistory(previousState);
}

function updateSolutionButton() {
  solutionBtn.disabled = !optimalSolutions?.[size];
}

function showOptimalSolution() {
  const code = optimalSolutions[size];
  if (!code) return;
  const previousState = snapshotState();
  const solution = NoThreeLineCodec.decodeConfiguration(code, size);
  symmetry = solution.symmetryGroup;
  symmetrySelect.value = symmetry;
  setActiveCells(solution.cells);
  commitHistory(previousState);
}

function loadConfigurationCode(recordHistory = true) {
  const previousState = recordHistory ? snapshotState() : null;
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
    renderGrid(solution.cells);
    codeStatus.textContent = `Loaded ${size} × ${size} configuration.`;
    if (recordHistory) commitHistory(previousState);
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
  const previousState = snapshotState();
  if (toggleCell(cell.dataset.row, cell.dataset.col)) {
    updateDisplay();
    commitHistory(previousState);
  }
});

grid.addEventListener("pointerover", (event) => {
  const cell = event.target.closest(".cell");
  if (cell) showLineExplanation(cell);
});

grid.addEventListener("pointerout", (event) => {
  const cell = event.target.closest(".cell");
  if (cell && document.activeElement !== cell) clearLineExplanation();
});

grid.addEventListener("focusin", (event) => {
  const cell = event.target.closest(".cell");
  if (cell) showLineExplanation(cell);
});

grid.addEventListener("focusout", clearLineExplanation);

gridSizeSelect.addEventListener("change", () => {
  const previousState = snapshotState();
  size = Number(gridSizeSelect.value);
  targetCount.textContent = String(size * 2);
  symmetry = "iden";
  symmetrySelect.value = symmetry;
  renderGrid();
  commitHistory(previousState);
});

symmetrySelect.addEventListener("change", () => {
  const previousState = snapshotState();
  symmetry = symmetrySelect.value;
  makeGridSymmetric();
  commitHistory(previousState);
});

disableBlockedCellsInput.addEventListener("change", () => {
  disableBlockedCells = disableBlockedCellsInput.checked;
  updateDisplay();
});

function symmetricCellKeys(row, col) {
  row = Number(row);
  col = Number(col);
  const cellKeys = new Set([key(row, col)]);
  const include = (nextRow, nextCol) => cellKeys.add(key(nextRow, nextCol));

  // (r, c) -> (c, r)
  if (symmetry === "dia1" || symmetry === "dia2" || symmetry === "full") {
    include(col, row);
  }
  // (r, c) -> (c, s-r-1)
  if (symmetry === "rot4" || symmetry === "rct4" || symmetry === "full") {
    include(col, size - row - 1);
  }
  // (r, c) -> (s-r-1, c)
  if (symmetry === "ort1" || symmetry === "ort2" || symmetry === "full") {
    include(size - row - 1, col);
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
    include(size - row - 1, size - col - 1);
  }
  // (r, c) -> (s-c-1, s-r-1)
  if (symmetry === "dia2" || symmetry === "full") {
    include(size - col - 1, size - row - 1);
  }
  // (r, c) -> (c, s-r-1), (r, c) -> (s-c-1, r)
  if (symmetry === "rot4" || symmetry === "rct4" || symmetry === "full") {
    include(col, size - row - 1);
    include(size - col - 1, row);
  }
  // (r, c) -> (r, s-c-1)
  if (symmetry === "ort2" || symmetry === "full") {
    include(row, size - col - 1);
  }

  return cellKeys;
}

function updateCell(row, col, method) {
  for (const cellKey of symmetricCellKeys(row, col)) method(cellKey);
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
    return true;
  } else {
    const orbit = symmetricCellKeys(row, col);
    if (disableBlockedCells) {
      const candidates = Array.from(orbit, parseKey).filter(
        ([candidateRow, candidateCol]) =>
          !activeCells.has(key(candidateRow, candidateCol)),
      );
      if (lineIndex.findViolationLinesAfterAdding(candidates).length > 0) {
        return false;
      }
    }
    for (const orbitKey of orbit) addActiveCell(orbitKey);
    return true;
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

async function copyConfigurationLink() {
  if (copyLinkBtn.disabled) return;
  const link = window.location.href;
  try {
    await navigator.clipboard.writeText(link);
    codeStatus.textContent = "Link copied.";
    codeStatus.classList.remove("error");
  } catch {
    const copyField = document.createElement("textarea");
    copyField.value = link;
    copyField.setAttribute("readonly", "");
    copyField.style.position = "fixed";
    copyField.style.opacity = "0";
    document.body.appendChild(copyField);
    copyField.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch {}
    copyField.remove();
    codeStatus.textContent = copied ? "Link copied." : "Could not copy the link.";
    codeStatus.classList.toggle("error", !copied);
  }
}

clearBtn.addEventListener("click", clearGrid);
solutionBtn.addEventListener("click", showOptimalSolution);
loadCodeBtn.addEventListener("click", () => loadConfigurationCode());
copyLinkBtn.addEventListener("click", copyConfigurationLink);
undoBtn.addEventListener("click", undo);
redoBtn.addEventListener("click", redo);

window.addEventListener("keydown", (event) => {
  if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target?.tagName)) return;
  const pressedKey = event.key.toLowerCase();
  if (pressedKey === "z") {
    event.preventDefault();
    if (event.shiftKey) redo();
    else undo();
  } else if (pressedKey === "y") {
    event.preventDefault();
    redo();
  }
});

window.addEventListener("resize", () => {
  grid.style.setProperty("--cell-size", `${cellSizeForGrid(size)}px`);
});

const queryCode = new URLSearchParams(window.location.search).get("code");
populateSizeSelect();
renderGrid();

if (queryCode !== null) {
  configurationCode.value = queryCode;
  loadConfigurationCode(false);
}
undoStack = [];
redoStack = [];
updateHistoryButtons();
urlSyncEnabled = true;
synchronizeUrl(configurationCode.value);
