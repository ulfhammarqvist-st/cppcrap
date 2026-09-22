import csv
import io
import json
import os

RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def summarise(assessments, threshold):
    crappy = [item for item in assessments if item.crappy]
    unmeasured = [item for item in assessments if not item.measured]
    return {
        "functions": len(assessments),
        "crappy": len(crappy),
        "unmeasured": len(unmeasured),
        "branch_measured": sum(1 for item in assessments if item.kind == "branch"),
        "worst": max((item.score for item in assessments), default=0.0),
        "debt": sum(item.score - threshold for item in crappy),
        "threshold": threshold,
    }


def render_text(assessments, threshold, top=25, color=False, root=".", show_all=False, kind="line"):
    paint = _painter(color)
    lines = [paint(BOLD, f"CRAP report  (threshold {threshold:g}, {kind} coverage)"), ""]
    shown = assessments if show_all else ([item for item in assessments if item.crappy] or assessments)
    hidden = max(0, len(shown) - top)
    shown = shown[:top]
    if shown:
        lines.append(
            paint(DIM, f"  {'CRAP':>7} {'CX':>4} {'COV':>6} {'LINES':>6}  FUNCTION")
        )
    for item in shown:
        function = item.function
        style = RED if item.crappy else (YELLOW if item.score > threshold / 2 else GREEN)
        coverage = f"{item.coverage:.0%}" if item.measured else "n/a"
        lines.append(
            f"  {paint(style, f'{item.score:7.1f}')} {function.complexity:4d} "
            f"{coverage:>6} {function.lines:6d}  {function.name}"
        )
        location = f"{os.path.relpath(function.path, root)}:{function.start_line}"
        detail = f"{location} — {item.advice()}" if item.crappy else location
        lines.append(paint(DIM, f"          {detail}"))
    if hidden:
        lines.append(paint(DIM, f"  ... and {hidden} more"))
    summary = summarise(assessments, threshold)
    lines.append("")
    lines.append(
        f"  {summary['functions']} functions, "
        f"{paint(RED if summary['crappy'] else GREEN, str(summary['crappy']) + ' crappy')}, "
        f"worst {summary['worst']:.1f}, debt {summary['debt']:.1f}"
    )
    if kind == "branch" and summary["branch_measured"] < summary["functions"] - summary["unmeasured"]:
        fell_back = summary["functions"] - summary["unmeasured"] - summary["branch_measured"]
        lines.append(paint(DIM, f"  {fell_back} functions have no branches; scored on line coverage"))
    if summary["unmeasured"]:
        lines.append(
            paint(DIM, f"  {summary['unmeasured']} functions had no coverage data (counted as 0%)")
        )
    return "\n".join(lines) + "\n"


def render_json(assessments, threshold, root=".", kind="line"):
    payload = {
        "summary": dict(summarise(assessments, threshold), coverage_kind=kind),
        "functions": [_row(item, root) for item in assessments],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_csv(assessments, threshold, root="."):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(_row(assessments[0], root)) if assessments else
                            ["file", "line", "function", "complexity", "coverage", "crap", "crappy"])
    writer.writeheader()
    for item in assessments:
        writer.writerow(_row(item, root))
    return buffer.getvalue()


def _row(item, root):
    function = item.function
    return {
        "file": os.path.relpath(function.path, root),
        "line": function.start_line,
        "end_line": function.end_line,
        "function": function.name,
        "complexity": function.complexity,
        "coverage": round(item.coverage, 4) if item.measured else None,
        "coverage_kind": item.kind,
        "crap": round(item.score, 2),
        "crappy": item.crappy,
        "advice": item.advice(),
    }


def _painter(color):
    if not color:
        return lambda style, text: text
    return lambda style, text: f"{style}{text}{RESET}"
