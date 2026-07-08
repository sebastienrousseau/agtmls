# Language profile: Swift

You are working in a Swift project (5.9+, targeting Swift 6 language
mode where the toolchain allows). The universal rules above still
apply; this section refines them for Swift idioms.

## Error handling

- `throws` + `do { try ... } catch` is the native convention for
  synchronous and `async` functions alike — `async throws` composes
  directly with `await`. Reserve `Result<Success, Failure>` for
  completion-handler APIs and other non-`async` callback boundaries
  where a return-typed outcome is the only option.
- Model failures as a dedicated `enum` conforming to `Error` (add
  `LocalizedError` when the message reaches a user). Associated
  values carry the context a caller needs — don't collapse everything
  into a single `.failure(String)` case.
- Never `try!` and never `fatalError()` on recoverable or real-world
  input (parsing, network, disk, user entry). Reserve `fatalError`
  and `preconditionFailure` for genuine invariant violations proved
  by construction — and say so in a comment.
- `try?` is fine for "I only care whether this succeeded," but don't
  use it to silently swallow an error a caller would want to see —
  that's the same smell as an empty `catch {}`.
- Catch specific error cases before a catch-all; a bare `catch` that
  discards the underlying error loses exactly the information a
  debugger needs.

## Types and idioms

- Value types (`struct`, `enum`) by default. Reach for a `class` only
  when you need reference identity, shared mutable state, or
  inheritance from a framework type (e.g. `UIViewController`). Mark
  classes `final` unless they're deliberately designed for
  subclassing.
- `enum` with associated values for closed sets of variants, paired
  with an exhaustive `switch` (no catch-all `default` that would
  silently swallow a new case added later). If the set is genuinely
  open-ended, that's a signal for a protocol, not an enum.
- Optionals over sentinel values (`-1`, `""`, magic strings) for
  "value may be absent." `guard let ... else { return }` for early
  exit, `if let` for narrow scoping, `??` for defaults. Avoid `!` on
  data that came from outside the process — parsing, I/O, user input.
- Protocol-oriented design: protocols plus extensions (default
  implementations) over deep class hierarchies. Compose behavior from
  small protocols rather than inheriting it from a shared base class.
- `Codable` for serialization; custom `CodingKeys` when the wire
  format's naming doesn't match Swift's, custom
  `init(from:)`/`encode(to:)` only when the shape genuinely diverges.
- Access control is a design decision, not an afterthought — default
  to `internal`, promote to `public` deliberately (see Packaging).

## Concurrency

- `async`/`await` with structured concurrency as the default shape:
  `async let` for a fixed, known set of parallel children, `TaskGroup`
  / `withThrowingTaskGroup` for dynamic fan-out. Both guarantee the
  parent doesn't return before its children finish or are cancelled.
- Actors for shared mutable state — an `actor` replaces hand-rolled
  locks, `DispatchSemaphore`, or `NSLock` around mutable data. Don't
  reach for manual synchronization when an actor already gives you
  data-race safety.
- `@MainActor` on anything that touches UI state; let the compiler
  prove isolation instead of asserting "this always runs on main" in
  a comment. Aim for strict concurrency checking (Swift 6 mode) and
  make `Sendable` conformance real — `@unchecked Sendable` needs a
  comment justifying why the compiler can't see the safety.
- Avoid unstructured `Task { ... }` where a structured alternative
  (`async let`, `TaskGroup`, or just `await` in the caller) would do.
  When an unstructured `Task` is genuinely necessary (e.g. kicking off
  work from synchronous UI code), give it explicit priority and
  respect cancellation (`Task.checkCancellation()` / `Task.isCancelled`)
  rather than letting it run unbounded.

## Testing discipline

- `swift-testing` (`import Testing`, `@Test` functions, `#expect` /
  `#require`) for new test code; XCTest remains fine for UI tests,
  performance tests, or an existing XCTest suite you're extending
  rather than migrating wholesale.
- Run with `swift test`. `@Test(arguments:)` for parameterized cases
  over combinatorial input instead of hand-copied near-duplicate test
  functions.
- Regression discipline: a bug fix ships with a test that fails on
  the pre-fix tree, landed in the same commit as the fix.
- `async` test functions (`@Test func ...() async throws`) for
  exercising `async` APIs directly — don't wrap them in expectation
  bridges when the test function can just be `async`.

## Packaging

- Swift Package Manager is the default distribution mechanism:
  `Package.swift` at the root, dependencies declared there rather
  than vendored.
- Pin `// swift-tools-version:` and the `platforms:` floor
  deliberately (e.g. `.iOS(.v17), .macOS(.v14)`) — raising either is
  a breaking change for consumers on older toolchains or OS versions.
- Keep the public surface `public`-annotated on purpose: export types
  and members a consumer needs, leave everything else `internal`.
  Widening access later is easy; narrowing it is a breaking change.
- Justify new package dependencies the same as any other supply-chain
  decision — what it buys you, what the alternatives were.

## Toolchain

CI already enforces `swift-format` and `SwiftLint`; run them before
pushing and pass the gate rather than re-describing it. The
conventions the linter can't express for you:

- A SwiftLint rule you disagree with gets
  `// swiftlint:disable:next <rule>` with a comment explaining why,
  scoped to the one line — never a blanket `swiftlint:disable` for a
  whole file.
- Treat compiler warnings as errors where the target allows it
  (`-warnings-as-errors`); an ignored warning today is a `!`-shaped
  crash next release.

## What NOT to do

- No force-unwrap `!` or `try!` on data that isn't statically proven
  present — that includes JSON payloads, user input, and file reads.
- No `class` where a `struct` gives you the same behavior without the
  reference-semantics footguns (shared mutation, retain cycles).
- No `fatalError()` for a case a caller could reasonably trigger;
  that belongs in a thrown `Error`.
- No class inheritance chains where a protocol plus extensions would
  compose the same behavior with less coupling.
- No retain cycles: closures that capture `self` across an async
  boundary or a stored callback use `[weak self]` (or `[unowned self]`
  only when the lifetime is provably tied).
- No singletons or global mutable state as the default way to share
  data — pass dependencies explicitly or use an actor.
