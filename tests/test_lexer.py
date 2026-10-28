import unittest

from cppcrap.lexer import tokenize


def values(source):
    return [token.value for token in tokenize(source)]


class TokenizeTest(unittest.TestCase):
    def test_drops_comments(self):
        self.assertEqual(values("a // if (x)\nb /* while */ c"), ["a", "b", "c"])

    def test_keeps_line_numbers_across_block_comments(self):
        tokens = tokenize("a\n/* one\ntwo */\nb")
        self.assertEqual([(token.value, token.line) for token in tokens], [("a", 1), ("b", 4)])

    def test_raw_string_is_one_token(self):
        tokens = tokenize('R"d(if (x) { })d"')
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].kind, "str")

    def test_string_escapes_do_not_leak(self):
        self.assertEqual(values(r'"a\"b" + c'), ['"a\\"b"', "+", "c"])

    def test_char_literal_with_quote(self):
        self.assertEqual(values(r"c = '\'' ;"), ["c", "=", r"'\''", ";"])

    def test_digit_separator_is_part_of_number(self):
        tokens = tokenize("1'000'000")
        self.assertEqual([(token.kind, token.value) for token in tokens], [("num", "1'000'000")])

    def test_preprocessor_is_a_single_token(self):
        tokens = tokenize("#define MAX(a, b) ((a) > (b) ? (a) : (b))\nint x;")
        self.assertEqual(tokens[0].kind, "preproc")
        self.assertEqual([token.value for token in tokens[1:]], ["int", "x", ";"])

    def test_line_continuation_joins_lines(self):
        tokens = tokenize("int \\\nx;")
        self.assertEqual([token.line for token in tokens], [1, 2, 2])

    def test_multi_character_operators(self):
        self.assertEqual(values("a && b || c::d ->e <<= f"), ["a", "&&", "b", "||", "c", "::", "d", "->", "e", "<<=", "f"])

    def test_string_prefixes(self):
        tokens = tokenize('u8"hi" L"there"')
        self.assertEqual([token.kind for token in tokens], ["str", "str"])


    def test_unterminated_block_comment_ends_the_input(self):
        self.assertEqual(values("a /* b"), ["a"])

    def test_line_comment_continues_over_a_backslash(self):
        self.assertEqual(values("a // x \\\nb\nc"), ["a", "c"])

    def test_directive_continues_over_a_backslash(self):
        tokens = tokenize("#define X \\\n  1\nint y;")
        self.assertEqual(tokens[0].kind, "preproc")
        self.assertEqual([(token.value, token.line) for token in tokens[1:]], [("int", 3), ("y", 3), (";", 3)])

    def test_escaped_newline_in_a_string_counts_the_line(self):
        self.assertEqual(tokenize('"a\\\nb" c')[-1].line, 2)

    def test_unterminated_raw_string_ends_the_input(self):
        self.assertEqual([token.kind for token in tokenize('x R"d(if (y) {')], ["name", "str"])

    def test_exponents_stay_in_the_number(self):
        self.assertEqual(values("1.5e-3 + 0x1p+4 + .5"), ["1.5e-3", "+", "0x1p+4", "+", ".5"])

    def test_unknown_characters_are_skipped(self):
        self.assertEqual(values("a ` b"), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
