# Agent Loop Design Reference

This reference captures deeper checks for `agent-loop-design`.

## Required Outputs

- A concrete finding list or readiness decision.
- Commands or sources used for verification.
- Residual risks and required human review points.

## Safety

Respect the bundle `safety_policy` in `metadata.json`; do not escalate permissions or publish artifacts without explicit review.
