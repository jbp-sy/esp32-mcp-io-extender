# Skill: Python Integration API

## Purpose
Provide a Python-first integration boundary.

## Guidelines
- Prefer typed Python helpers over raw protocol payload crafting.
- Keep exceptions explicit (`DeviceError`, `TransportError`).
- Keep downstream repos decoupled from protocol specifics.
