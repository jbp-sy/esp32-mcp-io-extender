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

## Guardrails
- Preserve board safety policy as non-negotiable.
- Keep protocol changes additive when possible.
- Update docs + bridge + MCP + CLI together for protocol-affecting changes.
- Expose Python APIs that abstract protocol details for downstream integrations.
