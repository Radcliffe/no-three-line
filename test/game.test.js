const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const { projectRoot, startApp } = require("./helpers/app-harness");

const MIN_SIZE = 3;
const MAX_SIZE = 90;

const THREE_BY_THREE_OPTIMAL = [
  [0, 0], [0, 1], [1, 0], [1, 2], [2, 1], [2, 2],
];

function clickCells(elements, cells) {
  for (const [row, col] of cells) {
    elements.grid.dispatch("click", { target: elements.__cellAt(row, col) });
  }
}

test("a fresh grid starts empty with the target count for its size", () => {
  const elements = startApp("");
  assert.equal(elements.gridSize.value, "3");
  assert.equal(elements.grid.children.length, 9);
  assert.equal(elements.activeCount.textContent, "0");
  assert.equal(elements.configurationCode.value, "");
  assert.equal(elements.copyLinkBtn.disabled, true);
  assert.equal(elements.undoBtn.disabled, true);
  assert.equal(elements.redoBtn.disabled, true);
  assert.equal(
    elements.__cellAt(0, 0).attributes.get("aria-label"),
    "Row 1, column 1, inactive",
  );
});

test("clicking a cell activates it and updates its accessible label", () => {
  const elements = startApp("");
  const cell = elements.__cellAt(1, 2);

  elements.grid.dispatch("click", { target: cell });
  assert.equal(cell.classList.contains("active"), true);
  assert.equal(elements.activeCount.textContent, "1");
  assert.equal(cell.attributes.get("aria-label"), "Row 2, column 3, active");

  elements.grid.dispatch("click", { target: cell });
  assert.equal(cell.classList.contains("active"), false);
  assert.equal(elements.activeCount.textContent, "0");
  assert.equal(cell.attributes.get("aria-label"), "Row 2, column 3, inactive");
});

test("changing the grid size rebuilds the board and resets symmetry", () => {
  const elements = startApp("");
  elements.symmetry.value = "rot2";
  elements.symmetry.dispatch("change");
  clickCells(elements, [[0, 0]]);
  assert.equal(elements.activeCount.textContent, "2");

  elements.gridSize.value = "7";
  elements.gridSize.dispatch("change");

  assert.equal(elements.grid.children.length, 49);
  assert.equal(elements.activeCount.textContent, "0");
  assert.equal(elements.targetCount.textContent, "14");
  assert.equal(elements.symmetry.value, "iden");
  assert.equal(elements.grid.style["--size"], 7);
});

test("clearing the board empties it, restores identity symmetry, and is undoable", () => {
  const elements = startApp("");
  elements.symmetry.value = "rot2";
  elements.symmetry.dispatch("change");
  clickCells(elements, [[0, 0]]);
  assert.equal(elements.activeCount.textContent, "2");

  elements.clearBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "0");
  assert.equal(elements.symmetry.value, "iden");
  assert.equal(elements.__cellAt(0, 0).classList.contains("active"), false);

  elements.undoBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "2");
  assert.equal(elements.symmetry.value, "rot2");
});

test("clearing an already empty board records no history", () => {
  const elements = startApp("");
  elements.clearBtn.dispatch("click");
  assert.equal(elements.undoBtn.disabled, true);
});

test("a symmetry group places and removes the whole orbit of a cell", () => {
  const elements = startApp("");
  elements.gridSize.value = "5";
  elements.gridSize.dispatch("change");
  elements.symmetry.value = "rot4";
  elements.symmetry.dispatch("change");

  clickCells(elements, [[0, 1]]);
  assert.deepEqual(elements.__activeKeys(), ["0,1", "1,4", "3,0", "4,3"]);
  assert.equal(elements.activeCount.textContent, "4");

  elements.grid.dispatch("click", { target: elements.__cellAt(3, 0) });
  assert.deepEqual(elements.__activeKeys(), []);
  assert.equal(elements.activeCount.textContent, "0");
});

test("selecting a symmetry group completes the cells already on the board", () => {
  const elements = startApp("");
  elements.gridSize.value = "5";
  elements.gridSize.dispatch("change");
  clickCells(elements, [[0, 0]]);
  assert.equal(elements.activeCount.textContent, "1");

  elements.symmetry.value = "rot2";
  elements.symmetry.dispatch("change");

  assert.deepEqual(elements.__activeKeys(), ["0,0", "4,4"]);
  assert.equal(elements.activeCount.textContent, "2");
});

