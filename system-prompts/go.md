# Language profile: Go

You are working in a Go project. The universal rules above still
apply; this section refines them for Go idioms.

## Error handling

- Functions that can fail return `(T, error)`, error last. Check it
  immediately with `if err != nil`; do not stack multiple fallible
  calls before checking.
- Never ignore a returned `err` — not even `_ = f()` "because it
  can't fail here." If it truly can't fail, that's still worth a
  comment explaining why, not a silent discard.
- Wrap errors with `fmt.Errorf("doing X: %w", err)` to preserve the
  chain; callers use `errors.Is` / `errors.As` to inspect it, never
  string-match on `err.Error()`.
- Sentinel errors (`var ErrNotFound = errors.New(...)`) for values
  callers compare with `errors.Is`. Typed errors (`type ValidationError
  struct{...}`) implementing `Error() string` when the caller needs
  fields, inspected with `errors.As`.
- `panic` is for programmer bugs and unrecoverable startup failures
  (a nil dependency wired wrong, an invariant violated by construction)
  — never for expected failures like a missing file or bad input.
  Library code in particular must not panic on bad input; return an
  error and let the caller decide.
- A `recover()` belongs at a process boundary (an HTTP middleware, a
  worker-pool goroutine) to contain a panic and log it — not as a
  general-purpose control-flow mechanism.

## Idioms & types

- Define interfaces at the consumer, not the producer: accept
  interfaces, return concrete structs. A package exposing `Store`
  should return `*Store`, not `Store` behind an interface it also
  defines — let the caller declare the narrow interface it actually
  needs.
- Keep interfaces small. One or two methods is normal; `io.Reader`
  and `io.Writer` are the model to imitate, not the exception.
- Composition over inheritance — Go has no inheritance. Embed a
  struct or interface to reuse behavior, and be deliberate about what
  the embedding promotes into the outer type's method set.
- Design zero-value-usable types where practical (`sync.Mutex`,
  `bytes.Buffer`, `var b strings.Builder`) so callers don't need a
  constructor just to get a usable value.
- `defer` for cleanup (`Close`, `Unlock`, `cancel`) right after the
  resource is acquired, not scattered later in the function — and
  check the deferred error where it matters (`defer func() { err =
  errors.Join(err, f.Close()) }()`), don't silently swallow it.
- Go has no sum types. Model a closed set of variants with an
  interface plus a small set of concrete implementing types (a
  "sealed" pattern via an unexported marker method), or a tagged
  struct with an explicit kind field — not a grab-bag `interface{}`
  that pushes the type switch onto every caller.
- Generics earn their place when they remove real duplication
  (a container, a `Map`/`Filter` helper, a comparable-keyed cache).
  If a plain interface with one or two methods reads clearer, prefer
  it — a type parameter that exists to avoid one type assertion is
  not a win.

## Concurrency

- Default model: share memory by communicating, not the reverse.
  Pass ownership of data across a channel rather than mutating a
  shared struct from multiple goroutines.
- Fan-out/join: `sync.WaitGroup` for a bounded fixed set of
  goroutines; `golang.org/x/sync/errgroup` when any of them can fail
  and you need the first error plus coordinated cancellation.
- `context.Context` is the first parameter of any function that does
  I/O, blocks, or spans a request — `func Fetch(ctx context.Context,
  id string) (*Item, error)`. Never store a `Context` in a struct
  field; thread it through calls instead.
- Guard shared mutable state with a `sync.Mutex`/`sync.RWMutex` held
  for the shortest scope possible, or move the state behind a single
  goroutine that owns it and communicates over a channel — pick one
  discipline per piece of state, not both.
- Every channel has exactly one owner responsible for closing it, and
  that owner never writes after close. Document who closes a channel
  in the function that creates it; a channel closed by a receiver or
  closed twice is a bug, not a style choice.
- Every goroutine you spawn either terminates on its own, is joined
  with a `WaitGroup`/`errgroup`, or is bound to a `Context` that gets
  canceled — a goroutine with no exit path and no owner is a leak.

## Testing discipline

- `go test ./...` as the baseline; table-driven tests are the
  default shape for anything with more than two cases:
  `tests := []struct{ name string; in T; want U }{...}` iterated with
  `t.Run(tt.name, func(t *testing.T) {...})`.
- Use `t.Run` subtests even for a single logical group when it aids
  `-run` filtering and failure output.
- `testing/quick`, or `gopkg.in/quick`-style property tests, for
  input spaces with an algebraic property (round-trip encode/decode,
  idempotent normalization) rather than hand-picked cases alone.
- Run the race detector (`go test -race ./...`) for anything touching
  goroutines or shared state — a concurrency bug that doesn't show up
  without `-race` is still a bug.
- Regression discipline: fix a bug by first writing a test that fails
  on the pre-fix tree, then land both in the same commit.
- Table cases and subtests should assert behavior (`want` values),
  not just execute the code path — coverage without assertions is not
  a test.

## Modules & build

- `go.mod` declares the module path and the `go` directive; pin the
  `go` directive to the actual minimum toolchain version the module
  needs, and treat raising it as a deliberate, documented decision,
  not an incidental side effect of `go mod tidy`.
- Rely on minimal version selection — don't hand-pin transitive
  dependencies in `go.mod` unless working around a specific known-bad
  version, and say why in the commit.
- Keep the public surface small: unexported by default, promote a
  type or function to exported only when an external caller actually
  needs it. A large exported surface is a maintenance liability, not
  a convenience.
- `go mod tidy` before committing so `go.mod`/`go.sum` reflect actual
  imports, and commit `go.sum` — it's the supply-chain integrity
  record, not a generated artifact to gitignore.

## Toolchain

CI already enforces `gofmt`/`goimports` and `go vet` plus
`golangci-lint`; run them before pushing and pass the gate rather than
re-describing it. The conventions the linter can't express for you:

- A `golangci-lint` finding you disagree with gets a narrowly scoped
  `//nolint:<linter> // reason` on the specific line, never a blanket
  disable in `.golangci.yml` without a comment explaining the
  trade-off.
- Run `go vet ./...` as part of the same pre-push habit as `go test`
  — it catches struct-tag typos, `Printf` format mismatches, and
  lock-copying bugs that compile cleanly but are wrong.
- `gofmt -l .` (or `goimports -l .`) should report nothing; don't
  hand-format around the tool.

## What NOT to do

- No exceptions-as-panics. Don't use `panic`/`recover` as a substitute
  for returning `error` because it's "more convenient" up the stack.
- No deep interface hierarchies or Java-style `AbstractFooFactory`
  layering. One small interface at the point of use beats a taxonomy
  of interfaces nobody implements more than once.
- No `interface{}`/`any` as a default parameter or return type to
  dodge writing the real type — reserve it for genuine generic
  containers or serialization boundaries, and prefer a type parameter
  or a concrete interface first.
- No naked returns in anything but the shortest functions — a naked
  return in a 40-line function forces the reader to scroll back to
  the signature to know what's being returned.
- No ignoring `err`. Not `_ = f()`, not a `//nolint` slapped on
  reflexively — either handle it, wrap and propagate it, or justify
  the discard inline.
