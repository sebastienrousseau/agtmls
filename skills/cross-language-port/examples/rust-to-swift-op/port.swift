// Port (TARGET): the same op evaluator, idiomatic Swift.
//
// THE IDIOM SHIFT: Rust's `enum` with associated values maps 1:1 to a Swift
// `enum` with associated values — that part is a near-transliteration. What
// changes is the ERROR CHANNEL: Rust's `Result<T, String>` becomes Swift's
// native `throws`. Callers use `try` / `do-catch` instead of matching a
// `Result`. Porting the enum literally but keeping `Result` would read as
// non-native Swift; the point is to adopt the target's error convention.
//
// Contract matches reference.rs exactly.

enum Op {
    case add(Int, Int)
    case neg(Int)
}

struct EvalError: Error { let message: String }

func num(_ s: String) throws -> Int {
    guard let v = Int(s) else { throw EvalError(message: "not an integer: \(s)") }
    return v
}

func parse(_ line: String) throws -> Op {
    let toks = line.split(separator: " ", omittingEmptySubsequences: true).map(String.init)
    switch toks.count {
    case 3 where toks[0] == "ADD":
        return .add(try num(toks[1]), try num(toks[2]))
    case 2 where toks[0] == "NEG":
        return .neg(try num(toks[1]))
    default:
        if let cmd = toks.first {
            throw EvalError(message: "unknown or malformed op: \(cmd)")
        }
        throw EvalError(message: "empty")
    }
}

func eval(_ op: Op) -> Int {
    switch op {
    case let .add(a, b): return a + b
    case let .neg(a): return -a
    }
}

while let line = readLine(strippingNewline: true) {
    if line.isEmpty { continue }
    do {
        print(eval(try parse(line)))
    } catch let e as EvalError {
        print("ERROR: \(e.message)")
    }
}
