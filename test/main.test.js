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
    this.attributes.set(name, String(value));
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  dispatch(type, event = {}) {
    this.listeners.get(type)?.({ target: this, ...event });
  }

  closest(selector) {
    return selector === ".cell" && this.classList.contains("cell") ? this : null;
  }
}

function startApp(search) {
  const ids = [
    "gridSize", "grid", "activeCount", "lineWarning", "clearBtn",
    "solutionBtn", "targetCount", "symmetry", "configurationCode",
    "loadCodeBtn", "codeStatus", "disableBlockedCells",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  elements.symmetry.value = "iden";
  elements.disableBlockedCells.checked = true;

  const document = {
    getElementById: (id) => elements[id],
    createElement: (tagName) => new FakeElement(tagName),
    createDocumentFragment: () => new FakeElement("#fragment"),
  };
  const window = {
    innerWidth: 1200,
    location: { search },
    addEventListener() {},
  };
  const context = vm.createContext({
    URLSearchParams,
    console,
    document,
    globalThis: undefined,
    optimalSolutions: {},
    window,
  });
  context.globalThis = context;
  vm.runInContext(codecSource, context);
  vm.runInContext(mainSource, context);
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
  assert.equal(
    elements.grid.children.filter((cell) => cell.classList.contains("active")).length,
    16,
  );
});

test("URL-encoded symmetry punctuation is decoded before loading", () => {
  const elements = startApp("?code=%2B010212");
  assert.equal(elements.gridSize.value, "3");
  assert.equal(elements.symmetry.value, "ort2");
  assert.equal(elements.configurationCode.value, "+010212");
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
  elements.grid.dispatch("click", { target: corner });

  assert.equal(elements.activeCount.textContent, "1");
  assert.equal(elements.lineWarning.classList.contains("visible"), false);
  assert.equal(corner.classList.contains("active"), false);
});
