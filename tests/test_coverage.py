import os
import tempfile
import unittest

from cppcrap import coverage

LCOV = """TN:
SF:/src/a.cpp
DA:1,3
DA:2,0
DA:4,1
BRDA:1,0,0,3
BRDA:1,0,1,0
BRDA:2,0,0,-
BRDA:2,0,1,-
end_of_record
SF:/src/b.cpp
DA:1,0
end_of_record
"""

LLVM_JSON = """
{"data": [{"files": [{"filename": "/src/a.cpp", "segments": [
 [1, 15, 3, true, true, false],
 [2, 10, 0, true, true, false],
 [4, 4, 3, true, false, false],
 [6, 2, 0, false, false, false]],
 "branches": [[2, 9, 2, 14, 3, 0, 0, 0, 4]],
 "expansions": [{"source_region": [5, 3, 5, 20, 3, 0, 0, 0],
                 "branches": [[90, 1, 90, 9, 1, 1, 0, 0, 4]]}]}]}]}
"""

COBERTURA = """<?xml version="1.0"?>
<coverage><sources><source>/src</source></sources><packages><package><classes>
<class filename="a.cpp"><lines>
<line number="1" hits="3"/><line number="2" hits="0"/><line number="4" hits="1"/>
</lines></class></classes></package></packages></coverage>
"""

GCOV = """        -:    0:Source:/src/a.cpp
        3:    1:int f() {
    #####:    2:  if (x) {
        -:    3:  // comment
        1:    4:  return 1;
"""


class ParseTest(unittest.TestCase):
    def assert_a_cpp(self, data):
        self.assertEqual(data.lines_for("/src/a.cpp"), {1: 3, 2: 0, 4: 1})

    def test_lcov(self):
        data = coverage.parse(LCOV)
        self.assert_a_cpp(data)
        self.assertEqual(data.lines_for("/src/b.cpp"), {1: 0})

    def test_llvm_json(self):
        data = coverage.parse(LLVM_JSON)
        self.assertEqual(data.lines_for("/src/a.cpp"), {1: 3, 2: 3, 3: 0, 4: 0, 5: 3, 6: 3})

    def test_cobertura(self):
        self.assert_a_cpp(coverage.parse(COBERTURA))

    def test_gcov(self):
        self.assert_a_cpp(coverage.parse(GCOV, "a.cpp.gcov"))

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            coverage.parse("not coverage data")


class BranchTest(unittest.TestCase):
    def test_lcov_outcomes(self):
        data = coverage.parse(LCOV)
        self.assertTrue(data.has_branches)
        self.assertEqual(data.branches_for("/src/a.cpp"), {1: (1, 2), 2: (0, 2)})

    def test_llvm_json_counts_both_outcomes_and_expansions(self):
        data = coverage.parse(LLVM_JSON)
        self.assertEqual(data.branches_for("/src/a.cpp"), {2: (1, 2), 5: (2, 2)})

    def test_cobertura_conditions(self):
        text = COBERTURA.replace('<line number="2" hits="0"/>',
                                 '<line number="2" hits="0" branch="true" '
                                 'condition-coverage="50% (1/2)"/>')
        self.assertEqual(coverage.parse(text).branches_for("/src/a.cpp"), {2: (1, 2)})

    def test_gcov_branch_lines(self):
        text = GCOV + "branch  0 taken 4\nbranch  1 never executed\n"
        self.assertEqual(coverage.parse(text, "a.cpp.gcov").branches_for("/src/a.cpp"), {4: (1, 2)})

    def test_data_without_branches(self):
        self.assertFalse(coverage.parse(GCOV, "a.cpp.gcov").has_branches)

    def test_branch_range_coverage(self):
        data = coverage.parse(LCOV)
        self.assertEqual(data.range_coverage("/src/a.cpp", 1, 2, "branch"), (0.25, "branch"))

    def test_branchless_range_falls_back_to_lines(self):
        data = coverage.parse(LCOV)
        self.assertEqual(data.range_coverage("/src/a.cpp", 4, 4, "branch"), (1.0, "line"))

    def test_merging_two_runs_does_not_double_the_branch(self):
        data = coverage.parse(LCOV).merge(coverage.parse(LCOV))
        self.assertEqual(data.branches_for("/src/a.cpp")[1], (1, 2))

    def test_merging_two_runs_combines_what_each_reached(self):
        other = LCOV.replace("BRDA:1,0,0,3", "BRDA:1,0,0,-").replace("BRDA:1,0,1,0", "BRDA:1,0,1,7")
        data = coverage.parse(LCOV).merge(coverage.parse(other))
        self.assertEqual(data.branches_for("/src/a.cpp")[1], (2, 2))

    def test_template_instantiations_are_one_source_branch(self):
        # Three stampings of the same `while (a && b)`; only one run reached either outcome.
        instantiated = """
{"data": [{"files": [{"filename": "/src/a.cpp", "segments": [], "branches": [
 [7, 10, 7, 20, 4, 1, 0, 0, 4], [7, 24, 7, 40, 4, 1, 0, 0, 4],
 [7, 10, 7, 20, 0, 0, 0, 0, 4], [7, 24, 7, 40, 0, 0, 0, 0, 4],
 [7, 10, 7, 20, 0, 0, 0, 0, 4], [7, 24, 7, 40, 0, 0, 0, 0, 4]]}]}]}
"""
        self.assertEqual(coverage.parse(instantiated).branches_for("/src/a.cpp"), {7: (4, 4)})


class LookupTest(unittest.TestCase):
    def test_range_coverage(self):
        data = coverage.parse(LCOV)
        self.assertEqual(data.range_coverage("/src/a.cpp", 1, 4), (2 / 3, "line"))
        self.assertEqual(data.range_coverage("/src/a.cpp", 2, 2), (0.0, "line"))
        self.assertIsNone(data.range_coverage("/src/a.cpp", 10, 20))
        self.assertIsNone(data.range_coverage("/src/missing.cpp", 1, 4))

    def test_matches_by_path_suffix(self):
        data = coverage.parse("SF:/build/../src/a.cpp\nDA:1,1\nend_of_record\n")
        self.assertEqual(data.range_coverage("src/a.cpp", 1, 1).value, 1.0)

    def test_prefers_longest_matching_suffix(self):
        data = coverage.parse(
            "SF:/one/lib/a.cpp\nDA:1,1\nend_of_record\n"
            "SF:/two/lib/a.cpp\nDA:1,0\nend_of_record\n"
        )
        self.assertEqual(data.range_coverage("/two/lib/a.cpp", 1, 1).value, 0.0)

    def test_merge_sums_hits(self):
        data = coverage.parse(LCOV).merge(coverage.parse("SF:/src/a.cpp\nDA:2,5\nend_of_record\n"))
        self.assertEqual(data.lines_for("/src/a.cpp")[2], 5)

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "run.info"), "w") as handle:
                handle.write(LCOV)
            data = coverage.load(directory)
        self.assertEqual(data.range_coverage("/src/a.cpp", 1, 1).value, 1.0)


if __name__ == "__main__":
    unittest.main()
