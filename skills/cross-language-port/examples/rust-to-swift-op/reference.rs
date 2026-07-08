//! Reference (SOURCE): evaluate a tiny op language over an enum with
//! associated values. Idiomatic Rust: `enum Op { Add(i64,i64), Neg(i64) }`
//! and a `Result<_, String>` error channel that the caller `match`es.
//!
//! Contract: one op per stdin line ("ADD a b" | "NEG a") -> the integer
//! result, or "ERROR: <reason>".

use std::io::{self, BufRead, Write};

enum Op {
    Add(i64, i64),
    Neg(i64),
}

fn num(s: &str) -> Result<i64, String> {
    s.parse().map_err(|_| format!("not an integer: {s}"))
}

fn parse(line: &str) -> Result<Op, String> {
    let toks: Vec<&str> = line.split_whitespace().collect();
    match toks.as_slice() {
        ["ADD", a, b] => Ok(Op::Add(num(a)?, num(b)?)),
        ["NEG", a] => Ok(Op::Neg(num(a)?)),
        [cmd, ..] => Err(format!("unknown or malformed op: {cmd}")),
        [] => Err("empty".to_string()),
    }
}

fn eval(op: Op) -> i64 {
    match op {
        Op::Add(a, b) => a + b,
        Op::Neg(a) => -a,
    }
}

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let mut out = io::stdout().lock();
    for line in stdin.lock().lines() {
        let line = line?;
        if line.is_empty() {
            continue;
        }
        match parse(&line) {
            Ok(op) => writeln!(out, "{}", eval(op))?,
            Err(e) => writeln!(out, "ERROR: {e}")?,
        }
    }
    Ok(())
}
