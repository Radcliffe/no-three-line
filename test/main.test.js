const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const projectRoot = path.join(__dirname, "..");
const codecSource = fs.readFileSync(
  path.join(projectRoot, "configuration-codec.js"),
  "utf8",
);
const mainSource = fs.readFileSync(path.join(projectRoot, "main.js"), "utf8");

class FakeClassList {
  constructor(element) {
    this.element = element;
  }

  add(...names) {
    for (const name of names) this.element.classes.add(name);
  }

  remove(...names) {
    for (const name of names) this.element.classes.delete(name);
  }

  toggle(name, force) {
    const enabled = force === undefined ? !this.contains(name) : Boolean(force);
    if (enabled) this.add(name);
    else this.remove(name);
    return enabled;
  }

  contains(name) {
    return this.element.classes.has(name);
  }
}

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.listeners = new Map();
    this.classes = new Set();
    this.classList = new FakeClassList(this);
    this.style = { setProperty: (name, value) => this.style[name] = value };
    this.value = "";
    this.textContent = "";
    this.checked = false;
    this.disabled = false;
    this.selected = false;
    this.setAttributeCount = 0;
  }

  set className(value) {
    this.classes = new Set(String(value).split(/\s+/).filter(Boolean));
  }

  get className() {
    return [...this.classes].join(" ");
  }

  set innerHTML(value) {
    if (value === "") this.children = [];
  }

  appendChild(child) {
    if (child.tagName === "#FRAGMENT") this.children.push(...child.children);
    else this.children.push(child);
    if (child.selected) this.value = child.value;
    return child;
  }

  setAttribute(name, value) {
    this.setAttributeCount++;
    this.attributes.set(name, String(value));
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  dispatch(type, event = {}) {
    return this.listeners.get(type)?.({ target: this, ...event });
  }

  closest(selector) {
    return selector === ".cell" && this.classList.contains("cell") ? this : null;
  }

  select() {
    this.selectedText = true;
  }

  remove() {}
}

