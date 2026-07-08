# Language profile: Python

You are working in a Python project. The universal rules above still
apply; this section refines them for Python idioms.

## Error handling

- Raise, don't return sentinels. A function returning `None`, `-1`,
  or `False` to signal failure forces every caller to remember to
  check — and most won't. Raise a specific exception instead.
- Define a small exception hierarchy per package: a base
  `YourPackageError(Exception)` with narrow subclasses
  (`ValidationError`, `NotFoundError`, ...). Callers catch the base
  for "anything from this package" or a subclass for one failure
  mode.
- EAFP over LBYL: `try`/`except` around the operation rather than a
  pre-flight `hasattr` / `in` check, when the check-then-act window
  is a real race (filesystem, network, shared dict) or the
  exceptional path is rare. `dict.get(key, default)` is still right
  for a plain lookup — EAFP avoids a redundant check, not `except`
  itself.
- Never write a bare `except:` — it catches `SystemExit` and
  `KeyboardInterrupt` too. Catch the specific type(s); a genuine
  catch-all at a process boundary catches `Exception` and re-raises
  or logs with `logging.exception` so the traceback survives.
- `raise NewError(...) from original` when translating one exception
  into another; `from None` only when the original is truly noise.
- Reserve `return` for the normal-path result. A function whose
  contract is "give me the thing or tell me why not" is two
  functions (`get` raising, `get_or_none` returning `Optional[T]`),
  not one signature doing both.

## Types and idioms

- Type hints on every public function signature and class attribute;
  run `mypy --strict` (or `pyright --strict`) in CI, not just
  locally.
- `dataclasses` (`@dataclass(frozen=True, slots=True)` by default)
  for internal structured data; `pydantic` `BaseModel` at boundaries
  parsing untrusted input (HTTP bodies, config files, CLI args) that
  need validation, coercion, and a JSON schema for free. Don't reach
  for pydantic where a plain dataclass would do.
- Context managers (`with`) for anything with a lifecycle — files,
  locks, DB transactions, temp state. Write `__enter__`/`__exit__`
  or `@contextmanager` rather than a manual `try/finally: close()`
  at every call site.
- Comprehensions and generator expressions over `map`/`filter` and
  manual accumulator loops, but stop nesting past two levels — an
  unreadable comprehension is worse than the loop it replaced.
- `pathlib.Path` over `os.path` string joins — `/` composition,
  `.exists()`, `.read_text()` are more legible and less
  platform-fragile than `os.path.join` + `open()`.
- f-strings for interpolation; `.format()` for templates built from
  a runtime variable; `%` for logging call sites, where the
  `logging` module lazy-formats `%s` args in a way f-strings can't.
- `Enum` (or `StrEnum` on 3.11+) for a closed set of named
  constants; `Literal["a", "b", "c"]` for a closed set of strings
  crossing a function boundary without needing enum identity. Don't
  pass bare strings where either fits — that's how `if mode ==
  "wrte":` typos survive to production.

## Typing discipline

- The `mypy --strict` pass is the closest thing Python has to the
  typecheck a compiled language gets for free at every build. A
  change landing without it passing has quietly given up a
  guarantee the codebase relies on — treat a red mypy run with the
  same weight as a red test suite, not a linter nag.
- Avoid `Any`. It doesn't mean "unknown type," it means "opt this
  value out of type checking," and the coverage loss silently
  spreads to everything it touches. `object` plus a narrowing
  `isinstance` check is the honest alternative when the real type
  is genuinely unknown.
- Prefer `Protocol` for structural typing — "anything with a
  `.read()` method" — over forcing unrelated classes into a shared
  ABC to satisfy a type signature. Nominal inheritance is for
  genuine is-a relationships; `Protocol` is duck typing with a
  checker watching.
- `TypedDict` for dict-shaped data that must stay a plain dict (JSON
  payloads consumed as `dict[str, Any]`); a `dataclass` once the
  value has behavior or invariants beyond storage.
- A `# type: ignore[specific-code]` is a documented exception, not a
  silencer — no bare `# type: ignore`. If mypy is wrong, say why; if
  mypy is right and the fix is out of scope, say that and link the
  follow-up.

