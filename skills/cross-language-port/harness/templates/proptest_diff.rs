//! Differential property test TEMPLATE (Rust `proptest`).
//!
//! Assert the Rust PORT agrees with the SOURCE oracle (shelled out to) over
//! generated inputs. Drop into a crate's `tests/`, add `proptest` as a
//! dev-dependency, replace `port(...)` with a direct call to your ported
//! function (formatted identically to the source's stdout), and adjust the
//! input regex to your function's domain.

use std::io::Write;
use std::process::{Command, Stdio};

use proptest::prelude::*;

/// The reference implementation, invoked as a subprocess oracle.
fn oracle(input: &str) -> String {
    let mut child = Command::new("python3")
        .arg("reference.py")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("spawn reference");
    child
        .stdin
        .take()
        .unwrap()
        .write_all(input.as_bytes())
        .unwrap();
    let out = child.wait_with_output().unwrap();
    String::from_utf8(out.stdout).unwrap()
}

/// Replace with a direct call to your ported function that returns the same
/// stdout the source would (one line per input line, trailing newline).
fn port(_input: &str) -> String {
    unimplemented!("call your ported function and format identically")
}

proptest! {
    #[test]
    fn port_matches_oracle(line in "[0-9A-Fa-f #/:]{0,40}") {
        let stdin = format!("{line}\n");
        prop_assert_eq!(port(&stdin), oracle(&stdin));
    }
}
