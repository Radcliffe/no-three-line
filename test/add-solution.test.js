const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

test("discovery updater validates input, updates related files, and rolls back failures", () => {
  const result = spawnSync("python3", ["-B", "test/test_add_solution.py"], {
    cwd: path.join(__dirname, ".."),
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.error?.message || result.stderr || result.stdout);
});
