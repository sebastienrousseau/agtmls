//! Port (TARGET): IBAN mod-97 validation, idiomatic Rust.
//!
//! THE LANDMINE. Rust `std` has no arbitrary-precision integer, and the
//! expanded IBAN reaches ~40 decimal digits — past even `u128` (~39). A
//! 1:1 port of Python's `int(digits) % 97` therefore OVERFLOWS on long
//! IBANs. The idiomatic port never builds the big number: it folds the
//! remainder as it goes — `rem = (rem*10 + d) % 97` per digit, or
//! `(rem*100 + v) % 97` when a letter expands to a two-digit value. `u32`
//! is plenty because `rem < 97` always.
//!
//! Contract matches `reference.py` exactly: one IBAN per stdin line,
//! non-empty lines print `valid`/`invalid`. Only the space char is
//! stripped (to match Python's `.replace(" ", "")`, not all whitespace).

use std::io::{self, BufRead, Write};

fn iban_is_valid(iban: &str) -> bool {
    let s: String = iban
        .chars()
        .filter(|&c| c != ' ')
        .collect::<String>()
        .to_uppercase();
    if !(15..=34).contains(&s.len()) || !s.chars().all(|c| c.is_ascii_alphanumeric()) {
        return false;
    }
    let b = s.as_bytes();
    if !(b[0].is_ascii_alphabetic()
        && b[1].is_ascii_alphabetic()
        && b[2].is_ascii_digit()
        && b[3].is_ascii_digit())
    {
        return false;
    }
    // Move the first four characters to the end, then fold mod 97.
    let mut rem: u32 = 0;
    for byte in s[4..].bytes().chain(s[..4].bytes()) {
        if byte.is_ascii_digit() {
            rem = (rem * 10 + u32::from(byte - b'0')) % 97;
        } else {
            let v = u32::from(byte - b'A') + 10; // A..Z -> 10..=35 (two digits)
            rem = (rem * 100 + v) % 97;
        }
    }
    rem == 1
}

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let mut out = io::stdout().lock();
    for line in stdin.lock().lines() {
        let line = line?;
        if line.is_empty() {
            continue;
        }
        writeln!(
            out,
            "{}",
            if iban_is_valid(&line) {
                "valid"
            } else {
                "invalid"
            }
        )?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::iban_is_valid;

    #[test]
    fn canonical_valid() {
        assert!(iban_is_valid("GB82 WEST 1234 5698 7654 32"));
        assert!(iban_is_valid("DE89370400440532013000"));
        assert!(iban_is_valid("FR1420041010050500013M02606"));
    }

    #[test]
    fn rejects_bad_check_digit_and_length() {
        assert!(!iban_is_valid("GB82 WEST 1234 5698 7654 33"));
        assert!(!iban_is_valid("XX00"));
    }

    #[test]
    fn no_u128_overflow_on_max_length() {
        // 34-char IBAN full of letters would overflow a build-the-int port.
        let long = "GB82WEST12345698765432AAAAAAAAAAAA";
        let _ = iban_is_valid(long); // must not panic / must fold, not build
    }
}
