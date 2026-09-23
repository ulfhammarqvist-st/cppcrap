from dataclasses import dataclass

from .lexer import tokenize

SCOPE_KEYWORDS = {"namespace", "class", "struct", "union", "enum"}
SCOPE_SKIP = {"class", "struct", "final", "alignas"}
DECISION_KEYWORDS = {"if", "for", "while", "case", "catch"}
DECISION_OPERATORS = {"&&", "||", "?"}
NOT_A_CALLEE = {
    "if", "for", "while", "switch", "catch", "return", "sizeof", "alignof",
    "decltype", "noexcept", "static_assert", "throw", "new", "delete", "typeid",
    "case", "do", "else", "using", "and", "or", "not", "requires", "constexpr",
    "template", "typename", "explicit", "else", "co_await", "co_return", "co_yield",
    "__attribute__", "assert",
}
BODY_QUALIFIERS = {
    "const", "volatile", "noexcept", "override", "final", "mutable", "constexpr",
    "consteval", "constinit", "requires", "throw", "try", "decltype", "auto",
}
NAME_LINK = {"::", "~"}
MAX_SIGNATURE_TAIL = 200


@dataclass
class Function:
    name: str
    path: str
    start_line: int
    end_line: int
    complexity: int

    @property
    def lines(self):
        return self.end_line - self.start_line + 1


def parse_source(path, text):
    return _Parser(tokenize(text), path).run()


def parse_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return parse_source(path, handle.read())


class _Parser:
    def __init__(self, tokens, path):
        self.tokens = tokens
        self.path = path
        self.n = len(tokens)

    def run(self):
        functions = []
        scopes = []
        decl = []
        i = 0
        while i < self.n:
            token = self.tokens[i]
            if token.kind == "preproc":
                i += 1
                continue
            if token.kind == "op":
                if token.value == "{":
                    scopes.append(_scope_name(decl))
                    decl = []
                    i += 1
                    continue
                if token.value == "}":
                    if scopes:
                        scopes.pop()
                    decl = []
                    i += 1
                    continue
                if token.value == ";":
                    decl = []
                    i += 1
                    continue
                if token.value == "(":
                    function, next_index = self._try_function(decl, i, scopes)
                    if function is not None:
                        functions.append(function)
                        decl = []
                    i = next_index
                    continue
            decl.append(token)
            i += 1
        return functions

    def _try_function(self, decl, paren_index, scopes):
        close = self._skip_balanced(paren_index, "(", ")")
        name = _declarator_name(decl)
        if name is None:
            return None, close
        body = self._find_body(close)
        if body is None:
            return None, close
        end, end_line, complexity = self._scan_body(body)
        start_line = decl[-1].line if decl else self.tokens[paren_index].line
        return Function(
            name=_qualify(scopes, name),
            path=self.path,
            start_line=start_line,
            end_line=end_line,
            complexity=complexity,
        ), end + 1

    def _find_body(self, index):
        i = index
        limit = min(self.n, index + MAX_SIGNATURE_TAIL)
        while i < limit:
            token = self.tokens[i]
            if token.kind == "op":
                if token.value == "{":
                    return i
                if token.value in (";", "=", "}", ")"):
                    return None
                if token.value in ("(", "["):
                    i = self._skip_balanced(i, token.value, ")" if token.value == "(" else "]")
                    continue
                if token.value == ":":
                    return self._find_body_after_init_list(i + 1)
                if token.value == "->":
                    return self._find_body_after_return_type(i + 1)
                i += 1
                continue
            if token.kind == "name" and token.value not in BODY_QUALIFIERS:
                return None
            i += 1
        return None

    def _find_body_after_return_type(self, index):
        i = index
        limit = min(self.n, index + MAX_SIGNATURE_TAIL)
        while i < limit:
            token = self.tokens[i]
            if token.kind == "op":
                if token.value == "{":
                    return i
                if token.value in (";", "=", "}"):
                    return None
                if token.value in ("(", "["):
                    i = self._skip_balanced(i, token.value, ")" if token.value == "(" else "]")
                    continue
            i += 1
        return None

    def _find_body_after_init_list(self, index):
        i = index
        expect_initializer = True
        while i < self.n:
            token = self.tokens[i]
            if expect_initializer:
                if token.kind == "name" or token.value in ("::", "<", ">", ",", "..."):
                    i += 1
                    continue
                if token.value in ("(", "{"):
                    i = self._skip_balanced(i, token.value, ")" if token.value == "(" else "}")
                    expect_initializer = False
                    continue
                return None
            if token.value == ",":
                expect_initializer = True
                i += 1
                continue
            if token.value == "{":
                return i
            return None
        return None

    def _scan_body(self, start):
        complexity = 1
        depth = 0
        i = start
        while i < self.n:
            token = self.tokens[i]
            if token.kind == "op":
                if token.value == "{":
                    depth += 1
                elif token.value == "}":
                    depth -= 1
                    if depth == 0:
                        return i, token.line, complexity
                elif token.value in DECISION_OPERATORS:
                    complexity += 1
            elif token.kind == "name" and token.value in DECISION_KEYWORDS:
                if not (token.value == "if" and self._is_constexpr_if(i)):
                    complexity += 1
            i += 1
        last = self.tokens[-1]
        return self.n - 1, last.line, complexity

    def _is_constexpr_if(self, index):
        """True for `if constexpr`, whose branch the compiler picks -- no runtime path to test."""
        nxt = index + 1
        return (
            nxt < self.n
            and self.tokens[nxt].kind == "name"
            and self.tokens[nxt].value == "constexpr"
        )

    def _skip_balanced(self, index, opener, closer):
        depth = 0
        i = index
        while i < self.n:
            value = self.tokens[i].value
            if self.tokens[i].kind == "op":
                if value == opener:
                    depth += 1
                elif value == closer:
                    depth -= 1
                    if depth == 0:
                        return i + 1
            i += 1
        return self.n


