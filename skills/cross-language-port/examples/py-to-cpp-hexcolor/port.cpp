// Port (TARGET): parse a #RRGGBB hex colour into "r g b" decimals.
//
// THE IDIOM SHIFT: Python raises `ValueError`; idiomatic modern C++ returns
// `std::expected<T, E>` (C++23) — the error is a value the caller inspects,
// not an exception unwinding the stack. RAII does the rest: `std::string`
// owns its buffer, there is no `new`/`delete`, and nothing leaks on the
// error path. Same contract as reference.py.
#include <array>
#include <cctype>
#include <expected>
#include <iostream>
#include <string>

namespace {

std::expected<std::array<int, 3>, std::string>
parse_color(const std::string& s) {
  if (s.size() != 7 || s[0] != '#') {
    return std::unexpected("invalid colour: " + s);
  }
  std::array<int, 3> rgb{};
  for (int channel = 0; channel < 3; ++channel) {
    int value = 0;
    for (int nibble = 0; nibble < 2; ++nibble) {
      const unsigned char c =
          static_cast<unsigned char>(s[1 + channel * 2 + nibble]);
      if (!std::isxdigit(c)) {
        return std::unexpected("invalid colour: " + s);
      }
      const int digit = std::isdigit(c)
                            ? c - '0'
                            : std::tolower(c) - 'a' + 10;
      value = value * 16 + digit;
    }
    rgb[channel] = value;
  }
  return rgb;
}

}  // namespace

int main() {
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) {
      continue;
    }
    if (const auto result = parse_color(line)) {
      std::cout << (*result)[0] << ' ' << (*result)[1] << ' ' << (*result)[2]
                << '\n';
    } else {
      std::cout << "ERROR: " << result.error() << '\n';
    }
  }
  return 0;
}