## Testing discipline

- `pytest`, not `unittest`, for new suites — fixtures over
  `setUp`/`tearDown`, plain `assert` over `self.assertEqual`.
- `@pytest.mark.parametrize` for the same assertion across many
  inputs instead of a copy-pasted test per case — one broken input
  produces one failing test id, not a hunt through a loop.
- Fixtures scoped (`function`, `module`, `session`) to the narrowest
  lifetime that's actually correct — a `session`-scoped fixture
  mutated by one test silently poisons the rest of the run.
- `hypothesis` for combinatorial or boundary-heavy input spaces
  (parsing, serialization round-trips, numeric edge cases) where
  hand-enumerated examples would miss the bug.
- A bug fix ships in the same commit as a test that fails on the
  pre-fix tree and passes after. A regression test added without
  first confirming it fails against the old code is not evidence.
- Mock at the boundary (network client, filesystem, clock), not the
  function under test — mocking the thing you're supposed to verify
  passes regardless of whether the code works.

## Packaging and environment

- `pyproject.toml` as the single source of truth (`[project]` +
  `[build-system]`) — no parallel `setup.py`/`setup.cfg` unless a
  legacy build step genuinely requires it.
- `uv` (or `poetry`) for dependency resolution and lockfiles; commit
  the lockfile (`uv.lock` / `poetry.lock`) so CI and every
  contributor resolve the same graph.
- Pin direct dependencies to a compatible range (`>=x.y,<x+1`); let
  the lockfile pin the exact resolved versions. Unpinned deps mean
  the same source produces a different build tomorrow.
- `src/` layout (`src/yourpkg/__init__.py`) over a flat package at
  repo root — it forces the test suite to import the installed
  package instead of the working directory, catching packaging bugs
  before they ship.
- Declare `requires-python = ">=3.x"` explicitly. Treat raising the
  floor like a Rust MSRV bump: a breaking change with a version bump
  and a changelog line, not a silent edit.

## Toolchain

CI already enforces `ruff format --check`, `ruff check`, and `mypy
--strict`; run them before pushing and pass the gate rather than
re-describing it. The conventions the linter can't express for you:

- `ruff format` (or `black`) clean before every push — don't
  hand-format and drift from the tool's opinion.
- A `# noqa: CODE` or `# type: ignore[code]` carries the specific
  code and a one-line reason inline — never a blanket `# noqa` or
  `# type: ignore` that silences everything on the line, including
  the next real bug.
- `__all__` declared where a module wants an explicit public surface
  for tooling and readers.

## What NOT to do

- No Java-style getter/setter boilerplate (`get_x()`/`set_x()`). Use
  a plain attribute, and reach for `@property` only when access
  needs actual logic (validation, laziness, derived value) — not
  preemptively on every field.
- No Go-style `(result, err)` tuple returns smuggled in as Python's
  error model. Python has exceptions; use them. A function returning
  `tuple[T | None, Exception | None]` makes every call site redo the
  `if err is not None` dance the language doesn't need.
- No mutable default arguments (`def f(items=[]):`) — the list is
  created once at function-definition time and shared across every
  call. Default to `None` and assign the mutable value in the body.
- No wildcard imports (`from module import *`) outside a
  deliberately curated `__init__.py` re-export — they make it
  impossible to tell where a name came from by reading the file.
- No `except Exception: pass`. A silently swallowed exception is a
  bug report nobody will ever file — at minimum log it; usually let
  it propagate.
- No god classes reimplementing what a dataclass, a `NamedTuple`, or
  a plain function already covers. Reach for a class when behavior
  is tied to state, not as the default container for data.
