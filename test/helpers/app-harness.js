const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const projectRoot = path.join(__dirname, "..", "..");
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
    "lineExplanation", "solutionPanel", "solutionText", "discovery",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  elements.symmetry.value = "iden";
  elements.disableBlockedCells.checked = true;
  elements.showLineViolations.checked = true;
  const clipboardWrites = [];
  const body = new FakeElement("body");
  let createdButtons = 0;
  let activeElement = null;

  const document = {
    body,
    get activeElement() { return activeElement; },
    set activeElement(element) { activeElement = element; },
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
  elements.__document = document;
  elements.__clipboardWrites = clipboardWrites;
  elements.__createdButtons = () => createdButtons;
  elements.__cellAt = (row, col) =>
    elements.grid.children.find(
      (cell) =>
        cell.dataset.row === String(row) && cell.dataset.col === String(col),
    );
  elements.__activeKeys = () =>
    elements.grid.children
      .filter((cell) => cell.classList.contains("active"))
      .map((cell) => `${cell.dataset.row},${cell.dataset.col}`)
      .sort();
  return elements;
}

module.exports = { FakeClassList, FakeElement, projectRoot, startApp };
