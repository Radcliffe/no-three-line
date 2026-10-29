"""Regression tests for the multi-file discovery update (also run by npm test)."""

import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import add_solution as updater
from convert_optimal_solutions import format_solution_object, parse_solutions


CODE = "x010212"
DISCOVERER = 'Zoë "A" | B\\C <D>'
DATE = "October 28, 2026"


def fixture():
    source = "Sym.-Gruppe full\n. o o .\no . . o\no . . o\n. o o .\n"
    return {
        "README.md": (
            "The app supports grids from 3 × 3 through 90 × 90.\n"
            "The bundle currently covers 1 size: 4; it omits other sizes.\n"
        ),
        "optimal-solutions.txt": source,
        "optimal-solutions.generated.js": format_solution_object(parse_solutions(source)),
        "ATTRIBUTION.md": "| Size | Class | Attribution | Date | Confidence |\n"
                          "| 4 | `full` | Existing | 1968 | Bound only |\n",
        "optimal-solution-attributions.js": 'const optimalSolutionAttributions = {\n'
                                            '  4: { date: "1968" },\n};\n',
        "test/configuration-codec.test.js": "const numberOfSolutions = 1; // UPDATE\n",
        "test/game.test.js": "assert.deepEqual(unsolved, [\n    3, 5, // UPDATE\n]);\n",
    }


class AddSolutionTests(unittest.TestCase):
    def test_rejects_bad_inputs(self):
        cases = [
            (2, CODE, DISCOVERER, DATE),
            (91, CODE, DISCOVERER, DATE),
            (3, "q010212", DISCOVERER, DATE),
            (3, "x01021", DISCOVERER, DATE),
            (3, "x010213", DISCOVERER, DATE),
            (3, "x010211", DISCOVERER, DATE),
            (3, "x100212", DISCOVERER, DATE),
            (3, "x0102\\", DISCOVERER, DATE),
            (3, ".010101", DISCOVERER, DATE),
            (3, CODE, "", DATE),
            (3, CODE, "Name\nName", DATE),
            (3, CODE, DISCOVERER, "2026-10-28"),
            (3, CODE, DISCOVERER, "February 29, 2026"),
            (3, CODE, DISCOVERER, "October 028, 2026"),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                updater.validate_discovery(*args)
        updater.validate_discovery(3, CODE, DISCOVERER, "February 29, 2028")

    def test_updates_all_files_and_preserves_converter_round_trip(self):
        before = fixture()
        solution = updater.validate_discovery(3, CODE, DISCOVERER, DATE)
        after = updater.prepare_updates(before, solution, DISCOVERER, DATE)
        self.assertEqual(set(after), set(updater.FILES))
        self.assertTrue(all(before[name] != after[name] for name in updater.FILES))
        self.assertEqual(
            format_solution_object(parse_solutions(after["optimal-solutions.txt"])),
            after["optimal-solutions.generated.js"],
        )
        self.assertIn('  3: "x010212",\n  4:', after["optimal-solutions.generated.js"])
        self.assertIn("2 sizes: 3 through 4; it omits 5 through 90.", after["README.md"])
        self.assertIn("numberOfSolutions = 2; // UPDATE", after["test/configuration-codec.test.js"])
        self.assertIn("[\n    5, 6,", after["test/game.test.js"])
        self.assertIn("90, // UPDATE", after["test/game.test.js"])
        self.assertIn("Zoë &#34;A&#34; &#124; B&#92;C &#60;D&#62;", after["ATTRIBUTION.md"])
        self.assertIn('Zoë \\"A\\" | B\\\\C <D>', after["optimal-solution-attributions.js"])
        self.assertIn(f"{DATE} | Explicit |\n| 4", after["ATTRIBUTION.md"])
        with self.assertRaisesRegex(ValueError, "already has"):
            updater.prepare_updates(after, solution, DISCOVERER, DATE)

    def test_missing_markers_or_drift_fail_before_writing(self):
        solution = updater.validate_discovery(3, CODE, DISCOVERER, DATE)
        for name in ("README.md", "test/game.test.js", "test/configuration-codec.test.js",
                     "optimal-solutions.generated.js", "ATTRIBUTION.md",
                     "optimal-solution-attributions.js"):
            before = fixture()
            before[name] = "unexpected content\n"
            with self.subTest(name=name), self.assertRaises(ValueError):
                updater.prepare_updates(before, solution, DISCOVERER, DATE)

    def test_insert_after_last_entry_and_empty_missing_list(self):
        self.assertEqual(updater.size_ranges([]), "none")
        self.assertEqual(updater.size_ranges([3, 4, 6, 8, 9]), "3 through 4, 6, and 8 through 9")
        text = "const credits = {\n  4: {\n    date: \"1968\",\n  },\n};\n"
        added = updater.insert_by_size(text, r"^  (\d+): \{[^}]*\},\n", 5, "  5: {},\n")
        self.assertTrue(added.endswith("  },\n  5: {},\n};\n"))
        self.assertEqual(
            updater.replace_once("    90, // UPDATE\n", r"^    [\d, ]*// UPDATE$", "    // UPDATE"),
            "    // UPDATE\n",
        )

    def test_interactive_workflow_and_rollback(self):
        for failure in (None, subprocess.CalledProcessError(1, ["npm", "test"]),
                        FileNotFoundError("npm unavailable"), KeyboardInterrupt()):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                before = fixture()
                for name, content in before.items():
                    (root / name).parent.mkdir(parents=True, exist_ok=True)
                    (root / name).write_text(content, encoding="utf-8")
                output = io.StringIO()
                with patch.object(updater, "ROOT", root), \
                     patch("builtins.input", side_effect=["3", CODE, DISCOVERER, DATE]), \
                     patch.object(updater.subprocess, "run", side_effect=failure) as run, \
                     contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = updater.main()
                run.assert_called_once_with(["npm", "test"], cwd=root, check=True)
                if failure is None:
                    self.assertEqual(result, 0)
                    self.assertIn("npm test passed", output.getvalue())
                    self.assertIn(CODE, (root / "optimal-solutions.generated.js").read_text())
                else:
                    self.assertNotEqual(result, 0)
                    self.assertNotIn("npm test passed", output.getvalue())
                    for name, content in before.items():
                        self.assertEqual((root / name).read_text(encoding="utf-8"), content)


if __name__ == "__main__":
    unittest.main()