test("a blocked move is rejected and leaves the history untouched", () => {
  const elements = startApp("");
  clickCells(elements, [[0, 0], [1, 1]]);
  const blocked = elements.__cellAt(2, 2);
  assert.equal(blocked.disabled, true);
  assert.equal(blocked.classList.contains("blocked"), true);

  elements.undoBtn.dispatch("click");
  elements.undoBtn.dispatch("click");
  assert.equal(elements.undoBtn.disabled, true);
  elements.redoBtn.dispatch("click");
  elements.redoBtn.dispatch("click");
  assert.equal(elements.redoBtn.disabled, true);

  elements.grid.dispatch("click", { target: blocked });
  assert.equal(elements.activeCount.textContent, "2");
  assert.equal(blocked.classList.contains("active"), false);
  assert.equal(elements.undoBtn.disabled, false);
  assert.equal(elements.redoBtn.disabled, true);
});

test("turning off move prevention allows three in a line and flags it", () => {
  const elements = startApp("");
  elements.disableBlockedCells.checked = false;
  elements.disableBlockedCells.dispatch("change");

  clickCells(elements, [[0, 0], [1, 1], [2, 2]]);

  assert.equal(elements.activeCount.textContent, "3");
  assert.equal(elements.lineWarning.classList.contains("visible"), true);
  assert.equal(elements.__cellAt(1, 1).classList.contains("line-hit"), true);
  assert.match(
    elements.__cellAt(1, 1).attributes.get("aria-label"),
    /on a line with three or more active cells/,
  );
  assert.equal(elements.grid.classList.contains("optimal"), false);

  elements.disableBlockedCells.checked = true;
  elements.disableBlockedCells.dispatch("change");
  assert.equal(elements.lineWarning.classList.contains("visible"), true);
  assert.equal(elements.__cellAt(0, 1).disabled, false);
});

test("a full board with six points but a line is not treated as optimal", () => {
  const elements = startApp("");
  elements.disableBlockedCells.checked = false;
  elements.disableBlockedCells.dispatch("change");

  clickCells(elements, [[0, 0], [0, 1], [1, 0], [1, 1], [2, 0], [2, 1]]);

  assert.equal(elements.activeCount.textContent, "6");
  assert.equal(elements.grid.classList.contains("optimal"), false);
});

test("the discovery notice appears only for an unsolved size with a full code", () => {
  const elements = startApp("");
  assert.equal(elements.discovery.style.display, "none");

  clickCells(elements, THREE_BY_THREE_OPTIMAL);
  assert.equal(elements.configurationCode.value, ".010212");
  assert.equal(elements.discovery.style.display, "block");

  elements.grid.dispatch("click", { target: elements.__cellAt(0, 0) });
  assert.equal(elements.configurationCode.value, "");
  assert.equal(elements.discovery.style.display, "none");
});

test("the discovery notice stays hidden while the board has three in a line", () => {
  const elements = startApp("");
  elements.disableBlockedCells.checked = false;
  elements.disableBlockedCells.dispatch("change");

  clickCells(elements, [[0, 0], [0, 1], [1, 0], [1, 1], [2, 0], [2, 1]]);

  assert.equal(elements.configurationCode.value, ".010101");
  assert.equal(elements.lineWarning.classList.contains("visible"), true);
  assert.equal(elements.discovery.style.display, "none");

  clickCells(elements, [[1, 1], [2, 0], [1, 2], [2, 2]]);
  assert.deepEqual(elements.__activeKeys(), [
    "0,0", "0,1", "1,0", "1,2", "2,1", "2,2",
  ]);
  assert.equal(elements.lineWarning.classList.contains("visible"), false);
  assert.equal(elements.discovery.style.display, "block");
});

test("the discovery notice stays hidden when the size has a bundled solution", () => {
  const elements = startApp("", { solutions: { 3: ".010212" } });
  clickCells(elements, THREE_BY_THREE_OPTIMAL);
  assert.equal(elements.configurationCode.value, ".010212");
  assert.equal(elements.discovery.style.display, "none");
});

