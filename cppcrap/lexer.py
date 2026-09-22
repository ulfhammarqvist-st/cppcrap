from dataclasses import dataclass

NAME_START = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$")
NAME_CHARS = NAME_START | set("0123456789")
DIGITS = set("0123456789")
RAW_PREFIXES = {"R", "LR", "uR", "UR", "u8R"}
STRING_PREFIXES = {"", "L", "u", "U", "u8"}

OPERATORS = [
    "<<=", ">>=", "->*", "...", "<=>",
    "::", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", ".*",
    "{", "}", "(", ")", "[", "]", ";", ":", ",", ".", "?", "~", "!",
    "+", "-", "*", "/", "%", "&", "|", "^", "<", ">", "=", "#", "@",
]


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int


def tokenize(text):
    tokens = []
    i = 0
    line = 1
    n = len(text)
    at_line_start = True
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            at_line_start = True
            continue
        if c in " \t\r\f\v":
            i += 1
            continue
        if c == "\\" and i + 1 < n and text[i + 1] == "\n":
            i += 2
            line += 1
            continue
        if text.startswith("//", i):
            i, line = _skip_line_comment(text, i, line)
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            line += text.count("\n", i, end)
            i = end
            continue
        if at_line_start and c == "#":
            start_line = line
            i, line, value = _read_directive(text, i, line)
            tokens.append(Token("preproc", value, start_line))
            continue
        at_line_start = False
        if c in NAME_START:
            j = i
            while j < n and text[j] in NAME_CHARS:
                j += 1
            word = text[i:j]
            if word in RAW_PREFIXES and j < n and text[j] == '"':
                start_line = line
                i, line, value = _read_raw_string(text, j, line)
                tokens.append(Token("str", value, start_line))
                continue
            if word in STRING_PREFIXES and j < n and text[j] in "\"'":
                i = j
                continue
            tokens.append(Token("name", word, line))
            i = j
            continue
        if c in DIGITS or (c == "." and i + 1 < n and text[i + 1] in DIGITS):
            start_line = line
            i, line, value = _read_number(text, i, line)
            tokens.append(Token("num", value, start_line))
            continue
        if c == '"' or c == "'":
            start_line = line
            i, line, value = _read_quoted(text, i, line)
            tokens.append(Token("str" if c == '"' else "char", value, start_line))
            continue
        for op in OPERATORS:
            if text.startswith(op, i):
                tokens.append(Token("op", op, line))
                i += len(op)
                break
        else:
            i += 1
    return tokens


def _skip_line_comment(text, i, line):
    n = len(text)
    while i < n:
        if text[i] == "\\" and text.startswith("\n", i + 1):
            i += 2
            line += 1
            continue
        if text[i] == "\n":
            return i, line
        i += 1
    return i, line


def _read_directive(text, i, line):
    n = len(text)
    start = i
    while i < n:
        if text[i] == "\\" and text.startswith("\n", i + 1):
            i += 2
            line += 1
            continue
        if text[i] == "\n":
            break
        i += 1
    return i, line, text[start:i].strip()


def _read_raw_string(text, i, line):
    n = len(text)
    open_paren = text.find("(", i)
    if open_paren < 0:
        return n, line + text.count("\n", i, n), text[i:]
    delim = text[i + 1:open_paren]
    terminator = ")" + delim + '"'
    end = text.find(terminator, open_paren)
    end = n if end < 0 else end + len(terminator)
    return end, line + text.count("\n", i, end), text[i:end]


def _read_quoted(text, i, line):
    quote = text[i]
    n = len(text)
    j = i + 1
    while j < n:
        if text[j] == "\\":
            if text[j + 1:j + 2] == "\n":
                line += 1
            j += 2
            continue
        if text[j] == "\n":
            line += 1
            j += 1
            continue
        if text[j] == quote:
            j += 1
            break
        j += 1
    return j, line, text[i:j]


def _read_number(text, i, line):
    n = len(text)
    j = i
    while j < n:
        c = text[j]
        if c in NAME_CHARS or c == ".":
            if c in "eEpP" and j + 1 < n and text[j + 1] in "+-":
                j += 2
                continue
            j += 1
            continue
        if c == "'" and j + 1 < n and text[j + 1] in NAME_CHARS:
            j += 2
            continue
        break
    return j, line, text[i:j]
