// Reference (SOURCE): reduce a fraction "a/b" to lowest terms.
//
// Idiomatic Go: return (value, error). Callers branch on `err != nil`; the
// value slot holds the zero value when there is an error. This (T, error)
// pair is the shape the Rust port must translate into `Result`.
//
// Contract: one "a/b" per stdin line -> "p/q" reduced, or "ERROR: <reason>".
package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func gcd(a, b int) int {
	if a < 0 {
		a = -a
	}
	if b < 0 {
		b = -b
	}
	for b != 0 {
		a, b = b, a%b
	}
	return a
}

func reduce(s string) (string, error) {
	parts := strings.Split(s, "/")
	if len(parts) != 2 {
		return "", fmt.Errorf("expected a/b")
	}
	num, err := strconv.Atoi(strings.TrimSpace(parts[0]))
	if err != nil {
		return "", fmt.Errorf("numerator not an integer")
	}
	den, err := strconv.Atoi(strings.TrimSpace(parts[1]))
	if err != nil {
		return "", fmt.Errorf("denominator not an integer")
	}
	if den == 0 {
		return "", fmt.Errorf("division by zero")
	}
	g := gcd(num, den)
	num, den = num/g, den/g
	if den < 0 { // keep the sign on the numerator
		num, den = -num, -den
	}
	return fmt.Sprintf("%d/%d", num, den), nil
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	for sc.Scan() {
		line := sc.Text()
		if line == "" {
			continue
		}
		if out, err := reduce(line); err != nil {
			fmt.Fprintf(w, "ERROR: %s\n", err)
		} else {
			fmt.Fprintln(w, out)
		}
	}
}