def _scope_name(decl):
    for index, token in enumerate(decl):
        if token.kind == "name" and token.value in SCOPE_KEYWORDS:
            for candidate in decl[index + 1:]:
                if candidate.kind != "name":
                    break
                if candidate.value in SCOPE_SKIP:
                    continue
                return candidate.value
            return "(anonymous)"
    return None


def _declarator_name(decl):
    if not decl:
        return None
    operator_name = _operator_name(decl)
    if operator_name is not None:
        return operator_name
    if decl[-1].kind != "name" or decl[-1].value in NOT_A_CALLEE:
        return None
    parts = [decl[-1].value]
    i = len(decl) - 2
    while i >= 0:
        if decl[i].value == "~":
            parts.insert(0, "~")
            i -= 1
            continue
        if decl[i].value != "::" or i == 0:
            break
        owner = i - 1
        if decl[owner].value == ">":
            owner = _open_angle(decl, owner)
        if owner < 0 or decl[owner].kind != "name":
            break
        parts.insert(0, decl[owner].value + "::")
        i = owner - 1
    if i >= 0 and decl[i].value in (".", "->"):
        return None
    return "".join(parts)


def _open_angle(decl, index):
    depth = 0
    while index >= 0:
        if decl[index].value == ">":
            depth += 1
        elif decl[index].value == "<":
            depth -= 1
            if depth == 0:
                return index - 1
        index -= 1
    return -1


def _operator_name(decl):
    for index in range(len(decl) - 1, -1, -1):
        token = decl[index]
        if token.kind == "name" and token.value == "operator":
            symbol = "".join(part.value for part in decl[index + 1:])
            return "operator" + symbol
        if token.kind != "op" and token.value not in ("new", "delete"):
            return None
    return None


def _qualify(scopes, name):
    prefix = [scope for scope in scopes if scope]
    return "::".join(prefix + [name])
