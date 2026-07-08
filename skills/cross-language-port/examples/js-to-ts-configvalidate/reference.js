#!/usr/bin/env node
// Reference (SOURCE): validate + normalize a JSON endpoint config.
// Contract: one JSON object per stdin line -> "host:port" or
// "ERROR: <reason>". JavaScript has no static types, so every check is a
// runtime check — which is exactly the point the TypeScript port must not
// lose.
import { readFileSync } from "fs";

function normalize(line) {
  let value;
  try {
    value = JSON.parse(line);
  } catch {
    return "ERROR: invalid json";
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return "ERROR: not an object";
  }
  if (typeof value.host !== "string" || value.host.length === 0) {
    return "ERROR: host must be a non-empty string";
  }
  if (typeof value.port !== "number" || !Number.isInteger(value.port)) {
    return "ERROR: port must be an integer";
  }
  if (value.port < 1 || value.port > 65535) {
    return "ERROR: port out of range";
  }
  return `${value.host}:${value.port}`;
}

for (const line of readFileSync(0, "utf8").split("\n")) {
  if (line === "") continue;
  console.log(normalize(line));
}
