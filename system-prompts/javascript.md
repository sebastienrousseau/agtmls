# Language profile: JavaScript

You are working in a plain JavaScript project (no TypeScript). The
universal rules above still apply; this section refines them for
modern JS idioms.

## Modern baseline

- ES modules (`import`/`export`) — no `require`/`module.exports` in
  new code unless the runtime forces CommonJS.
- `const` by default, `let` when reassignment is genuine. Never
  `var` — its function-scoping and hoisting are a bug generator.
- `===`/`!==` always. `==`/`!=` only when deliberately matching
  `null`/`undefined` together, and say so in a comment.
- `async`/`await` over `.then()` chains and callback pyramids. A
  callback-shaped API gets wrapped at the boundary, not propagated.
- Optional chaining (`?.`) and nullish coalescing (`??`) over manual
  `&&` guard chains and `|| defaultValue` (which misfires on `0`,
  `''`, `false`).
- Array methods (`map`/`filter`/`reduce`/`find`/`some`/`every`) over
  manual `for` loops when the resulting expression is clearer, not
  shorter for its own sake — a `reduce` that needs a comment to
  explain itself should be a `for` loop instead.

## Correctness without static types

JavaScript has no compile-time type checker. The test suite and
runtime validation are the *only* correctness nets — treat them
accordingly:

- Validate external input explicitly at every boundary (function
  arguments from untrusted callers, HTTP bodies, CLI args, file
  contents, env vars): hand-rolled guards (`typeof`, `Array.isArray`,
  range checks) or a schema library (`zod`, `ajv`) for anything
  shaped like a document.
- Never assume a JSON payload matches the shape you expect — parse,
  then validate, then use. `JSON.parse` alone is not validation.
- If the project can adopt TypeScript, say so and note it as the
  stronger option. For projects staying in plain JS, add JSDoc
  `@type`/`@param`/`@returns` annotations on public functions and run
  `tsc --checkJs --allowJs --noEmit` in CI — free type-checking
  without a build step or a `.ts` file in sight.
- Assertions (`assert`, or a small `invariant()` helper) at internal
  boundaries where "this cannot happen" is actually load-bearing —
  fail loudly in dev/test rather than let a `undefined` silently
  propagate three call frames deep.

## Error handling

- `throw new Error(...)` (or a subclass) — never `throw` a string,
  plain object, or other non-`Error` value. Only `Error` instances
  carry a stack trace and compose with `instanceof` checks.
- Define domain error subclasses (`class ValidationError extends
  Error`) when callers need to distinguish failure modes; attach
  structured detail as properties, not by parsing `error.message`.
- Every `async` function's rejection path is either awaited inside a
  `try`/`catch` or explicitly propagated to a caller that will
  handle it. No floating promises — an un-awaited `async` call whose
  result is discarded is a silent failure waiting to happen.
- No unhandled rejections: wire a top-level `process.on
  ('unhandledRejection', …)` (Node) or equivalent as a last-resort
  net, but treat it as a bug report, not a control-flow mechanism.
- Fail loudly, not silently: don't swallow a `catch` block into a
  no-op or a `console.log` unless the call site documents why the
  error is genuinely recoverable there.

## Idioms

- Immutability by default: don't mutate function arguments or
  shared state; return new arrays/objects (`[...arr, x]`,
  `{ ...obj, key: value }`) instead of `push`/direct assignment on
  something the caller still holds a reference to.
- Pure functions where possible — same input, same output, no
  hidden reliance on module-level mutable state. Isolate the
  unavoidable side effects (I/O, `Date.now()`, `Math.random()`) at
  the edges.
- `Map`/`Set` over a plain object used as a hash map when keys
  aren't strings, when insertion order matters semantically, or when
  keys/values need to be added and removed at runtime — an object
  carries prototype-chain surprises (`__proto__`, inherited methods)
  that a `Map` does not.
- Never use floating-point (`Number`) for money. Use integer minor
  units (cents) or `BigInt`/a decimal library when a domain needs
  genuine fractional precision.
- Destructuring and default parameters over manual `arguments`
  indexing or `options.foo === undefined ? x : options.foo`.

## Testing discipline

- `vitest` or Node's built-in `node --test` — pick one per project
  and stay consistent; don't mix runners.
- `fast-check` for property-based tests over combinatorial input
  spaces (string escaping, numeric boundaries, object shape
  variations).
- Regression test discipline: a bug fix ships a test that FAILS on
  the pre-fix tree, landed in the same commit as the fix.
- Mock at the boundary (network, filesystem, clock), not the unit
  under test — a test that mocks the function it's testing proves
  nothing.
- Async tests always `await` (or `return`) the assertion; a dangling
  promise in a test body lets failures pass silently.

## Dependencies and build

- `pnpm` (or `npm` if the project already standardized on it) with a
  committed lockfile — never install without one.
- Pin versions for anything security-sensitive; avoid unpinned `^`/
  `~` ranges on dependencies that touch untrusted input.
- Minimal dependency footprint: a one-function need doesn't justify
  a package. Justify every addition in the PR — what it does that
  hand-rolling wouldn't, and its maintenance/supply-chain posture.
- ESM (`"type": "module"` in `package.json`) for new projects; a
  `.cjs` escape hatch only where a dependency forces it.

## Toolchain

CI already enforces `prettier --check` and `eslint`; run them before
pushing and pass the gate rather than re-describing it. The
conventions the linter can't express for you:

- An `eslint-disable-next-line <rule>` is scoped to one line, names
  the specific rule, and carries a comment explaining why — never a
  blanket `/* eslint-disable */` at file scope.
- `prettier` output is not up for debate in review; if the formatting
  looks wrong, fix the config, don't hand-format around it.
- Keep `package.json` `engines.node` accurate — it's the runtime
  floor, and bumping it is a breaking change worth calling out.

## What NOT to do

- No `var`.
- No `==`/`!=` (outside the documented `null`/`undefined` exception).
- No callback pyramids — wrap callback APIs in a `Promise` at the
  boundary instead of nesting.
- No mutating shared state (function arguments, module-level
  objects/arrays) in place.
- No `eval()` or `new Function(...)` on anything derived from input.
- No floating-point arithmetic for money.
- No `throw`ing strings, plain objects, or other non-`Error` values.
