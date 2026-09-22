import argparse
import fnmatch
import os
import sys

from . import __version__
from . import coverage as coverage_module
from . import report
from .crap import DEFAULT_THRESHOLD, assess
from .functions import parse_file

SOURCE_EXTENSIONS = (".c", ".cc", ".cpp", ".cxx", ".c++", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl", ".tcc")
DEFAULT_EXCLUDES = (
    "*/test/*", "*/tests/*", "*_test.*", "*_tests.*", "*_unittest.*", "*Test.*",
    "*.test.*", "*.tests.*",
    "*/build*/*", "*/cmake-build*/*", "*/_deps/*", "*/external/*", "*/ext/*", "*/third_party/*",
    "*/vendor/*", "*/node_modules/*", "*/.git/*",
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cppcrap",
        description="Change Risk Anti-Patterns (CRAP) for C++: complexity you have not tested.",
        epilog="CRAP = complexity^2 * (1 - coverage)^3 + complexity",
    )
    parser.add_argument("paths", nargs="*", default=["."], help="source files or directories")
    parser.add_argument("-c", "--coverage", action="append", default=[], metavar="PATH",
                        help="lcov .info, llvm-cov json, cobertura xml, .gcov, or a directory of them")
    parser.add_argument("-t", "--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="score above which a function counts as crap (default: %(default)s)")
    parser.add_argument("-f", "--format", choices=("text", "json", "csv"), default="text")
    parser.add_argument("--top", type=int, default=25, help="rows to print (default: %(default)s)")
    parser.add_argument("--all", action="store_true", help="print every function")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    parser.add_argument("--no-default-excludes", action="store_true")
    parser.add_argument("--min-complexity", type=int, default=1)
    parser.add_argument("--skip-unmeasured", action="store_true",
                        help="ignore functions absent from the coverage data")
    parser.add_argument("--assume-untested", action="store_true",
                        help="run without coverage and score every function as 0%% covered")
    parser.add_argument("--exit-zero", action="store_true", help="always exit 0")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--version", action="version", version=f"cppcrap {__version__}")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    paths = args.paths or ["."]
    excludes = list(args.exclude) + ([] if args.no_default_excludes else list(DEFAULT_EXCLUDES))

    sources = collect_sources(paths, excludes)
    if not sources:
        print("no C++ sources found", file=sys.stderr)
        return 2

    if not args.coverage and not args.assume_untested:
        return fail(
            "no coverage data given -- refusing to invent it.",
            "CRAP is complexity weighed against coverage; without coverage this is",
            "a complexity list, not a risk report. Pass --coverage PATH, or",
            "--assume-untested if you really mean to score everything as 0% covered.",
        )

    data = coverage_module.CoverageData()
    for path in args.coverage:
        try:
            data.merge(coverage_module.load(path))
        except (OSError, ValueError) as error:
            return fail(f"{error}", "the coverage run did not produce usable data.")
    if args.coverage and not data:
        return fail(
            "the coverage input is empty.",
            "Your coverage run produced a file but no line data in it.",
        )

    functions = []
    for path in sources:
        functions.extend(
            function for function in parse_file(path)
            if function.complexity >= args.min_complexity
        )

    assessments = assess(functions, data, args.threshold)
    if args.coverage and not any(item.measured for item in assessments):
        return fail(
            f"the coverage data matches none of the {len(assessments)} functions found.",
            "Stale report, a different source tree, or a build that never ran the tests.",
            "Files in the report: " + ", ".join(sorted(data.files)[:3]) + " ...",
        )
    if args.skip_unmeasured:
        assessments = [item for item in assessments if item.measured]
    root = os.getcwd()
    top = len(assessments) if args.all else args.top
    if args.format == "json":
        sys.stdout.write(report.render_json(assessments, args.threshold, root))
    elif args.format == "csv":
        sys.stdout.write(report.render_csv(assessments, args.threshold, root))
    else:
        color = not args.no_color and sys.stdout.isatty()
        sys.stdout.write(report.render_text(assessments, args.threshold, top, color, root, args.all))

    if args.exit_zero:
        return 0
    return 1 if any(item.crappy for item in assessments) else 0


def fail(*lines):
    print(f"cppcrap: {lines[0]}", file=sys.stderr)
    for line in lines[1:]:
        print(f"         {line}", file=sys.stderr)
    return 2


def collect_sources(paths, excludes):
    found = []
    for path in paths:
        if os.path.isfile(path):
            found.append(os.path.realpath(path))
            continue
        for root, directories, names in os.walk(path):
            directories[:] = [name for name in directories if not name.startswith(".")]
            for name in sorted(names):
                if name.endswith(SOURCE_EXTENSIONS):
                    found.append(os.path.realpath(os.path.join(root, name)))
    return [path for path in dict.fromkeys(found) if not _excluded(path, excludes)]


def _excluded(path, excludes):
    relative = os.path.relpath(path, os.getcwd())
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(relative, pattern)
        or fnmatch.fnmatch("/" + relative, pattern)
        for pattern in excludes
    )
