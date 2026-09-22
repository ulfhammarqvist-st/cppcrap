# cppcrap

A CRAP tester for C++. It finds the functions that are both complicated and untested — the ones
that will bite you when you change them.

```
CRAP = complexity² × (1 − coverage)³ + complexity
```

The metric is Alberto Savoia's, popularised by Uncle Bob's rule for legacy code: a function may be
hairy, or it may be untested, but it may not be both. Ten branches with a test suite behind them
score 10. The same ten branches with nothing behind them score 110. Anything over 30 is crap.

The tool tells you which of the two ways out is still open:

```
CRAP report  (threshold 30)

     CRAP   CX    COV  LINES  FUNCTION
     67.0   21    53%     34  shop::Pricing::total
          examples/demo/src/pricing.cpp:7 — cover 73% of its lines (now 53%) or cut complexity 21 -> 12

  4 functions, 1 crappy, worst 67.0, debt 37.0
```

Exit code is 1 when anything is crap, so it works as a build gate.

## Install

```sh
pip install -e .
```

No dependencies, no compile database, no build integration. It reads your sources and your existing
coverage report.

## Use

```sh
cppcrap src include --coverage build/coverage.info
cppcrap src -c build/coverage.json --threshold 20 --format json > crap.json
cppcrap src -c build/coverage/ --exit-zero        # report without failing the build
```

Coverage input can be an lcov tracefile, `llvm-cov export` JSON, a Cobertura XML from gcovr, a
`.gcov` file, or a directory holding any of them. Several `--coverage` flags are merged.

### Producing coverage

clang:

```sh
clang++ -fprofile-instr-generate -fcoverage-mapping -O0 -g -o tests ...
LLVM_PROFILE_FILE=tests.profraw ./tests
llvm-profdata merge -sparse tests.profraw -o tests.profdata
llvm-cov export ./tests -instr-profile=tests.profdata -format=lcov > coverage.info
```

For a CMake project with a ctest suite, `scripts/cmake-coverage.sh <source-dir>` does all of it:
configures an instrumented Debug build, runs the tests with one profile per process, merges them and
exports `coverage.info`. It passes the instrumentation as global flags rather than through a
project's own coverage option, because a project that adds `--coverage` after `add_subdirectory()`
leaves those targets linking instrumented libraries without the runtime.

gcc:

```sh
g++ --coverage -O0 -g -o tests ...
./tests && gcov *.gcda           # or: lcov -c -d . -o coverage.info
```

### CI

```yaml
- run: ctest --test-dir build
- run: llvm-cov export ./build/tests -instr-profile=build/tests.profdata -format=lcov > cov.info
- run: cppcrap src include --coverage cov.info --threshold 30
```

Start by pointing it at the code you are about to change, not the whole tree. On a legacy codebase
raise the threshold until the build is green, then ratchet it down.

## Options

| flag | meaning |
| --- | --- |
| `-c, --coverage PATH` | coverage file or directory, repeatable |
| `-t, --threshold N` | crap limit, default 30 |
| `-f, --format text\|json\|csv` | output shape |
| `--top N` / `--all` | how many rows to print |
| `--exclude GLOB` | skip paths, repeatable |
| `--no-default-excludes` | keep tests, build and vendor directories |
| `--min-complexity N` | ignore functions below this complexity |
| `--skip-unmeasured` | ignore functions your coverage report never mentions |
| `--assume-untested` | run with no coverage at all and score everything as 0% covered |
| `--exit-zero` | never fail the build |

Test, build, vendor and third-party directories are excluded by default.

**No coverage, no report.** The tool exits 2, without printing a report, when no `--coverage` is
given, when the file it is given holds no line data, or when the coverage it loaded matches none of
the functions it found — a stale report or a test run that never happened. A score computed from
coverage nobody produced is a lie with a number on it. `--assume-untested` says you meant it.

Individual functions the coverage report never mentions are counted as untested, which is usually
the truth. Platform-gated code is the exception — a `#if _WIN32` branch is not untested on a mac,
it is unbuilt, and the report marks its coverage `n/a`. `--skip-unmeasured` drops those rows.

## How it measures

Complexity is cyclomatic: one, plus one for every `if`, `for`, `while`, `case`, `catch`, `&&`,
`||` and `?`. Lambdas and nested classes count towards the function that contains them.

`if constexpr` counts like any other branch. The path is chosen at compile time, but the coverage
report still measures it: a chain instantiated with three of its fifty types leaves the other
forty-seven branches without line hits, and a template nothing instantiates has no coverage data at
all, which the tool reads as untested. Both halves of the formula have to count the same code, so
compile-time branches are branches. Preprocessor conditionals are the exception — the parser sees
every `#if` arm but the coverage report only knows the one that was compiled.

Coverage for a function is the share of its instrumented lines that ran, taken from the line data
in the coverage report. Header-only and template code is measured the same way as anything else.

Parsing is done by a small C++ tokenizer, not a compiler, so it needs no flags and no build system
and it accepts code that will not compile. The trade-offs: function-like macros
(`TEST_F(Suite, Case) { ... }`) are reported as functions, macros that hide control flow are not
expanded, and a function whose signature is split across `#if`/`#else` branches merges with the one
after it. Amalgamated headers are where you notice; ordinary code is fine.

## Demo

```sh
examples/demo/run.sh
```

Builds a small library with clang coverage, runs its tests, and reports the crap. Requires clang.

## Tests

```sh
python3 -m unittest discover -s tests -t .
```
