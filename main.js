const MIN_SIZE = 3;
const MAX_SIZE = 68;

// const optimalSolutions = {
//     3: {
//         cells: [
//             [0, 0],
//             [0, 1],
//             [1, 0],
//             [1, 2],
//             [2, 1],
//             [2, 2],
//         ],
//         symmetryGroup: "D2",
//     },
// };

const gridSizeSelect = document.getElementById("gridSize");
const grid = document.getElementById("grid");
const activeCountEl = document.getElementById("activeCount");
const lineWarning = document.getElementById("lineWarning");
const clearBtn = document.getElementById("clearBtn");
const solutionBtn = document.getElementById("solutionBtn");
const solutionPanel = document.getElementById("solutionPanel");
const solutionText = document.getElementById("solutionText");
const targetCount = document.getElementById("targetCount");

let size = 3;
let activeCells = new Set();
let cellsByKey = new Map();

function key(row, col) {
  return `${row},${col}`;
}

function parseKey(cellKey) {
  return cellKey.split(",").map(Number);
}

function gcd(a, b) {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b !== 0) {
    const temp = b;
    b = a % b;
    a = temp;
  }
  return a || 1;
}

function canonicalLine(row, col, dRow, dCol) {
  const divisor = gcd(dRow, dCol);
  let stepRow = dRow / divisor;
  let stepCol = dCol / divisor;

  if (stepRow < 0 || (stepRow === 0 && stepCol < 0)) {
    stepRow *= -1;
    stepCol *= -1;
  }

  let startRow = row;
  let startCol = col;
  while (
    startRow - stepRow >= 0 &&
    startRow - stepRow < size &&
    startCol - stepCol >= 0 &&
    startCol - stepCol < size
  ) {
    startRow -= stepRow;
    startCol -= stepCol;
  }

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
      button.dataset.row = row;
      button.dataset.col = col;
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
  hideSolutionPanel();
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

  activeCountEl.textContent = activeCells.size;
  lineWarning.classList.toggle("visible", badCells.size > 0);
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
  hideSolutionPanel();
  updateDisplay();
}

function updateSolutionButton() {
  solutionBtn.disabled = !optimalSolutions[size];
}

function hideSolutionPanel() {
  solutionPanel.classList.remove("visible");
  solutionText.textContent = "";
}

function showOptimalSolution() {
  const solution = optimalSolutions[size];
  if (!solution) return;

  setActiveCells(solution.cells || []);
  solutionText.textContent = `Grid ${size} × ${size}. Symmetry group: ${solution.symmetryGroup || "not specified"}.`;
  solutionPanel.classList.add("visible");
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

  const cellKey = key(Number(cell.dataset.row), Number(cell.dataset.col));
  if (activeCells.has(cellKey)) {
    activeCells.delete(cellKey);
  } else {
    activeCells.add(cellKey);
  }
  hideSolutionPanel();
  updateDisplay();
});

gridSizeSelect.addEventListener("change", () => {
  size = Number(gridSizeSelect.value);
  targetCount.textContent = String(size * 2);
  renderGrid();
});

clearBtn.addEventListener("click", clearGrid);
solutionBtn.addEventListener("click", showOptimalSolution);

window.addEventListener("resize", () => {
  grid.style.setProperty("--cell-size", `${cellSizeForGrid(size)}px`);
});

populateSizeSelect();
renderGrid();
