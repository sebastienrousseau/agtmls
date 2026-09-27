# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Per-function complexity: cyclomatic, cognitive, Halstead difficulty, lines.

The portfolio's hygiene rule (~/Code/AGENTS.md section 0) holds every
function to four ceilings. This measures them with the standard library
alone, so the check runs in the offline gate like every other script here
(AGENTS.md invariant 2), rather than needing radon or complexipy installed.

- **Cyclomatic** (McCabe, counted as radon does): 1, plus one per `if`,
  `elif`, loop, `except`, `case`, `assert`, conditional expression,
  comprehension `for` and `if`, `else` on a loop or `try`, and each extra
  operand of `and`/`or`.
- **Cognitive** (SonarSource, counted as complexipy does): one per break in
  linear flow (`if`, `elif`, `else`, loop, `except`, `match`, conditional
  expression, comprehension `for` and `if`, a run of `and`/`or`), plus the
  current nesting depth for the structures that nest. A nested function's
  structures count toward the function around it. Unlike complexipy, a
  `lambda`'s are counted too, one level deeper: a ceiling errs strict.
- **Halstead difficulty**: (distinct operators / 2) x (operands / distinct
  operands), over the function's tokens.
- **Lines**: source lines of the function, without blank lines, comments
  or its docstring.

For cyclomatic, Halstead and lines, a nested function or class is measured
on its own and left out of the function around it; a `lambda` is part of
the function it is written in, as radon counts it.
"""

from __future__ import annotations

import ast
import io
import keyword
import tokenize
from dataclasses import dataclass
from pathlib import Path

CEILINGS = {"cyclomatic": 10, "cognitive": 15, "halstead": 30.0, "lines": 60}
FILE_LINES = 500

_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)


@dataclass(frozen=True)
class Measure:
    """One function's metrics; `name` is its dotted path inside the file."""

    name: str
    line: int
    cyclomatic: int
    cognitive: int
    halstead: float
    lines: int

    def over(self) -> dict[str, float]:
        """The metrics above their ceiling, by name."""
        return {
            metric: getattr(self, metric)
            for metric, ceiling in CEILINGS.items()
            if getattr(self, metric) > ceiling
        }


def _own_nodes(function: ast.AST):
    """Every node of `function`'s body, not descending into nested scopes."""
    stack = list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _NESTED):
            stack.extend(ast.iter_child_nodes(node))


def cyclomatic(function: ast.AST) -> int:
    score = 1
    for node in _own_nodes(function):
        if isinstance(node, (ast.If, ast.IfExp, ast.ExceptHandler, ast.Assert)):
            score += 1
        elif isinstance(node, (*_LOOPS, ast.Try)):
            # A loop is a decision; an `else` on a loop or a `try` is another.
            score += (0 if isinstance(node, ast.Try) else 1) + bool(node.orelse)
        elif isinstance(node, ast.match_case):
            score += 1
        elif isinstance(node, ast.comprehension):
            score += 1 + len(node.ifs)
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
    return score


def cognitive(function: ast.AST) -> int:
    return sum(_cognitive(child, 0) for child in ast.iter_child_nodes(function))


def _block(nodes, nesting: int) -> int:
    return sum(_cognitive(node, nesting) for node in nodes)


def _else(orelse: list, nesting: int) -> int:
    """An `else` on a loop or a `try`: one, plus its body a level deeper."""
    return 1 + _block(orelse, nesting + 1) if orelse else 0


def _loop(node, nesting: int) -> int:
    header = node.test if isinstance(node, ast.While) else node.iter
    return 1 + nesting + _cognitive(header, nesting) + _block(node.body, nesting + 1) + _else(node.orelse, nesting)


def _try(node, nesting: int) -> int:
    handlers = sum(1 + nesting + _block(handler.body, nesting + 1) for handler in node.handlers)
    return _block(node.body, nesting) + handlers + _else(node.orelse, nesting) + _block(node.finalbody, nesting)


def _match(node: ast.Match, nesting: int) -> int:
    cases = sum(_block(case.body, nesting + 1) for case in node.cases)
    return 1 + nesting + _cognitive(node.subject, nesting) + cases


def _if_expression(node: ast.IfExp, nesting: int) -> int:
    return 1 + nesting + _block((node.test, node.body, node.orelse), nesting + 1)


def _comprehension(node: ast.comprehension, nesting: int) -> int:
    return 1 + nesting + len(node.ifs) + _block(ast.iter_child_nodes(node), nesting)


