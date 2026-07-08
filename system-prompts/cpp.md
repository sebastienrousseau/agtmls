# Language profile: C++

You are working in a C++ project. The universal rules above still
apply; this section refines them for modern C++ (target C++20/23)
idioms.

## Error handling

- `std::expected<T, E>` (C++23) for recoverable, expected failure
  paths — parsing, validation, I/O results the caller is meant to
  branch on. Reserve exceptions for truly exceptional conditions:
  invariant violations, constructor failure, out-of-memory.
- Never let a fallible call's return value go unchecked. A
  `[[nodiscard]]`-returning function whose result is silently
  dropped is a bug, not a style nit — apply `[[nodiscard]]` to
  `std::expected`- and error-code-returning functions so the
  compiler catches it.
- RAII, not `try`/`catch`/`finally`, is the cleanup mechanism.
  Every resource-owning type must release correctly whether it's
  destroyed normally or unwound by an in-flight exception — that's
  the property to test, not "we remembered to catch."
- `std::optional<T>` for "value or absence," not for "value or
  error." If the caller needs to know *why* something failed,
  that's `std::expected`, not `std::optional`.
- Don't translate a lower-level exception into a swallowed `catch
  (...) {}`. Catch narrowly, handle or rethrow (`throw;` preserves
  the original), and never catch-and-ignore across a boundary.

## Memory & RAII

- Smart pointers own memory; raw pointers observe it. `new` and
  `delete` do not appear in application code — `std::make_unique`
  / `std::make_shared` (or a factory that wraps them) are the only
  entry points.
- `std::unique_ptr<T>` is the default for owned, single-owner
  resources. Reach for `std::shared_ptr<T>` only when ownership is
  genuinely shared and the lifetime graph can't be expressed with a
  single owner plus borrows — a `shared_ptr` used because "ownership
  is unclear" is a design smell, not a solution.
- Rule of zero: if a type manages a resource, wrap that one
  resource in its own RAII type and let the compiler generate
  copy/move/dtor for the composing type. Hand-writing the rule of
  five is a signal the resource should have been factored out.
- `const`-correctness by default: member functions that don't
  mutate are `const`; parameters that aren't sinks are `const T&`
  or a view type. A non-`const` reference to something the callee
  only reads is a design bug, not a convenience.
- `std::span<T>` / `std::string_view` for non-owning views into
  contiguous data — but a view is only as good as what it points
  into. Never return a `string_view`/`span` bound to a local,
  temporary, or anything whose lifetime doesn't provably outlive
  every use.

## Types & idioms

- Value semantics by default. Pass and return by value and let move
  semantics make it cheap; reach for indirection (pointer, `unique_ptr`,
  reference) only when the type is polymorphic, expensive to move, or
  ownership genuinely requires it.
- Implement move constructor/assignment (or take the rule of zero)
  for any type holding a resource; mark them `noexcept` when they
  are, so standard containers pick moves over copies.
- `enum class` always — a bare `enum` that implicitly converts to
  `int` and pollutes the enclosing scope is a defect, not a
  shorthand.
- `constexpr` for anything computable at compile time; `consteval`
  when it must be. Compile-time evaluation is a correctness tool
  (fail the build instead of the runtime), not just an optimization.
- Structured bindings for multi-value returns and map iteration —
  `auto [key, value] : m` over `it->first` / `it->second`.
- Ranges (`<ranges>`, C++20) for pipeline-shaped transformations over
  hand-rolled index loops, when the composed view reads more clearly
  than the loop it replaces.
- `auto` where the type is spelled out on the right-hand side or is
  genuinely unwieldy (iterators, lambda types); spell out the type
  when `auto` would hide a narrowing conversion or the reader's
  intent.

## Testing discipline

- GoogleTest or Catch2, run through `ctest` so the whole suite has
  one entry point regardless of which framework a given target uses.
- A bug fix ships together with a test that fails on the pre-fix
  tree and passes after — the fix and its proof land in the same
  commit.
- AddressSanitizer and UndefinedBehaviorSanitizer run in CI (a
  sanitizer build is a separate CMake configuration, not a flag
  bolted onto the release build). A memory-safety fix without a
  sanitizer-clean run is unverified.
- Cross-path parity: if two implementations claim the same
  semantics (e.g. a SIMD fast path vs a scalar fallback), a test
  that runs both against shared inputs and compares outputs is
  mandatory.

## Build & dependencies

- CMake, expressed as targets and their properties
  (`target_link_libraries`, `target_compile_features`,
  `target_include_directories`) — not global `set(CMAKE_CXX_FLAGS
  ...)` mutation, which leaks into every target in the build.
- `vcpkg` or Conan for third-party dependencies; no vendored
  copy-pasted sources unless the project has no package-manager
  path and says so explicitly.
- Pin the standard explicitly: `target_compile_features(tgt PUBLIC
  cxx_std_20)` (or 23). Don't rely on the compiler's default
  dialect.
- Warnings are errors in CI (`-Werror` / `/WX`) so a new warning
  fails the build instead of accumulating.

## Toolchain

CI already enforces `clang-format` and `clang-tidy`; run them
before pushing and pass the gate rather than re-describing it. The
conventions the linter can't express for you:

- `-Wall -Wextra -Werror` at minimum; add `-Wpedantic` and
  `-Wshadow` unless the project has a documented reason not to.
- A `clang-tidy` finding you disagree with gets a narrowly scoped
  `// NOLINT(check-name): reason` on the offending line — never a
  blanket `// NOLINTBEGIN` around a whole file or a suppressed
  check in `.clang-tidy` without a comment explaining why.
- `.clang-format` is checked in and authoritative; don't hand-format
  against it.

## What NOT to do

- No raw owning pointers and no manual `delete` — if you're writing
  `delete` outside a smart pointer's own implementation, stop and
  reach for `unique_ptr`/`shared_ptr` instead.
- No C-style casts (`(T)x`) and no `reinterpret_cast` as a first
  resort. Use `static_cast`, `const_cast`, or `dynamic_cast` for
  what they're each scoped to do, so the cast documents its own
  intent.
- No macros where `constexpr`, `inline` functions, or templates do
  the same job with type checking. A macro is a last resort for
  things the type system genuinely cannot express (header guards,
  conditional compilation).
- No returning a reference or `string_view`/`span` bound to a local
  variable, parameter copy, or temporary — the object dies at the
  end of the function and the caller inherits a dangling view.
- No ignoring exception safety: a function that leaves a container
  or resource half-mutated when an exception escapes mid-operation
  is broken, even if the exception itself is "handled" elsewhere.
