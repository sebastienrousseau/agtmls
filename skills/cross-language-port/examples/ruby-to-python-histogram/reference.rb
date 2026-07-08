#!/usr/bin/env ruby
# frozen_string_literal: true

# Reference (SOURCE): word-frequency histogram.
#
# Idiomatic Ruby: an Enumerable pipeline. `split` on whitespace, drop empties,
# `tally` to count, `sort` to order. `tally` and block-driven Enumerable are
# the Ruby idioms the Python port maps to `collections.Counter` and
# comprehensions.
#
# Contract: read all of stdin; output "<word> <count>" per line, sorted by
# word ascending (words are unique, so ties never arise).

counts = $stdin.read.split(/\s+/).reject(&:empty?).tally
counts.sort.each { |word, n| puts "#{word} #{n}" }
