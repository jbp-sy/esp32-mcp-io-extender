# Skill: Git Workflow Hygiene

## Purpose
Keep workstreams reviewable and handoff-friendly.

## Requirements
- Create/use a dedicated branch per subject (for example `codex/<topic>`).
- Slice commits logically by concern; avoid unrelated mixed commits.
- Keep each commit coherent (code + tests + docs for that slice when relevant).
- Do not make merge policy decisions for the user.

## Handoff standard
- Prefer a clean working tree (`git status` empty) at session end.
- If clean state is impossible, explicitly report why and list remaining deltas.