// A genuinely new solution cannot be constructed in a test: the sizes below are
// exactly the ones for which no 2n-point configuration is known. This pins down
// which sizes can reach the discovery notice in production, where the tests
// above inject a bundle to exercise both branches on a small grid. Update this
// list whenever a solution is added to optimal-solutions.txt.
test("the discovery notice is reachable only for sizes the bundle omits", () => {
  const context = vm.createContext({});
  vm.runInContext(
    `${fs.readFileSync(path.join(projectRoot, "optimal-solutions.generated.js"), "utf8")}
     this.solutions = optimalSolutions;`,
    context,
  );

  const unsolved = [];
  for (let size = MIN_SIZE; size <= MAX_SIZE; size++) {
    if (!context.solutions[size]) unsolved.push(size);
  }

  assert.deepEqual(unsolved, [
    75, 77, 78, 79, 80, 81, 82,      // UPDATE
    83, 84, 85, 86, 87, 88, 89, 90,
  ]);
});

test("the code field and share link track the board", () => {
  const elements = startApp("");
  clickCells(elements, THREE_BY_THREE_OPTIMAL);

  assert.equal(elements.copyLinkBtn.disabled, false);
  assert.equal(
    new URL(elements.__window.location.href).searchParams.get("code"),
    ".010212",
  );

  elements.clearBtn.dispatch("click");
  assert.equal(elements.copyLinkBtn.disabled, true);
  assert.equal(
    new URL(elements.__window.location.href).searchParams.get("code"),
    null,
  );
});

test("loading a code from the field reports success and replaces the board", () => {
  const elements = startApp("");
  elements.configurationCode.value = "o2423670617014535";
  elements.loadCodeBtn.dispatch("click");

  assert.equal(elements.gridSize.value, "8");
  assert.equal(elements.grid.children.length, 64);
  assert.equal(elements.targetCount.textContent, "16");
  assert.equal(elements.symmetry.value, "rot4");
  assert.equal(elements.activeCount.textContent, "16");
  assert.equal(elements.codeStatus.textContent, "Loaded 8 × 8 configuration.");
  assert.equal(elements.codeStatus.classList.contains("error"), false);

  elements.undoBtn.dispatch("click");
  assert.equal(elements.gridSize.value, "3");
  assert.equal(elements.grid.children.length, 9);
  assert.equal(elements.activeCount.textContent, "0");
});

test("loading a malformed code reports the error and keeps the board", () => {
  const elements = startApp("");
  clickCells(elements, [[0, 0]]);
  elements.configurationCode.value = "x01021";
  elements.loadCodeBtn.dispatch("click");

  assert.equal(elements.activeCount.textContent, "1");
  assert.equal(elements.gridSize.value, "3");
  assert.equal(elements.codeStatus.classList.contains("error"), true);
  assert.match(elements.codeStatus.textContent, /does not describe a supported square grid/);
  assert.equal(elements.undoBtn.disabled, false);
});

test("a code for a grid smaller than the minimum is rejected", () => {
  const elements = startApp("");
  elements.configurationCode.value = "x0101";
  elements.loadCodeBtn.dispatch("click");

  assert.equal(elements.gridSize.value, "3");
  assert.equal(
    elements.codeStatus.textContent,
    "The app supports grid sizes from 3 to 90.",
  );
  assert.equal(elements.codeStatus.classList.contains("error"), true);
});

test("the solution button is disabled without a bundled solution for the size", () => {
  const elements = startApp("", { solutions: { 3: ".010212" } });
  assert.equal(elements.solutionBtn.disabled, false);

  elements.gridSize.value = "5";
  elements.gridSize.dispatch("change");
  assert.equal(elements.solutionBtn.disabled, true);

  elements.solutionBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "0");
});

test("showing a bundled solution applies its symmetry and can be undone", () => {
  const elements = startApp("", { solutions: { 8: "o2423670617014535" } });
  elements.gridSize.value = "8";
  elements.gridSize.dispatch("change");
  clickCells(elements, [[0, 0]]);

  elements.solutionBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "16");
  assert.equal(elements.symmetry.value, "rot4");
  assert.equal(elements.grid.classList.contains("optimal"), true);

  elements.undoBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "1");
  assert.equal(elements.symmetry.value, "iden");
});

