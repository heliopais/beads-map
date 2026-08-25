# Domain Docs

This is a single-context repository.

## Before exploring, read these

- `CONTEXT.md` at the repository root, if it exists.
- Relevant decisions under `docs/adr/`, if they exist.

Proceed silently when these files do not exist. Domain-modeling skills create
them lazily when terminology or architectural decisions are resolved.

## Layout

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── src/
```

## Vocabulary

Use canonical terms from `CONTEXT.md` in issue titles, proposals, tests, and
implementation. If a necessary concept is absent, resolve it through domain
modeling instead of silently inventing a synonym.

## Architectural decisions

Surface conflicts with existing ADRs explicitly. Do not silently override a
recorded decision.