_HANDLERS = {
    ast.ClassDef: lambda node, nesting: 0,
    # A nested function is folded into the one around it, as complexipy counts it.
    ast.FunctionDef: lambda node, nesting: _block(node.body, nesting),
    ast.AsyncFunctionDef: lambda node, nesting: _block(node.body, nesting),
    ast.Lambda: lambda node, nesting: _cognitive(node.body, nesting + 1),
    ast.If: lambda node, nesting: 1 + nesting + _cognitive_if(node, nesting),
    ast.For: _loop,
    ast.AsyncFor: _loop,
    ast.While: _loop,
    ast.Try: _try,
    ast.Match: _match,
    ast.IfExp: _if_expression,
    ast.BoolOp: lambda node, nesting: 1 + _block(node.values, nesting),
    ast.comprehension: _comprehension,
}
# `except*` (Python 3.11+); on 3.10 this re-registers ast.Try, harmlessly.
_HANDLERS[getattr(ast, "TryStar", ast.Try)] = _try


def _cognitive(node: ast.AST, nesting: int) -> int:
    handler = _HANDLERS.get(type(node))
    if handler is not None:
        return handler(node, nesting)
    return _block(ast.iter_child_nodes(node), nesting)


def _cognitive_if(node: ast.If, nesting: int) -> int:
    """An `if`'s test and bodies; an `elif` chain adds one per branch, not
    one per level, and `else` adds one."""
    score = _cognitive(node.test, nesting) + _block(node.body, nesting + 1)
    orelse = node.orelse
    while len(orelse) == 1 and isinstance(orelse[0], ast.If):
        branch = orelse[0]
        score += 1 + _cognitive(branch.test, nesting) + _block(branch.body, nesting + 1)
        orelse = branch.orelse
    if orelse:
        score += 1 + _block(orelse, nesting + 1)
    return score


def _nested_spans(function: ast.AST) -> list[tuple[int, int]]:
    return [
        (node.lineno, node.end_lineno)
        for node in _own_nodes(function)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


def _docstring_span(function: ast.AST) -> tuple[int, int] | None:
    body = getattr(function, "body", [])
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        return body[0].lineno, body[0].end_lineno
    return None


def _tokens(source: str, function: ast.AST):
    """The function's own tokens: nested scopes and its docstring left out."""
    skip = _nested_spans(function)
    doc = _docstring_span(function)
    if doc:
        skip.append(doc)
    lines = source.splitlines(keepends=True)[function.lineno - 1:function.end_lineno]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO("".join(lines)).readline))
    except (tokenize.TokenError, IndentationError):
        return
    for token in _whole_strings(tokens, lines):
        line = token.start[0] + function.lineno - 1
        if not any(start <= line <= end for start, end in skip):
            yield token, line


_SKIP = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}


def _span(lines: list[str], start: tuple[int, int], end: tuple[int, int]) -> str:
    """The source text between two token positions (1-based rows)."""
    (r1, c1), (r2, c2) = start, end
    if r1 == r2:
        return lines[r1 - 1][c1:c2]
    return lines[r1 - 1][c1:] + "".join(lines[r1:r2 - 1]) + lines[r2 - 1][:c2]


def _whole_strings(tokens, lines: list[str]):
    """Tokens with each f-string or t-string as one STRING token of its text.

    Python 3.12 splits an f-string into its parts (FSTRING_START, the
    expressions inside, FSTRING_END); earlier versions return it whole. Left
    alone, the same function would score differently on each Python in the
    CI matrix, and the baseline would move with the interpreter.
    """
    depth = 0
    for token in tokens:
        name = tokenize.tok_name.get(token.type, "")
        if name.endswith("STRING_START"):
            if depth == 0:
                opened = token.start
            depth += 1
        elif name.endswith("STRING_END"):
            depth -= 1
            if depth == 0:
                yield tokenize.TokenInfo(tokenize.STRING, _span(lines, opened, token.end), opened, token.end, "")
        elif depth == 0:
            yield token


def halstead_and_lines(source: str, function: ast.AST) -> tuple[float, int]:
    operators: list[str] = []
    operands: list[str] = []
    code_lines: set[int] = set()
    for token, line in _tokens(source, function):
        kind, text = token.type, token.string
        if kind in _SKIP:
            continue
        code_lines.add(line)
        if kind == tokenize.OP or (kind == tokenize.NAME and keyword.iskeyword(text)):
            operators.append(text)
        else:  # a name, number or (whole) string
            operands.append(text)
    distinct_operands = len(set(operands))
    difficulty = (len(set(operators)) / 2) * (len(operands) / distinct_operands) if distinct_operands else 0.0
    return round(difficulty, 1), len(code_lines)


def measure_source(source: str) -> list[Measure]:
    """Every function and method in `source`, outermost first."""
    tree = ast.parse(source)
    found: list[Measure] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                halstead, lines = halstead_and_lines(source, child)
                found.append(Measure(name, child.lineno, cyclomatic(child), cognitive(child), halstead, lines))
                walk(child, name + ".")
            elif isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            else:
                walk(child, prefix)

    walk(tree, "")
    return found


def measure_file(path: Path) -> list[Measure]:
    return measure_source(path.read_text(encoding="utf-8"))


def file_lines(path: Path) -> int:
    """A file's non-blank lines."""
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
