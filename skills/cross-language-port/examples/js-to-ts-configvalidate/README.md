# Worked port — JavaScript → TypeScript: config validation

Fleet domain: JS/TS tooling (`password-generator`, `stratos`, `crypto-service`).

## What this teaches

**The runtime type-erasure landmine (`reference.md` §R2 TypeScript, §R4).**
TypeScript types vanish at runtime. The tempting port —
`const c = JSON.parse(line) as Config` — compiles cleanly and validates
**nothing**; untrusted input walks straight past the type system and the
"typed" object is a lie. The idiomatic port validates at the boundary with
an explicit guard that narrows `unknown` → `Config`; the compile-time type
is the *reward* for validating, not a substitute. (Real projects use a
`zod` schema; kept dependency-free here so it runs on bare Node.)

The source JS already did every check at runtime (it had no choice). The
port's job is to **keep** that runtime validation while adding the
compile-time layer — not to let the types lull it into dropping the checks.

## Files

| File | Role |
|---|---|
| `reference.js` | SOURCE — modern ESM JavaScript, all-runtime validation |
| `port.ts` | TARGET — idiomatic TS: `unknown` → typed via an explicit guard |
| `package.json` | scopes both files as ESM |
| `corpus/` | valid + every failure mode (bad type, range, missing field, non-object, bad JSON) |
| `verify.sh` | differential proof: source reproduces golden **and** port matches |

## Run it

```sh
./verify.sh            # equivalence proof (node runs both .js and .ts)
tsc --noEmit port.ts   # full land-green typecheck (needs a local TypeScript)
```

`node` runs `port.ts` via type-stripping (no typecheck). For the compile-
time guarantee, run `tsc --noEmit` in a project with TypeScript installed —
that is the half of "green" this example demonstrates you must not skip.

Status: **source and port agree on all 8 inputs.**
