// Differential property test TEMPLATE (JS/TS `fast-check`).
//
// Assert the PORT agrees with the SOURCE oracle over generated inputs.
// Copy next to an example, adjust the two commands and the arbitrary to your
// function's input domain, then:
//
//     npm i -D fast-check && node fast-check_diff.mjs
import fc from "fast-check";
import { execFileSync } from "node:child_process";

const run = (cmd, args, stdin) =>
  execFileSync(cmd, args, { input: stdin, encoding: "utf8" });

const source = (s) => run("node", ["reference.js"], s); // the reference oracle
const port = (s) => run("node", ["port.ts"], s); // the ported target

fc.assert(
  fc.property(fc.string(), (line) => {
    const stdin = line + "\n";
    return port(stdin) === source(stdin);
  }),
  { numRuns: 500 },
);
console.log("ok: port matches source over 500 generated inputs");
