# Language profile: Ruby

You are working in a Ruby project. The universal rules above still
apply; this section refines them for Ruby idioms.

## Error handling

- Raise real exception classes: subclass `StandardError`, never
  `Exception` directly — `Exception` also catches `SystemExit` and
  `Interrupt`, which a library must not swallow.
- Library boundaries get a small hierarchy rooted at one gem-level
  base error (e.g. `MyGem::Error < StandardError`), with specific
  subclasses (`MyGem::ValidationError`, `MyGem::TimeoutError`) so
  callers can `rescue MyGem::ValidationError` without catching
  everything the gem can raise.
- `rescue SpecificError` always. A bare `rescue` or `rescue => e`
  at a call site hides `NoMethodError`, `TypeError`, and other bugs
  behind "handled" code — rescue the narrowest class that the
  recovery logic actually knows how to handle.
- Never `rescue nil` (or the equivalent `rescue; nil; end`). It
  discards the exception class, the message, and the backtrace —
  there is no way to tell a network timeout from a typo later.
- Reraise with context instead of swallowing: `raise
  MyGem::FetchError, "fetching #{url}"` inside a `rescue
  Net::HTTPError => e` block, or attach `cause:` explicitly when
  re-raising a different class so the original backtrace survives.
- `ensure` for cleanup that must run regardless of outcome (closing
  file handles, releasing locks, resetting state) — don't rely on
  the caller to clean up after a raised exception.
- Custom errors carry the data a caller needs to react
  programmatically (an `attr_reader` for the offending value, not
  just a formatted message string).

## Idioms

- `# frozen_string_literal: true` at the top of every file. It
  catches accidental mutation of string literals and is free
  performance under MRI's string deduplication.
- Reach for `Enumerable` — `map`, `select`, `reject`, `reduce`,
  `each_with_object`, `tally`, `group_by`, `flat_map` — before a
  hand-rolled loop with a mutable accumulator. A `for` loop or
  manual `while` counter is a signal something idiomatic was missed.
- Keyword arguments for anything with more than one parameter or
  where call-site clarity matters: `def connect(host:, port: 443,
  timeout: 5.0)`, not positional booleans or a trailing options
  hash.
- Duck typing over `is_a?` / `kind_of?` checks. Ask whether the
  object responds to the message you need (`respond_to?` at most,
  and ideally not even that — let `NoMethodError` do its job) rather
  than gating on class identity.
- `attr_reader` / `attr_accessor` / `attr_writer` over hand-written
  getters and setters that just wrap `@ivar`. Write a real method
  only when it does more than expose the ivar.
- `Struct.new` or, on Ruby 3.2+, `Data.define` for immutable value
  objects (a point, a money amount, a coordinate pair) instead of a
  full class with a hand-written `initialize`, `==`, and `hash`.
- Guard clauses (`return unless valid?`) over nested `if`/`else`
  pyramids — flatten the happy path, handle exceptions to it early.
- String interpolation (`"#{a}-#{b}"`) over concatenation with `+`
  or `<<` when building a message; reserve `<<` for building up a
  buffer in a loop.
- Symbols for internal identifiers and hash keys (`:pending`, not
  `"pending"`); reserve strings for things that are actually text.

## Types (optional)

- Ruby is duck-typed by default and most gems should stay that way
  — keep the public surface small, and let `respond_to?` and clear
  errors do the work that a type system would.
- For a library whose public surface benefits from static checking
  (a shared internal gem, a payments or auth boundary, anything
  with a wide blast radius when misused), add gradual typing with
  Sorbet (`sig { params(...).returns(...) }`) or RBS
  (`sig/*.rbs`) rather than retrofitting runtime type-checks by
  hand.
- Don't sprinkle `T.let` / `sig` annotations across an entire
  application for their own sake — type the boundary that pays for
  it (public API, money, external I/O), not every private helper.

## Testing discipline

- RSpec (`describe`/`context`/`it`) or Minitest — pick one per
  project and stay consistent; don't mix frameworks in the same
  suite.
- One behaviour per example. An `it` block that asserts three
  unrelated things fails ambiguously and slows down triage.
- `let` / `let!` for lazy fixtures, or a factory library (e.g.
  FactoryBot) for object graphs, instead of duplicating setup in
  every example or building fixtures in a shared mutable
  `before(:all)`.
- A bug fix ships with a test that fails on the pre-fix tree, in
  the same commit as the fix.
- Avoid over-mocking. Method dispatch in Ruby is dynamic and every
  object is technically monkey-patchable, which makes it easy to
  stub your way to a green suite that asserts nothing real — test
  observable behaviour (return values, raised errors, state
  changes) over internal message sends. Reserve `expect(...).to
  receive(...)` for genuine collaborator boundaries (an HTTP client,
  a mailer, a queue), not for objects you own end to end.

## Gems and environment

- Bundler manages dependencies; commit `Gemfile.lock` for
  applications so every environment resolves the same graph. For a
  published gem, commit the `.gemspec` version constraints and let
  consumers resolve their own lockfile.
- Semantic versioning in the gemspec (`~> 2.1`), and bump the major
  version on a breaking change to the gem's public API.
- Declare the Ruby version floor in `.ruby-version` (and mirror it
  in the gemspec's `required_ruby_version`) so `rbenv`/`rvm`/`mise`
  and CI all agree on which Ruby runs the suite.
- Vendor nothing that Bundler can manage; a `vendor/` full of
  hand-copied gem source is a supply-chain and upgrade liability.

## Toolchain

CI already enforces `rubocop` (or `standardrb`); run it before
pushing and pass the gate rather than re-describing it. The
conventions the linter can't express for you:

- Run `rubocop -a` (or `standardrb --fix`) locally and commit a
  clean tree — don't push code the autocorrect would have touched.
- A cop you disagree with gets `# rubocop:disable Cop/Name` on the
  offending line with a comment explaining why, immediately followed
  by `# rubocop:enable Cop/Name` once the exception ends — never a
  file-wide or project-wide disable for a single legitimate
  exception.
- Keep `.rubocop.yml` deviations from the default ruleset
  documented inline (why this project excludes or relaxes a cop),
  not silently accumulated.

## What NOT to do

- No Java-style class ceremony — abstract base classes, interface
  simulation via empty modules, a `Factory` for every `Builder`.
  Ruby's dynamism replaces most of that machinery with a method and
  a module.
- No bare `rescue` (or `rescue => e` used as a catch-all) around
  code that should only handle one failure mode.
- No mutating shared globals or constants at runtime
  (`SOME_CONST << value`, reopening a class to stash mutable state
  in a class variable) — treat constants as actually constant and
  give mutable shared state an explicit owner.
- No monkey-patching core classes (`String`, `Array`, `Hash`, `Object`)
  from inside a library — a consumer's app-wide behavior should never
  change because they required your gem. Core-class patches belong,
  at most, in the application that owns the whole process, and even
  there need a strong reason.
- No metaprogramming (`define_method`, `method_missing`,
  `class_eval` with a string) where a plain, greppable method would
  do. Metaprogramming earns its keep only when the alternative is
  genuinely repetitive boilerplate, and it always costs readability
  and debuggability.
