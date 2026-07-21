const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const test = require("node:test");

const projectRoot = path.join(__dirname, "..");

test("converter reproduces the checked-in solution bundle", () => {
  const temporaryDirectory = fs.mkdtempSync(
    path.join(os.tmpdir(), "no-three-line-test-"),
  );
  const outputPath = path.join(temporaryDirectory, "solutions.js");

  try {
    const result = spawnSync(
      "python3",
      [
        "convert_optimal_solutions.py",
        "optimal-solutions.txt",
        "-o",
        outputPath,
      ],
      { cwd: projectRoot, encoding: "utf8" },
    );

    assert.equal(result.status, 0, result.stderr);
    assert.equal(
      fs.readFileSync(outputPath, "utf8"),
      fs.readFileSync(
        path.join(projectRoot, "optimal-solutions.generated.js"),
        "utf8",
      ),
    );
  } finally {
    fs.rmSync(temporaryDirectory, { recursive: true, force: true });
  }
});
