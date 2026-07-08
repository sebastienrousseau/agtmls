# Language profile: TypeScript

You are working in a TypeScript project. The universal rules above
still apply; this section refines them for TypeScript idioms.

## Types

- `tsconfig.json` runs `"strict": true` (and, if not implied,
  `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`). A
  project that can't compile clean under strict mode is not
  TypeScript, it's JavaScript with extra syntax.
- `unknown` over `any` at every boundary. `any` is banned outside a
  narrow, commented escape hatch — it doesn't just widen one value,
  it disables checking for everything downstream that touches it.
- Model variants as discriminated unions (a shared literal tag
  field), not a loose interface with optional fields standing in
  for cases. Switch over the tag exhaustively; the default branch
  assigns the remaining value to a `never`-typed variable so an
  unhandled case is a compile error, not a runtime surprise.
- `readonly` on fields and array types by default; `as const` on
  literal objects/tuples you don't intend to mutate. Mutability is
  an opt-in, not the baseline.
- Generics carry constraints (`<T extends Base>`) — an unconstrained
  `<T>` that only ever forwards a value is usually a sign the
  function should just take `unknown` or be non-generic.
- No `!` non-null assertions to silence the checker on real data.
  If the compiler can't prove non-null, prove it with a narrowing
  check, a default, or an explicit `throw` — the assertion just
  moves the crash to a worse place.

## Runtime boundary

- Types are erased at compile time. Nothing about `interface User`
  or `as User` exists at runtime — a type annotation is a promise
  to the compiler, not a check on the value.
- Every external or untrusted input (HTTP body, query string, env
  var, file read, third-party API response, `JSON.parse` output)
  gets validated at the boundary with a runtime schema (`zod` or
  equivalent) that produces the typed value, not a cast that
  merely asserts one.
- `JSON.parse(x) as T` validates nothing — it is a type-level lie
  the compiler will believe and the runtime will not enforce.
  Parse into `unknown`, then decode through a schema.
- Once data has crossed the boundary through a schema parse, treat
  it as trusted for the rest of the call graph — don't re-validate
  internally on every function; validate once, type strictly after.

## Error handling

- Two shapes, pick per call site: `throw`/`try-catch` with an
  `Error` subclass for exceptional, unrecoverable failures, or a
  discriminated-union `Result<T, E>` for expected failures the
  caller is meant to branch on (validation, not-found, business
  rules). Don't build a third ad-hoc convention.
- Never `throw` a non-`Error` (no `throw "string"`, no `throw
  { code }`) — `catch` gets `unknown` in strict mode precisely
  because non-`Error` throws are legal JS; don't add to the mess.
- No empty `catch {}`. Handle it, rethrow it with context, or log
  and return an explicit failure value — silent swallowing hides
  the next bug.
- Every `Promise` is awaited, returned, or explicitly voided
  (`void somePromise()` with a comment on why fire-and-forget is
  safe here). An unhandled rejection is a production incident
  waiting to happen.

## Idioms

- `async`/`await` over raw `.then()` chains; reserve `Promise.all`
  / `Promise.allSettled` for genuine concurrency, not as a way to
  avoid writing sequential `await`s.
- ES modules only (`import`/`export`); no `require` in new code.
- Immutability by default: prefer `const`, spread/`map`/`filter`
  over in-place mutation, new objects over field reassignment.
  Mutate deliberately, not by default.
- Array methods (`map`, `filter`, `reduce`, `find`) over manual
  `for` loops when the resulting expression reads clearer — not as
  a purity contest when a loop is genuinely more readable.
- Prefer plain functions and types/interfaces over classes. Reach
  for a `class` when you need real state plus identity (a cache, a
  connection, a stateful service) — not as the default container
  for related functions.

## Testing discipline

- `vitest` (or `jest` on an existing codebase — don't migrate a
  working suite mid-feature). Colocate `*.test.ts` next to source
  or under a mirrored `tests/` tree; pick one convention per repo.
- `fast-check` for combinatorial input spaces (parser input,
  numeric boundaries, string encoding) where example-based tests
  can't cover the space.
- Regression discipline matches the universal rule: a bug fix ships
  with a test that fails on the pre-fix tree, in the same commit.
- Type-level tests (`expectTypeOf`, `tsd`, or a `// @ts-expect-error`
  probe) where the contract being protected is the type itself —
  e.g. a generic helper's inferred return type — not every function.

## Build and dependencies

- `pnpm` as the default package manager; `npm` is acceptable on an
  existing project that already committed to it. Don't mix
  lockfiles.
- `tsc --noEmit` is the typecheck gate, run separately from
  whatever bundler/transpiler (esbuild, swc, tsup) produces the
  actual output — a fast transpiler does not type-check.
- Pin `target` and `lib` in `tsconfig.json` explicitly; don't let
  them silently drift with a `@types/node` bump.
- Library output is ESM (`"type": "module"`, `.js`/`.d.ts`
  emitted); ship a CJS build only when a stated consumer needs it.

## Toolchain

CI already enforces `prettier --check`, `eslint`, and `tsc --noEmit`;
run them before pushing and pass the gate rather than re-describing
it. The conventions the linter can't express for you:

- An `eslint-disable-next-line <rule>` gets a comment justifying it
  and is scoped to the one line — never a file-level `/* eslint-disable */`
  or a blanket rule turned off in config to silence one call site.
- `@ts-expect-error` (never `@ts-ignore`) with a comment when a
  narrow, understood type gap must be suppressed — `@ts-ignore`
  suppresses silently even after the error stops applying.
- Barrel files (`index.ts` re-exporting a directory) are fine for
  a public package surface; don't let one grow into a re-export of
  the whole internal module graph.

## What NOT to do

- No `any` — including the implicit kind (`noImplicitAny` stays
  on). Type the boundary or use `unknown` and narrow.
- No `!` non-null assertions on real, potentially-absent data.
- No trusting `JSON.parse(x) as T`, `req.body as T`, or any other
  cast standing in for validation of untrusted input.
- No `enum` where a union of string literals is clearer — literal
  unions are structurally typed, tree-shake cleanly, and don't
  carry `enum`'s reverse-mapping surprises.
- No default exports from library packages — named exports keep
  renames, refactors, and auto-import tooling honest. A default
  export is acceptable for a single-component app entry point, not
  for a package other code imports.
