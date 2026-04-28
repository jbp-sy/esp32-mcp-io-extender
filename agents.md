# Agents Guide

This repository hosts an ESP32 MCP IO extender stack (firmware + host bridge + MCP tools).

## Required Context Load Order
1. `README.md`
2. `docs/serial_protocol.md`
3. `docs/agent_runbook.md`
4. `agents/library.required.skills.md`

## Required Skill Library (auto-reference)
- `agents/skills/repo-orientation.skills.md`
- `agents/skills/protocol-and-compatibility.skills.md`
- `agents/skills/python-integration-api.skills.md`
- `agents/skills/verification-and-safety.skills.md`
- `agents/skills/git-workflow-hygiene.skills.md`

## Guardrails
- Preserve board safety policy as non-negotiable.
- Keep protocol changes additive when possible.
- Update docs + bridge + MCP + CLI together for protocol-affecting changes.
- Expose Python APIs that abstract protocol details for downstream integrations.

## Workflow Expectations
- Finish the full change loop in one pass when feasible: implement, verify, document, and commit.
- Do not stop at "changes made"; run the required verification commands from `agents/skills/verification-and-safety.skills.md` first.
- If tests/tools are unavailable, report the exact blocker and still commit coherent completed work unless asked not to commit.
- Use coherent commits scoped to the change (code + docs + tests together when related).
- Default behavior after successful verification is to commit; only skip commit when the user explicitly says not to commit.

## Commit Hygiene
- Use clear imperative commit messages describing user-visible intent.
- Avoid mixing unrelated refactors with requested changes.
- Never rewrite or revert user-authored unrelated work.

## Skill Usage Notes
- `repo-orientation`: load architecture boundaries before editing.
- `protocol-and-compatibility`: treat `docs/serial_protocol.md` as contract.
- `python-integration-api`: keep downstream callers insulated from raw protocol details.
- `verification-and-safety`: compile/test and preserve safety invariants.
- `git-workflow-hygiene`: keep work reviewable and handoff-friendly.
