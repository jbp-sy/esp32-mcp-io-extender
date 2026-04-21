# Skill: Halo Bench Integration Guardrails

Purpose: keep this repository authoritative for protocol, transport, and safety
when downstream benches integrate via Python.

## Required behavior
- Treat serial JSONL protocol and UART pin reservation as stable contract.
- Reject changes that silently repurpose firmware UART pins (`GPIO20`, `GPIO21`).
- Keep low-level bridge API backward compatible when possible.
- Document protocol-affecting changes in `docs/serial_protocol.md` and integration notes.

## Safety policy
- Do not approve direct-drive workflows on `S_CAPACITOR`, `VBAT`, or `VSYS`.
- Require explicit caveat language in docs when direct 3.3 V wiring is assumed.
- Keep blocked/reserved pin policy synchronized across firmware and Python API docs.

## Workflow policy
- Use subject branches (`codex/...`) and logical commits.
- Keep tree clean at handoff; never leave partial protocol edits uncommitted.
- If changing transport/protocol behavior, update tests and docs in same branch.
