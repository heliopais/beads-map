# Issue tracker: Beads

Issues for this repository live in its local Beads database and are managed
with the `bd` CLI. The Dolt-backed database under `.beads/` is canonical.
Use `bd dolt push` and `bd dolt pull` to synchronize issue data.

External pull requests are not part of the triage queue.

## Conventions

- Use `bd` for all task tracking.
- Store the issue question or requested outcome in its description.
- Record discussion and resolution details as issue comments.
- Apply triage labels according to `docs/agents/triage-labels.md`.
- Use non-interactive commands; never invoke `bd edit`.
- Use issue titles—not bare IDs—when referring to issues in human-readable text.

## Common operations

- Create: `bd create --title "<title>" --description "<body>" --type <type>`
- Fetch: `bd show <id>`
- Search: `bd search "<query>"`
- List ready work: `bd ready`
- Claim: `bd update <id> --claim`
- Comment: `bd comments add <id> "<comment>"`
- Close: `bd close <id> --reason "<reason>"`
- Synchronize: `bd dolt pull` and `bd dolt push`

## Wayfinding operations

- Create a map as an epic labelled `wayfinder:map`.
- Create each ticket with `--parent <map-id>` and one of:
  `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`,
  or `wayfinder:task`.
- Create every ticket first, then wire dependencies in a second pass with
  `bd dep add <blocked-id> <blocker-id>`.
- List all map tickets with `bd children <map-id>`.
- Query the frontier with:
  `bd list --parent <map-id> --status=open --ready --no-assignee --sort=priority`.
- Claim a frontier ticket before working through it:
  `bd update <ticket-id> --claim`.
- Record a resolution with `bd comments add`, then close the ticket.
- Use `[Ticket title](beads:<ticket-id>)` as the stable context pointer until
  the project provides browser URLs for Beads issues.
- Append only the resolution gist and context pointer to the map's
  `Decisions so far`; the complete answer remains on the ticket.
- Run `bd dep cycles` after wiring dependencies.
