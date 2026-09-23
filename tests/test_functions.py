import unittest

from cppcrap.functions import parse_source


def parse(source):
    return {function.name: function for function in parse_source("a.cpp", source)}


class FunctionTest(unittest.TestCase):
    def test_free_function(self):
        functions = parse("int add(int a, int b) { return a + b; }")
        self.assertEqual(list(functions), ["add"])
        self.assertEqual(functions["add"].complexity, 1)

    def test_qualified_by_namespace_and_class(self):
        functions = parse("namespace a { namespace b { struct C { void f() {} }; } }")
        self.assertIn("a::b::C::f", functions)

    def test_anonymous_namespace(self):
        self.assertIn("(anonymous)::f", parse("namespace { void f() {} }"))

    def test_constructor_with_initializer_list(self):
        source = """
        struct C {
            C(int a, int b) : a_(a), b_{b, b}, c_(f(a)) { if (a) { b_[0] = 0; } }
            int a_; std::vector<int> b_; int c_;
        };
        """
        functions = parse(source)
        self.assertIn("C::C", functions)
        self.assertEqual(functions["C::C"].complexity, 2)

    def test_destructor_and_operator(self):
        functions = parse("struct C { ~C() {} bool operator==(const C& o) const { return true; } };")
        self.assertEqual(sorted(functions), ["C::operator==", "C::~C"])

    def test_declarations_are_not_definitions(self):
        source = """
        struct C {
            virtual void pure() = 0;
            void declared();
            C(const C&) = delete;
            ~C() = default;
        };
        int later;
        """
        self.assertEqual(parse(source), {})

    def test_out_of_line_definition_keeps_owner(self):
        functions = parse("void Ledger<int>::run() {}\nvoid Plain::go() {}")
        self.assertEqual(sorted(functions), ["Ledger::run", "Plain::go"])

    def test_trailing_return_and_qualifiers(self):
        source = "struct C { auto f() const noexcept -> std::vector<int> { return {}; } };"
        self.assertIn("C::f", parse(source))

    def test_calls_are_not_functions(self):
        source = "void f() { g(1); obj.h(2); ptr->i(3); }"
        self.assertEqual(list(parse(source)), ["f"])

    def test_complexity_counts_decisions(self):
        source = """
        int f(int x) {
            if (x > 0 && x < 10) { return 1; }
            for (int i = 0; i < x; ++i) {
                while (i > 2 || x == 3) { x--; }
            }
            switch (x) {
                case 1: break;
                case 2: break;
                default: break;
            }
            try { g(); } catch (...) { }
            return x ? 1 : 0;
        }
        """
        self.assertEqual(parse(source)["f"].complexity, 10)

    def test_compile_time_branches_do_not_count(self):
        """`if constexpr` resolves at compile time, so no instantiation can take the other arm.

        Counting them scored a dispatch table of 55 `else if constexpr` arms, fully exercised by
        the suite, as the most complex function in the codebase.
        """
        source = """
        template <typename T>
        int f(T x) {
            if constexpr (sizeof(T) > 4) { return 1; }
            else if constexpr (sizeof(T) > 2) { return 2; }
            if (x) { return 3; }
            return 0;
        }
        """
        self.assertEqual(parse(source)["f"].complexity, 2)

    def test_lambda_complexity_lands_on_enclosing_function(self):
        source = "void f() { auto g = [](int x) { return x > 0 ? 1 : 0; }; }"
        functions = parse(source)
        self.assertEqual(list(functions), ["f"])
        self.assertEqual(functions["f"].complexity, 2)

    def test_line_range_covers_the_body(self):
        source = "\n\nvoid f(int a,\n       int b) {\n  a = b;\n}\n"
        function = parse(source)["f"]
        self.assertEqual((function.start_line, function.end_line, function.lines), (3, 6, 4))

    def test_preprocessor_and_strings_do_not_confuse_the_parser(self):
        source = '''
        #define GUARD if (x) {
        void f() { const char* s = R"(void g() { if (1) {} })"; const char* t = "} void h() {"; }
        '''
        functions = parse(source)
        self.assertEqual(list(functions), ["f"])
        self.assertEqual(functions["f"].complexity, 1)

    def test_test_macros_look_like_functions(self):
        self.assertIn("TEST_F", parse("TEST_F(Suite, Case) { EXPECT_TRUE(true); }"))

    def test_control_keywords_are_never_functions(self):
        source = "void f() {}\nint main() { if (1) { } while (0) { } return 0; }"
        self.assertEqual(sorted(parse(source)), ["f", "main"])


if __name__ == "__main__":
    unittest.main()
