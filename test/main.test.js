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

function startApp(search, { clipboardFails = false } = {}) {
  const ids = [
    "gridSize", "grid", "activeCount", "lineWarning", "clearBtn",
    "solutionBtn", "targetCount", "symmetry", "configurationCode",
    "loadCodeBtn", "codeStatus", "disableBlockedCells",
    "undoBtn", "redoBtn", "copyLinkBtn",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  elements.symmetry.value = "iden";
  elements.disableBlockedCells.checked = true;
  const clipboardWrites = [];
  const body = new FakeElement("body");

  const document = {
    body,
    getElementById: (id) => elements[id],
    createElement: (tagName) => new FakeElement(tagName),
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
    optimalSolutions: {},
    window,
  });
  context.globalThis = context;
  vm.runInContext(codecSource, context);
  vm.runInContext(mainSource, context);
  elements.__window = window;
  elements.__clipboardWrites = clipboardWrites;
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
