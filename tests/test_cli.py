import contextlib
import io
import json
import os
import tempfile
import unittest

from cppcrap.cli import main

SOURCE = """
int tangle(int x, int y) {
    if (x > 0 && y > 0) { return 1; }
    for (int i = 0; i < x; ++i) {
        if (i % 2 == 0 || y == i) { y += i; }
        while (y > 100) { y /= 2; }
    }
    switch (y) {
        case 1: return 2;
        case 2: return 3;
        case 3: return 4;
        default: return 5;
    }
}

int trivial(int x) { return x; }
"""

TEST_SOURCE = "void helper_test() { if (1) { } }\n"


def lcov(path, covered_lines, all_lines):
    records = "".join(f"DA:{line},{1 if line in covered_lines else 0}\n" for line in all_lines)
    return f"TN:\nSF:{path}\n{records}end_of_record\n"


class CliTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = self.directory.name
        os.mkdir(os.path.join(root, "src"))
        os.mkdir(os.path.join(root, "tests"))
        self.source = os.path.join(root, "src", "tangle.cpp")
        self.write(self.source, SOURCE)
        self.write(os.path.join(root, "tests", "tangle_test.cpp"), TEST_SOURCE)
        self.coverage = os.path.join(root, "coverage.info")
        self.write(self.coverage, lcov(self.source, {3, 4}, range(2, 15)))
        previous = os.getcwd()
        os.chdir(root)
        self.addCleanup(os.chdir, previous)

    def write(self, path, text):
        with open(path, "w") as handle:
            handle.write(text)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_reports_and_fails_on_crap(self):
        code, out, _ = self.run_cli("src", "-c", self.coverage, "--no-color")
        self.assertEqual(code, 1)
        self.assertIn("tangle", out)
        self.assertIn("1 crappy", out)

    def test_exit_zero_still_reports(self):
        code, out, _ = self.run_cli("src", "-c", self.coverage, "--exit-zero")
        self.assertEqual(code, 0)
        self.assertIn("crappy", out)

    def test_generous_threshold_passes(self):
        code, _, _ = self.run_cli("src", "-c", self.coverage, "--threshold", "1000")
        self.assertEqual(code, 0)

    def test_json_output(self):
        _, out, _ = self.run_cli("src", "-c", self.coverage, "--format", "json")
        payload = json.loads(out)
        names = {row["function"]: row for row in payload["functions"]}
        self.assertEqual(payload["summary"]["crappy"], 1)
        self.assertTrue(names["tangle"]["crappy"])
        self.assertFalse(names["trivial"]["crappy"])
        self.assertEqual(names["tangle"]["file"], os.path.join("src", "tangle.cpp"))

    def test_csv_output(self):
        _, out, _ = self.run_cli("src", "-c", self.coverage, "--format", "csv")
        self.assertEqual(out.splitlines()[0].split(",")[:4], ["file", "line", "end_line", "function"])
        self.assertEqual(len(out.splitlines()), 3)

    def test_test_files_are_excluded_by_default(self):
        _, out, _ = self.run_cli(".", "-c", self.coverage, "--format", "json")
        self.assertNotIn("helper_test", out)

    def test_excludes_can_be_disabled(self):
        _, out, _ = self.run_cli(".", "-c", self.coverage, "--format", "json", "--no-default-excludes")
        self.assertIn("helper_test", out)

    def test_min_complexity_filters(self):
        _, out, _ = self.run_cli("src", "-c", self.coverage, "--format", "json", "--min-complexity", "5")
        self.assertEqual([row["function"] for row in json.loads(out)["functions"]], ["tangle"])

    def test_missing_coverage_is_fatal(self):
        code, out, err = self.run_cli("src", "--format", "json")
        self.assertEqual(code, 2)
        self.assertIn("refusing to invent it", err)
        self.assertEqual(out, "")

    def test_missing_coverage_can_be_forced(self):
        code, out, _ = self.run_cli("src", "--format", "json", "--assume-untested")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["summary"]["unmeasured"], 2)

    def test_coverage_that_matches_nothing_is_fatal(self):
        self.write("other.info", lcov("/elsewhere/other.cpp", {1}, range(1, 5)))
        code, out, err = self.run_cli("src", "-c", "other.info")
        self.assertEqual(code, 2)
        self.assertIn("matches none of the", err)
        self.assertEqual(out, "")

    def test_empty_coverage_is_fatal(self):
        self.write("empty.info", "TN:\n")
        code, _, err = self.run_cli("src", "-c", "empty.info")
        self.assertEqual(code, 2)
        self.assertIn("empty", err)

    def test_skip_unmeasured(self):
        _, out, _ = self.run_cli("src", "-c", self.coverage, "--format", "json", "--skip-unmeasured")
        rows = json.loads(out)["functions"]
        self.assertEqual([row["function"] for row in rows], ["tangle"])

    def test_branch_coverage_is_used_when_available(self):
        self.write("branchy.info", lcov(self.source, {3, 4, 16}, range(2, 17)).replace(
            "end_of_record", "BRDA:3,0,0,1\nBRDA:3,0,1,0\nBRDA:5,0,0,-\nBRDA:5,0,1,-\nend_of_record"))
        _, out, _ = self.run_cli("src", "-c", "branchy.info", "--format", "json")
        rows = {row["function"]: row for row in json.loads(out)["functions"]}
        self.assertEqual(json.loads(out)["summary"]["coverage_kind"], "branch")
        self.assertEqual(rows["tangle"]["coverage_kind"], "branch")
        self.assertEqual(rows["tangle"]["coverage"], 0.25)
        self.assertEqual(rows["trivial"]["coverage_kind"], "line")
        self.assertEqual(rows["trivial"]["coverage"], 1.0)

    def test_line_coverage_can_be_forced(self):
        _, out, _ = self.run_cli("src", "-c", self.coverage, "--format", "json",
                                 "--coverage-kind", "line")
        self.assertEqual(json.loads(out)["summary"]["coverage_kind"], "line")

    def test_branch_coverage_without_branch_data_is_an_error(self):
        code, _, err = self.run_cli("src", "-c", self.coverage, "--coverage-kind", "branch")
        self.assertEqual(code, 2)
        self.assertIn("carries none", err)

    def test_text_report_names_the_coverage_kind(self):
        _, out, _ = self.run_cli("src", "-c", self.coverage, "--no-color")
        self.assertIn("line coverage", out)

    def test_broken_coverage_file_is_an_error(self):
        self.write("junk.info", "definitely not coverage")
        code, _, err = self.run_cli("src", "-c", "junk.info")
        self.assertEqual(code, 2)
        self.assertIn("unrecognised coverage format", err)

    def test_no_sources_is_an_error(self):
        os.mkdir("empty")
        code, _, err = self.run_cli("empty")
        self.assertEqual(code, 2)
        self.assertIn("no C++ sources", err)


if __name__ == "__main__":
    unittest.main()