function startApp(
  search,
  { clipboardFails = false, solutions = {}, attributions = {} } = {},
) {
  const ids = [
    "gridSize", "grid", "activeCount", "lineWarning", "clearBtn",
    "solutionBtn", "targetCount", "symmetry", "configurationCode",
    "loadCodeBtn", "codeStatus", "disableBlockedCells", "showLineViolations",
    "undoBtn", "redoBtn", "copyLinkBtn",
    "lineExplanation", "solutionPanel", "solutionText",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  elements.symmetry.value = "iden";
  elements.disableBlockedCells.checked = true;
  elements.showLineViolations.checked = true;
  const clipboardWrites = [];
  const body = new FakeElement("body");
  let createdButtons = 0;

  const document = {
    body,
    getElementById: (id) => elements[id],
    createElement: (tagName) => {
      if (tagName === "button") createdButtons++;
      return new FakeElement(tagName);
    },
    createDocumentFragment: () => new FakeElement("#fragment"),
    execCommand(command) {
      if (command !== "copy") return false;
      const selected = body.children.find((element) => element.selectedText);
      if (!selected) return false;
      clipboardWrites.push(selected.value);
      return true;
    },
  };
  let currentUrl = new URL(search || "", "https://example.test/app");
  const windowListeners = new Map();
  const window = {
    innerWidth: 1200,
    location: {
      get href() { return currentUrl.href; },
      get search() { return currentUrl.search; },
    },
    history: {
      replaceState(_state, _title, nextUrl) {
        currentUrl = new URL(String(nextUrl), currentUrl);
      },
    },
    addEventListener(type, listener) { windowListeners.set(type, listener); },
    dispatch(type, event = {}) { return windowListeners.get(type)?.(event); },
  };
  const navigator = {
    clipboard: {
      async writeText(value) {
        if (clipboardFails) throw new Error("Clipboard unavailable");
        clipboardWrites.push(value);
      },
    },
  };
  const context = vm.createContext({
    URL,
    URLSearchParams,
    console,
    document,
    globalThis: undefined,
    navigator,
    optimalSolutionAttributions: attributions,
    optimalSolutions: solutions,
    window,
  });
  context.globalThis = context;
  vm.runInContext(codecSource, context);
  vm.runInContext(mainSource, context);
  elements.__window = window;
  elements.__clipboardWrites = clipboardWrites;
  elements.__createdButtons = () => createdButtons;
  return elements;
}

test("code query parameter loads its grid, symmetry, and cells", () => {
  const elements = startApp("?code=o3545011706672324");
  assert.equal(elements.gridSize.value, "8");
  assert.equal(elements.symmetry.value, "rot4");
  assert.equal(elements.activeCount.textContent, "16");
  assert.equal(elements.configurationCode.value, "o3545011706672324");
  assert.equal(elements.codeStatus.textContent, "Loaded 8 × 8 configuration.");
  assert.equal(elements.codeStatus.classList.contains("error"), false);
  assert.equal(elements.undoBtn.disabled, true);
  assert.equal(elements.redoBtn.disabled, true);
  assert.equal(elements.copyLinkBtn.disabled, false);
  assert.equal(elements.__createdButtons(), 64);
  assert.equal(
    elements.grid.children.filter((cell) => cell.classList.contains("active")).length,
    16,
  );
});

test("loading a same-size configuration reuses the existing grid", () => {
  const elements = startApp("?code=o3545011706672324");
  const firstCell = elements.grid.children[0];
  elements.configurationCode.value = "o2423670617014535";
  elements.loadCodeBtn.dispatch("click");
  assert.equal(elements.grid.children[0], firstCell);
  assert.equal(elements.activeCount.textContent, "16");
  assert.equal(elements.configurationCode.value, "o2423670617014535");
});

test("a large-grid edit only patches cells whose display state changed", () => {
  const elements = startApp("");
  elements.gridSize.value = "90";
  elements.gridSize.dispatch("change");
  assert.equal(elements.grid.children.length, 8100);
  for (const cell of elements.grid.children) cell.setAttributeCount = 0;

  elements.grid.dispatch("click", { target: elements.grid.children[0] });
  const updatedCells = elements.grid.children.filter(
    (cell) => cell.setAttributeCount > 0,
  );
  assert.equal(updatedCells.length, 1);
  assert.equal(updatedCells[0], elements.grid.children[0]);
});

test("URL-encoded symmetry punctuation is decoded before loading", () => {
  const elements = startApp("?code=%2B010212");
  assert.equal(elements.gridSize.value, "3");
  assert.equal(elements.symmetry.value, "ort2");
  assert.equal(elements.configurationCode.value, "+010212");
});

test("orbit-aware marking scales to the largest bundled configuration", () => {
  const source = fs.readFileSync(
    path.join(projectRoot, "optimal-solutions.generated.js"),
    "utf8",
  );
  const context = vm.createContext({});
  vm.runInContext(`${source}\nthis.solutions = optimalSolutions;`, context);
  const code = context.solutions[74];
  const elements = startApp(`?code=${encodeURIComponent(code)}`);
  assert.equal(elements.gridSize.value, "74");
  assert.equal(elements.activeCount.textContent, "148");
  assert.equal(elements.configurationCode.value, code);
});

test("an invalid code query reports an error without changing the default grid", () => {
  const elements = startApp("?code=bad");
  assert.equal(elements.gridSize.value, "3");
  assert.equal(elements.grid.children.length, 9);
  assert.equal(elements.activeCount.textContent, "0");
  assert.match(elements.codeStatus.textContent, /unknown symmetry character/);
  assert.equal(elements.codeStatus.classList.contains("error"), true);
});

test("move prevention cannot be bypassed by symmetry-generated cells", () => {
  const elements = startApp("");
  elements.symmetry.value = "rot2";
  elements.symmetry.dispatch("change");

  const center = elements.grid.children.find(
    (cell) => cell.dataset.row === "1" && cell.dataset.col === "1",
  );
  const corner = elements.grid.children.find(
    (cell) => cell.dataset.row === "0" && cell.dataset.col === "0",
  );
  elements.grid.dispatch("click", { target: center });
  assert.equal(corner.disabled, true);
  assert.equal(corner.classList.contains("blocked"), true);
  elements.grid.dispatch("click", { target: corner });

  assert.equal(elements.activeCount.textContent, "1");
  assert.equal(elements.lineWarning.classList.contains("visible"), false);
  assert.equal(corner.classList.contains("active"), false);
});

test("changing symmetry refreshes orbit-aware illegal cells", () => {
  const elements = startApp("");
  const center = elements.grid.children.find(
    (cell) => cell.dataset.row === "1" && cell.dataset.col === "1",
  );
  const corner = elements.grid.children.find(
    (cell) => cell.dataset.row === "0" && cell.dataset.col === "0",
  );
  elements.grid.dispatch("click", { target: center });
  assert.equal(corner.disabled, false);

  elements.symmetry.value = "rot2";
  elements.symmetry.dispatch("change");
  assert.equal(corner.disabled, true);
  assert.match(corner.attributes.get("aria-label"), /symmetry orbit/);
  elements.grid.dispatch("pointerover", { target: corner });
  const oppositeCorner = elements.grid.children.find(
    (cell) => cell.dataset.row === "2" && cell.dataset.col === "2",
  );
  assert.equal(oppositeCorner.classList.contains("orbit-explained"), true);
  assert.match(elements.lineExplanation.textContent, /outlined symmetry orbit/);
});

test("line violation highlights can be hidden and are enabled by default", () => {
  const elements = startApp("");
  const cellAt = (row, col) => elements.grid.children.find(
    (cell) => cell.dataset.row === String(row) && cell.dataset.col === String(col),
  );
  elements.disableBlockedCells.checked = false;
  elements.disableBlockedCells.dispatch("change");
  elements.grid.dispatch("click", { target: cellAt(0, 0) });
  elements.grid.dispatch("click", { target: cellAt(0, 1) });
  elements.grid.dispatch("click", { target: cellAt(0, 2) });

  assert.equal(elements.showLineViolations.checked, true);
  assert.equal(cellAt(0, 0).classList.contains("line-hit"), true);
  assert.equal(elements.lineWarning.classList.contains("visible"), true);

  elements.showLineViolations.checked = false;
  elements.showLineViolations.dispatch("change");
  assert.equal(cellAt(0, 0).classList.contains("line-hit"), false);
  assert.equal(elements.lineWarning.classList.contains("visible"), false);
  elements.grid.dispatch("pointerover", { target: cellAt(0, 0) });
  assert.equal(elements.lineExplanation.classList.contains("visible"), false);

  elements.showLineViolations.checked = true;
  elements.showLineViolations.dispatch("change");
  assert.equal(cellAt(0, 0).classList.contains("line-hit"), true);
  assert.equal(elements.lineWarning.classList.contains("visible"), true);
});

test("optimal solution information includes known discoverer and date", () => {
  const code = "o2423670617014535";
  const elements = startApp(`?code=${code}`, {
    solutions: { 8: code },
    attributions: {
      8: { discoverer: "H. E. Dudeney", date: "November 7, 1906" },
    },
  });
  assert.equal(elements.solutionBtn.disabled, false);
  assert.equal(elements.solutionPanel.classList.contains("visible"), true);
  assert.match(elements.solutionText.textContent, /8 × 8: 16 points/);
  assert.match(elements.solutionText.textContent, /90° rotational symmetry/);
  assert.match(elements.solutionText.textContent, /Discoverer: H\. E\. Dudeney/);
  assert.match(elements.solutionText.textContent, /Date: November 7, 1906/);
  assert.doesNotMatch(elements.solutionText.textContent, /maximum possible/);

  elements.gridSize.value = "71";
  elements.gridSize.dispatch("change");
  assert.equal(elements.solutionBtn.disabled, true);
  assert.match(elements.solutionText.textContent, /No bundled 142-point optimal solution/);
});

test("optimal solution information omits an unavailable discoverer", () => {
  const code = "x010212";
  const elements = startApp(`?code=${code}`, {
    solutions: { 3: code },
    attributions: { 3: { date: "By 1975" } },
  });
  assert.doesNotMatch(elements.solutionText.textContent, /Discoverer:/);
  assert.match(elements.solutionText.textContent, /Date: By 1975/);
});

test("every bundled solution has a dated attribution summary", () => {
  const context = vm.createContext({});
  const solutionSource = fs.readFileSync(
    path.join(projectRoot, "optimal-solutions.generated.js"),
    "utf8",
  );
  const attributionSource = fs.readFileSync(
    path.join(projectRoot, "optimal-solution-attributions.js"),
    "utf8",
  );
  vm.runInContext(
    `${solutionSource}\n${attributionSource}\n` +
      `this.solutions = optimalSolutions; this.attributions = optimalSolutionAttributions;`,
    context,
  );
  for (const size of Object.keys(context.solutions)) {
    assert.equal(typeof context.attributions[size]?.date, "string", `size ${size}`);
  }
});

test("hovering a blocked cell highlights and explains its responsible line", () => {
  const elements = startApp("");
  const cellAt = (row, col) => elements.grid.children.find(
    (cell) => cell.dataset.row === String(row) && cell.dataset.col === String(col),
  );
  elements.grid.dispatch("click", { target: cellAt(0, 0) });
  elements.grid.dispatch("click", { target: cellAt(2, 2) });
  const blockedCenter = cellAt(1, 1);
  elements.grid.dispatch("pointerover", { target: blockedCenter });

  assert.match(elements.lineExplanation.textContent, /highlighted line/);
  assert.equal(blockedCenter.classList.contains("line-explained"), true);
  assert.equal(cellAt(0, 0).classList.contains("line-source"), true);
  assert.equal(cellAt(2, 2).classList.contains("line-source"), true);

  elements.grid.dispatch("pointerout", { target: blockedCenter });
  assert.match(elements.lineExplanation.textContent, /Hover over a gray or red cell/);
  assert.equal(blockedCenter.classList.contains("line-explained"), false);
});

test("board changes synchronize the URL and can be undone and redone", () => {
  const code = "o3545011706672324";
  const elements = startApp(`?theme=light&code=${code}`);
  const activeCell = elements.grid.children.find((cell) =>
    cell.classList.contains("active"),
  );

  elements.grid.dispatch("click", { target: activeCell });
  assert.equal(new URL(elements.__window.location.href).searchParams.get("code"), null);
  assert.equal(
    new URL(elements.__window.location.href).searchParams.get("theme"),
    "light",
  );
  assert.equal(elements.undoBtn.disabled, false);
  assert.equal(elements.redoBtn.disabled, true);

  elements.undoBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "16");
  assert.equal(
    new URL(elements.__window.location.href).searchParams.get("code"),
    code,
  );
  assert.equal(elements.redoBtn.disabled, false);

  elements.redoBtn.dispatch("click");
  assert.equal(elements.activeCount.textContent, "12");
  assert.equal(new URL(elements.__window.location.href).searchParams.get("code"), null);
});

