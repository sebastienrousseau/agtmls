//! Port (TARGET): reduce a fraction "a/b" to lowest terms, idiomatic Rust.
//!
//! THE IDIOM SHIFT. Go's `(T, error)` with a zero-value on failure becomes
//! Rust's `Result<T, E>` — no zero-value ambiguity, and the compiler forces
//! the caller to handle the error. Go's `strconv.Atoi` (value, error)
//! becomes `str::parse` (`Result`), threaded with `?`. Go's imperative
//! branching collapses into `match`/`?`. Same contract as `reference.go`.
//!
//! Contract: one "a/b" per stdin line -> "p/q" reduced, or "ERROR: <reason>".

use std::io::{self, BufRead, Write};

fn gcd(mut a: i64, mut b: i64) -> i64 {
    a = a.abs();
    b = b.abs();
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

fn reduce(s: &str) -> Result<String, &'static str> {
    // Match Go's `strings.Split(s, "/")` + len==2 check exactly:
    // "1/2/3" must be rejected as "expected a/b", not parsed as 1 and "2/3".
    let parts: Vec<&str> = s.split('/').collect();
    if parts.len() != 2 {
        return Err("expected a/b");
    }
    let mut num: i64 = parts[0]
        .trim()
        .parse()
        .map_err(|_| "numerator not an integer")?;
    let mut den: i64 = parts[1]
        .trim()
        .parse()
        .map_err(|_| "denominator not an integer")?;
    if den == 0 {
        return Err("division by zero");
    }
    let g = gcd(num, den);
    num /= g;
    den /= g;
    if den < 0 {
        // keep the sign on the numerator
        num = -num;
        den = -den;
    }
    Ok(format!("{num}/{den}"))
}

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let mut out = io::stdout().lock();
    for line in stdin.lock().lines() {
        let line = line?;
        if line.is_empty() {
            continue;
        }
        match reduce(&line) {
            Ok(v) => writeln!(out, "{v}")?,
            Err(e) => writeln!(out, "ERROR: {e}")?,
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::reduce;

    #[test]
    fn reduces_and_signs() {
        assert_eq!(reduce("6/4").unwrap(), "3/2");
        assert_eq!(reduce("0/5").unwrap(), "0/1");
        assert_eq!(reduce("-6/4").unwrap(), "-3/2");
        assert_eq!(reduce("6/-4").unwrap(), "-3/2");
    }

    #[test]
    fn errors() {
        assert!(reduce("1/0").is_err());
        assert!(reduce("x/4").is_err());
        assert!(reduce("1/2/3").is_err());
    }
}
