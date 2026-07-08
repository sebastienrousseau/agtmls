# Worked port — Python → C++: hex colour parser

Fleet domain: Python → C++ (`euxis`).

## What this teaches

**Exceptions → `std::expected`, and RAII (`reference.md` §R2 C++, §R1.2).**
Python validates and `raise ValueError`; the caller uses `try/except`. The
idiomatic modern C++ port returns **`std::expected<T, E>` (C++23)** — the
error is a value the caller inspects (`if (result) … else result.error()`),
not an exception unwinding the stack. RAII carries the rest: `std::string`
owns its buffer, there is **no `new`/`delete`**, and nothing leaks on the
error path. Porting Python's exception model into C++ exceptions would
compile but miss the modern-C++ idiom this example demonstrates.

## Files

| File | Role |
|---|---|
| `reference.py` | SOURCE — idiomatic Python, `raise ValueError` |
| `port.cpp` | TARGET — idiomatic C++23, `std::expected` + RAII |
| `compile_flags.txt` | pins `-std=c++23` for clangd / the build |
| `corpus/` | valid colours + malformed (bad hex, no `#`, wrong length) |
| `verify.sh` | differential proof: source reproduces golden **and** port matches |

## Run it

```sh
./verify.sh                                      # compiles C++23, proves equivalence
c++ -std=c++23 -Wall -Wextra port.cpp -o /tmp/p  # land-green: zero warnings
ruff check reference.py                          # Python land-green
```

Status: **source and port agree on all 8 inputs; compiles clean under
`-std=c++23 -Wall -Wextra`.**

> Requires a C++23 compiler for `std::expected` (Apple clang 15+/GCC 13+).
> `compile_flags.txt` makes clangd use the right standard so the editor
> doesn't false-flag `std::expected`.
