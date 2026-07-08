// Port (TARGET): parse a duration like "1h30m45s" into seconds, idiomatic Go.
//
// THE IDIOM SHIFT: Python's `raise ValueError` + caller `try/except` becomes
// Go's `(int, error)` return + caller `if err != nil`. The control flow
// inverts — nothing "throws"; every failure is a value the caller must
// handle. No exceptions, no sum types; validation is a regexp plus an error.
// Same contract as reference.py.
package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strconv"
)

var (
	fullRe  = regexp.MustCompile(`^(\d+[hms])+$`)
	partsRe = regexp.MustCompile(`(\d+)([hms])`)
	unit    = map[string]int{"h": 3600, "m": 60, "s": 1}
)

func parseDuration(s string) (int, error) {
	if !fullRe.MatchString(s) {
		if s == "" {
			return 0, fmt.Errorf("empty")
		}
		return 0, fmt.Errorf("invalid duration: %s", s)
	}
	total := 0
	for _, m := range partsRe.FindAllStringSubmatch(s, -1) {
		n, _ := strconv.Atoi(m[1]) // safe: fullRe guarantees digit runs
		total += n * unit[m[2]]
	}
	return total, nil
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
		if v, err := parseDuration(line); err != nil {
			fmt.Fprintf(w, "ERROR: %s\n", err)
		} else {
			fmt.Fprintln(w, v)
		}
	}
}
