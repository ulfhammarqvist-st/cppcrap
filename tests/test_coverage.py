import os
import tempfile
import unittest

from cppcrap import coverage

LCOV = """TN:
SF:/src/a.cpp
DA:1,3
DA:2,0
DA:4,1
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
 [6, 2, 0, false, false, false]]}]}]}
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


class LookupTest(unittest.TestCase):
    def test_range_coverage(self):
        data = coverage.parse(LCOV)
        self.assertEqual(data.range_coverage("/src/a.cpp", 1, 4), 2 / 3)
        self.assertEqual(data.range_coverage("/src/a.cpp", 2, 2), 0.0)
        self.assertIsNone(data.range_coverage("/src/a.cpp", 10, 20))
        self.assertIsNone(data.range_coverage("/src/missing.cpp", 1, 4))

    def test_matches_by_path_suffix(self):
        data = coverage.parse("SF:/build/../src/a.cpp\nDA:1,1\nend_of_record\n")
        self.assertEqual(data.range_coverage("src/a.cpp", 1, 1), 1.0)

    def test_prefers_longest_matching_suffix(self):
        data = coverage.parse(
            "SF:/one/lib/a.cpp\nDA:1,1\nend_of_record\n"
            "SF:/two/lib/a.cpp\nDA:1,0\nend_of_record\n"
        )
        self.assertEqual(data.range_coverage("/two/lib/a.cpp", 1, 1), 0.0)

    def test_merge_sums_hits(self):
        data = coverage.parse(LCOV).merge(coverage.parse("SF:/src/a.cpp\nDA:2,5\nend_of_record\n"))
        self.assertEqual(data.lines_for("/src/a.cpp")[2], 5)

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "run.info"), "w") as handle:
                handle.write(LCOV)
            data = coverage.load(directory)
        self.assertEqual(data.range_coverage("/src/a.cpp", 1, 1), 1.0)


if __name__ == "__main__":
    unittest.main()
