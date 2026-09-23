from dataclasses import dataclass

DEFAULT_THRESHOLD = 30.0


def crap_score(complexity, coverage):
    uncovered = max(0.0, min(1.0, 1.0 - coverage))
    return complexity ** 2 * uncovered ** 3 + complexity


def required_coverage(complexity, threshold):
    if complexity > threshold:
        return None
    if complexity == 0:
        return 0.0
    return max(0.0, 1.0 - ((threshold - complexity) / complexity ** 2) ** (1.0 / 3.0))


def affordable_complexity(coverage, threshold):
    complexity = 1
    while crap_score(complexity + 1, coverage) <= threshold:
        complexity += 1
    return complexity


@dataclass
class Assessment:
    function: object
    coverage: float
    measured: bool
    threshold: float
    kind: str = None

    @property
    def score(self):
        return crap_score(self.function.complexity, self.coverage)

    @property
    def crappy(self):
        return self.score > self.threshold

    @property
    def compile_time_only(self):
        """A constexpr function the program never ran. Its work happened while it was compiled, and
        a coverage report cannot see that; zero here is not a gap a test could close."""
        return getattr(self.function, "compile_time", False) and self.measured and self.coverage == 0.0

    @property
    def beyond_testing(self):
        return self.function.complexity > self.threshold

    def advice(self):
        complexity = self.function.complexity
        if not self.crappy:
            return "ok"
        if self.beyond_testing:
            return (
                f"split it: complexity {complexity} stays above {self.threshold:g} "
                "even at 100% coverage"
            )
        needed = required_coverage(complexity, self.threshold)
        affordable = affordable_complexity(self.coverage, self.threshold)
        return (
            f"cover {needed:.0%} of its lines (now {self.coverage:.0%}) "
            f"or cut complexity {complexity} -> {affordable}"
        )


def assess(functions, coverage_data, threshold=DEFAULT_THRESHOLD, kind="line"):
    assessments = []
    for function in functions:
        measured = coverage_data.range_coverage(
            function.path, function.start_line, function.end_line, kind
        )
        assessments.append(
            Assessment(
                function=function,
                coverage=measured.value if measured else 0.0,
                measured=measured is not None,
                threshold=threshold,
                kind=measured.kind if measured else None,
            )
        )
    assessments.sort(key=lambda item: (-item.score, item.function.path, item.function.start_line))
    return assessments