test("copy link writes the synchronized URL to the clipboard", async () => {
  const elements = startApp("?code=o3545011706672324");
  await elements.copyLinkBtn.dispatch("click");
  assert.deepEqual(elements.__clipboardWrites, [elements.__window.location.href]);
  assert.equal(elements.codeStatus.textContent, "Link copied.");
});

test("copy link falls back when the modern clipboard API is unavailable", async () => {
  const elements = startApp(
    "?code=o3545011706672324",
    { clipboardFails: true },
  );
  await elements.copyLinkBtn.dispatch("click");
  assert.deepEqual(elements.__clipboardWrites, [elements.__window.location.href]);
  assert.equal(elements.codeStatus.textContent, "Link copied.");
  assert.equal(elements.codeStatus.classList.contains("error"), false);
});

test("keyboard shortcuts undo and redo outside form controls", () => {
  const elements = startApp("");
  const cell = elements.grid.children[0];
  elements.grid.dispatch("click", { target: cell });
  let prevented = 0;

  elements.__window.dispatch("keydown", {
    ctrlKey: true,
    metaKey: false,
    altKey: false,
    shiftKey: false,
    key: "z",
    target: { tagName: "BODY" },
    preventDefault() { prevented++; },
  });
  assert.equal(elements.activeCount.textContent, "0");

  elements.__window.dispatch("keydown", {
    ctrlKey: true,
    metaKey: false,
    altKey: false,
    shiftKey: true,
    key: "z",
    target: { tagName: "BODY" },
    preventDefault() { prevented++; },
  });
  assert.equal(elements.activeCount.textContent, "1");
  assert.equal(prevented, 2);
});
