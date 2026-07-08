#!/usr/bin/env node
// Port (TARGET): same contract, idiomatic TypeScript.
//
// THE LANDMINE: TypeScript types are ERASED at runtime. Writing
// `JSON.parse(line) as Config` compiles cleanly but validates NOTHING —
// untrusted input walks straight past the type system and your "typed"
// object is a lie. The idiomatic port validates at the boundary with an
// explicit runtime guard that narrows `unknown` down to the typed shape;
// the compile-time `Config` type is the *reward* for validating, never a
// substitute for it. (In a real project this guard is a `zod` schema; kept
// dependency-free here so the example runs on bare Node.)
import { readFileSync } from "fs";

interface Config {
  host: string;
  port: number;
}

function parseConfig(value: unknown): Config | string {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return "ERROR: not an object";
  }
  const o = value as Record<string, unknown>;
  if (typeof o.host !== "string" || o.host.length === 0) {
    return "ERROR: host must be a non-empty string";
  }
  if (typeof o.port !== "number" || !Number.isInteger(o.port)) {
    return "ERROR: port must be an integer";
  }
  if (o.port < 1 || o.port > 65535) {
    return "ERROR: port out of range";
  }
  return { host: o.host, port: o.port };
}

function normalize(line: string): string {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    return "ERROR: invalid json";
  }
  const result = parseConfig(value);
  return typeof result === "string" ? result : `${result.host}:${result.port}`;
}

for (const line of readFileSync(0, "utf8").split("\n")) {
  if (line === "") continue;
  console.log(normalize(line));
}
