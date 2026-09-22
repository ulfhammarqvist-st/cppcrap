import json
import os
import re
import xml.etree.ElementTree as ElementTree

GCOV_LINE = re.compile(r"^\s*([^:]+):\s*(\d+):")


class CoverageData:
    def __init__(self, files=None):
        self.files = dict(files or {})
        self._index = {}
        for path in self.files:
            self._index.setdefault(_key(path), []).append(path)

    def __bool__(self):
        return bool(self.files)

    def merge(self, other):
        for path, hits in other.files.items():
            target = self.files.setdefault(path, {})
            for line, count in hits.items():
                target[line] = target.get(line, 0) + count
            self._index.setdefault(_key(path), []).append(path)
        return self

    def lines_for(self, path):
        real = os.path.realpath(path)
        if real in self.files:
            return self.files[real]
        candidates = self._index.get(_key(path))
        if not candidates:
            return None
        if len(candidates) == 1:
            return self.files[candidates[0]]
        best = max(candidates, key=lambda other: _common_suffix(other, real))
        return self.files[best]

    def range_coverage(self, path, start_line, end_line):
        lines = self.lines_for(path)
        if lines is None:
            return None
        relevant = [hits for line, hits in lines.items() if start_line <= line <= end_line]
        if not relevant:
            return None
        return sum(1 for hits in relevant if hits > 0) / len(relevant)


def load(path):
    if os.path.isdir(path):
        data = CoverageData()
        for root, _, names in os.walk(path):
            for name in names:
                if name.endswith((".info", ".gcov", ".json", ".xml")):
                    data.merge(load(os.path.join(root, name)))
        return data
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    return parse(text, path)


def parse(text, path=""):
    head = text.lstrip()[:200]
    if path.endswith(".gcov") or head.startswith("        -:    0:Source:") or "0:Source:" in head:
        return CoverageData(_parse_gcov(text))
    if head.startswith("{"):
        return CoverageData(_parse_llvm_json(text))
    if head.startswith("<"):
        return CoverageData(_parse_cobertura(text))
    if head.startswith(("TN:", "SF:")) or "\nSF:" in text:
        return CoverageData(_parse_lcov(text))
    raise ValueError(f"unrecognised coverage format: {path or 'input'}")


def _parse_lcov(text):
    files = {}
    current = None
    for line in text.splitlines():
        if line.startswith("SF:"):
            current = files.setdefault(_norm(line[3:].strip()), {})
        elif line.startswith("DA:") and current is not None:
            number, _, hits = line[3:].partition(",")
            hits = hits.split(",")[0]
            current[int(number)] = current.get(int(number), 0) + int(hits)
        elif line.startswith("end_of_record"):
            current = None
    return files


def _parse_llvm_json(text):
    document = json.loads(text)
    files = {}
    for export in document.get("data", []):
        for entry in export.get("files", []):
            hits = files.setdefault(_norm(entry["filename"]), {})
            _segments_to_lines(entry.get("segments", []), hits)
    return files


def _segments_to_lines(segments, hits):
    if not segments:
        return
    by_line = {}
    for segment in segments:
        by_line.setdefault(segment[0], []).append(segment)
    wrapped = None
    for line in range(segments[0][0], segments[-1][0] + 1):
        on_line = by_line.get(line, ())
        count = _line_count(on_line, wrapped)
        if count is not None:
            hits[line] = max(hits.get(line, 0), count)
        if on_line:
            wrapped = on_line[-1]


def _line_count(on_line, wrapped):
    entries = [segment for segment in on_line if _starts_region(segment)]
    skipped = bool(on_line) and not _has_count(on_line[0]) and _is_entry(on_line[0])
    if skipped or not (entries or (wrapped is not None and _has_count(wrapped))):
        return None
    count = wrapped[2] if wrapped is not None and _has_count(wrapped) else 0
    for segment in entries:
        count = max(count, segment[2])
    return count


def _starts_region(segment):
    return _has_count(segment) and _is_entry(segment) and not _is_gap(segment)


def _has_count(segment):
    return bool(segment[3]) if len(segment) > 3 else True


def _is_entry(segment):
    return bool(segment[4]) if len(segment) > 4 else False


def _is_gap(segment):
    return bool(segment[5]) if len(segment) > 5 else False


def _parse_cobertura(text):
    files = {}
    root = ElementTree.fromstring(text)
    sources = [element.text or "" for element in root.findall("./sources/source")]
    for element in root.iter("class"):
        filename = element.get("filename")
        if not filename:
            continue
        hits = files.setdefault(_norm(_resolve(filename, sources)), {})
        for line in element.iter("line"):
            number = int(line.get("number", 0))
            hits[number] = max(hits.get(number, 0), int(line.get("hits", 0)))
    return files


def _parse_gcov(text):
    files = {}
    hits = None
    for line in text.splitlines():
        match = GCOV_LINE.match(line)
        if not match:
            continue
        count, number = match.group(1).strip(), int(match.group(2))
        if number == 0:
            _, _, value = line.partition(":Source:")
            if value:
                hits = files.setdefault(_norm(value.strip()), {})
            continue
        if hits is None or count == "-":
            continue
        hits[number] = 0 if count.startswith(("#", "=")) else int(count.rstrip("*"))
    return files


def _resolve(filename, sources):
    if os.path.isabs(filename):
        return filename
    for source in sources:
        candidate = os.path.join(source.strip(), filename)
        if os.path.exists(candidate):
            return candidate
    return filename


def _norm(path):
    return os.path.realpath(path)


def _key(path):
    return os.path.basename(path)


def _common_suffix(left, right):
    left_parts = left.split(os.sep)[::-1]
    right_parts = right.split(os.sep)[::-1]
    count = 0
    for a, b in zip(left_parts, right_parts):
        if a != b:
            break
        count += 1
    return count
