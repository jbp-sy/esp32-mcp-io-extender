# Skill: Protocol and Compatibility

## Rules
- Treat `docs/serial_protocol.md` as contract.
- Keep request/response `id` matching behavior.
- Keep structured errors and metadata stable.
- Prefer additive changes for new features.

## Required follow-through
When protocol behavior changes:
1. Update protocol docs.
2. Update bridge handling.
3. Update MCP wrappers.
4. Update CLI coverage.