test("keyboard focus shows and clears the line explanation", () => {
  const elements = startApp("");
  clickCells(elements, [[0, 0], [2, 2]]);
  const blockedCenter = elements.__cellAt(1, 1);

  elements.grid.dispatch("focusin", { target: blockedCenter });
  assert.equal(elements.lineExplanation.classList.contains("visible"), true);
  assert.match(elements.lineExplanation.textContent, /would create three in a line/);

  elements.grid.dispatch("focusout", { target: blockedCenter });
  assert.equal(elements.lineExplanation.classList.contains("visible"), false);
});

test("pointer-out keeps the explanation while the cell still has focus", () => {
  const elements = startApp("");
  clickCells(elements, [[0, 0], [2, 2]]);
  const blockedCenter = elements.__cellAt(1, 1);
  elements.__document.activeElement = blockedCenter;

  elements.grid.dispatch("pointerover", { target: blockedCenter });
  elements.grid.dispatch("pointerout", { target: blockedCenter });
  assert.equal(elements.lineExplanation.classList.contains("visible"), true);
});

test("hovering an empty cell with nothing to explain shows only the help text", () => {
  const elements = startApp("");
  elements.grid.dispatch("pointerover", { target: elements.__cellAt(1, 1) });
  assert.equal(elements.lineExplanation.classList.contains("visible"), false);
  assert.match(elements.lineExplanation.textContent, /Hover over a gray or red cell/);

  elements.showLineViolations.checked = false;
  elements.showLineViolations.dispatch("change");
  assert.match(elements.lineExplanation.textContent, /Hover over a gray cell/);
});

test("ctrl+y redoes and shortcuts are ignored inside form controls", () => {
  const elements = startApp("");
  clickCells(elements, [[0, 0]]);
  const press = (key, extra = {}) =>
    elements.__window.dispatch("keydown", {
      ctrlKey: true,
      metaKey: false,
      altKey: false,
      shiftKey: false,
      key,
      target: { tagName: "BODY" },
      preventDefault() {},
      ...extra,
    });

  press("z");
  assert.equal(elements.activeCount.textContent, "0");
  press("y");
  assert.equal(elements.activeCount.textContent, "1");

  press("z", { target: { tagName: "INPUT" } });
  assert.equal(elements.activeCount.textContent, "1");
  press("z", { ctrlKey: false, metaKey: false });
  assert.equal(elements.activeCount.textContent, "1");
  press("z", { altKey: true });
  assert.equal(elements.activeCount.textContent, "1");
});

test("undo history is capped at one hundred steps", () => {
  const elements = startApp("");
  const cell = elements.__cellAt(0, 0);
  for (let i = 0; i < 105; i++) {
    elements.grid.dispatch("click", { target: cell });
  }

  let undone = 0;
  while (!elements.undoBtn.disabled) {
    elements.undoBtn.dispatch("click");
    undone++;
    assert.ok(undone <= 200, "undo did not terminate");
  }
  assert.equal(undone, 100);
});

test("cell sizing shrinks with the grid and follows window resizes", () => {
  const elements = startApp("");
  assert.equal(elements.grid.style["--cell-size"], "42px");
  assert.equal(elements.grid.style["--gap-size"], "3px");

  elements.gridSize.value = "40";
  elements.gridSize.dispatch("change");
  assert.equal(elements.grid.style["--cell-size"], "24px");
  assert.equal(elements.grid.style["--gap-size"], "2px");
  assert.equal(elements.grid.style["--cell-radius"], "4px");

  elements.__window.innerWidth = 400;
  elements.__window.dispatch("resize");
  assert.equal(elements.grid.style["--cell-size"], "7px");
});

test("every size from 3 to 90 is offered in the size selector", () => {
  const elements = startApp("");
  assert.equal(elements.gridSize.children.length, 88);
  assert.equal(elements.gridSize.children[0].value, "3");
  assert.equal(elements.gridSize.children[0].textContent, "3 × 3");
  assert.equal(elements.gridSize.children.at(-1).value, "90");
});
