import unittest

from cppcrap import coverage
from cppcrap.crap import Assessment, affordable_complexity, assess, crap_score, required_coverage
from cppcrap.functions import Function


def function(name, complexity, start=1, end=10, path="/src/a.cpp"):
    return Function(name=name, path=path, start_line=start, end_line=end, complexity=complexity)


class ScoreTest(unittest.TestCase):
    def test_fully_covered_scores_its_complexity(self):
        self.assertEqual(crap_score(10, 1.0), 10)

    def test_untested_is_punished_cubically(self):
        self.assertEqual(crap_score(10, 0.0), 110)
        self.assertEqual(crap_score(10, 0.5), 22.5)

    def test_simple_code_is_safe_even_untested(self):
        self.assertEqual(crap_score(1, 0.0), 2)

    def test_coverage_outside_range_is_clamped(self):
        self.assertEqual(crap_score(4, 1.5), 4)

    def test_required_coverage_hits_the_threshold(self):
        needed = required_coverage(10, 30)
        self.assertAlmostEqual(crap_score(10, needed), 30)

    def test_required_coverage_is_impossible_above_threshold(self):
        self.assertIsNone(required_coverage(31, 30))

    def test_affordable_complexity(self):
        self.assertEqual(affordable_complexity(1.0, 30), 30)
        self.assertEqual(affordable_complexity(0.0, 30), 5)


class AssessTest(unittest.TestCase):
    def setUp(self):
        self.data = coverage.parse(
            "SF:/src/a.cpp\n" + "".join(f"DA:{line},{line % 2}\n" for line in range(1, 11))
            + "end_of_record\n"
        )

    def test_scores_and_sorts(self):
        results = assess([function("small", 2), function("big", 14)], self.data, 30)
        self.assertEqual([item.function.name for item in results], ["big", "small"])
        self.assertEqual(results[0].coverage, 0.5)
        self.assertEqual(results[0].score, 14 ** 2 * 0.125 + 14)
        self.assertTrue(results[0].crappy)
        self.assertFalse(results[1].crappy)

    def test_missing_coverage_counts_as_untested(self):
        results = assess([function("orphan", 6, path="/src/zz.cpp")], self.data, 30)
        self.assertFalse(results[0].measured)
        self.assertEqual(results[0].coverage, 0.0)
        self.assertTrue(results[0].crappy)

    def test_advice_demands_coverage_when_reachable(self):
        results = assess([function("big", 14)], self.data, 30)
        self.assertIn("cover 57% of its lines (now 50%)", results[0].advice())

    def test_advice_demands_refactoring_when_hopeless(self):
        results = assess([function("monster", 40)], self.data, 30)
        self.assertTrue(results[0].beyond_testing)
        self.assertIn("split it", results[0].advice())


if __name__ == "__main__":
    unittest.main()


class CompileTimeTest(unittest.TestCase):
    def assess_one(self, compile_time, covered):
        function = Function(
            name="buildTable", path="/src/a.hpp", start_line=1, end_line=9,
            complexity=3, compile_time=compile_time)
        return Assessment(function=function, coverage=covered, measured=True, threshold=10)

    def test_a_constexpr_function_the_program_never_ran_is_not_a_gap(self):
        self.assertTrue(self.assess_one(True, 0.0).compile_time_only)

    def test_a_constexpr_function_that_did_run_is_scored_as_usual(self):
        self.assertFalse(self.assess_one(True, 0.4).compile_time_only)

    def test_an_ordinary_uncovered_function_is_still_a_gap(self):
        self.assertFalse(self.assess_one(False, 0.0).compile_time_only)
