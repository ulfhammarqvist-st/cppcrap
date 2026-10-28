import csv
import io
import unittest

from cppcrap.crap import Assessment
from cppcrap.functions import Function
from cppcrap.report import GREEN, RED, render_csv, render_text


def assessment(name, complexity, coverage, kind="line", measured=True):
    function = Function(name=name, path="a.cpp", start_line=1, end_line=2, complexity=complexity)
    return Assessment(function=function, coverage=coverage, measured=measured, threshold=30, kind=kind)


class RenderTextTest(unittest.TestCase):
    def test_shows_only_the_top_and_counts_the_rest(self):
        items = [assessment(f"f{index}", 20, 0.0) for index in range(4)]
        text = render_text(items, 30, top=3)
        self.assertIn("f2", text)
        self.assertNotIn("f3", text)
        self.assertIn("... and 1 more", text)

    def test_color_marks_crappy_and_clean(self):
        self.assertIn(RED, render_text([assessment("bad", 20, 0.0)], 30, color=True))
        self.assertIn(GREEN, render_text([assessment("good", 1, 1.0)], 30, color=True))
        self.assertNotIn(RED, render_text([assessment("bad", 20, 0.0)], 30))

    def test_names_functions_scored_on_lines_in_a_branch_report(self):
        items = [assessment("branchy", 3, 1.0, "branch"), assessment("straight", 1, 1.0, "line")]
        text = render_text(items, 30, kind="branch")
        self.assertIn("1 functions have no branches; scored on line coverage", text)

    def test_counts_unmeasured_functions(self):
        text = render_text([assessment("orphan", 1, 0.0, kind=None, measured=False)], 30)
        self.assertIn("n/a", text)
        self.assertIn("1 functions had no coverage data", text)

    def test_empty_report_has_no_table(self):
        self.assertNotIn("FUNCTION", render_text([], 30))


class RenderCsvTest(unittest.TestCase):
    def test_empty_report_still_has_a_header(self):
        rows = list(csv.reader(io.StringIO(render_csv([], 30))))
        self.assertEqual(rows, [["file", "line", "function", "complexity", "coverage", "crap", "crappy"]])


if __name__ == "__main__":
    unittest.main()
