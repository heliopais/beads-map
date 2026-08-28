# Metadata Editing Plan

Status: Planned
Tracking epic: `beads-map-bz4`
Target release: Beads Map 0.2.0

## Outcome

Beads Map will support an explicit edit mode for five metadata fields on the
selected bead: title, description, priority, assignee, and labels. Beads remains
the source of truth and `bd update` remains the only issue writer. The graph is
updated only from the canonical snapshot returned after a successful write.

This is the first intentional mutation boundary in an application that has so
far been read-only. The implementation therefore favors a narrow allowlist,
clear user intent, and observable failure over a generic issue-editing API.

## Scope

The first release edits:

- title — required, trimmed, and non-empty;
- description — free text and allowed to be empty;
- priority — one of P0 through P4;
- assignee — optional text, with an explicit unassigned value;
- labels — a deduplicated exact set, including the empty set.

The first release does not create or delete beads, change ID or type, claim,
close, reopen, defer, change status, edit parent/dependency relationships, run
sync, or expose arbitrary `bd` flags. Those operations require separate product
decisions because they have stronger workflow or graph consequences.

## User interaction

The normal details panel remains a viewer. An explicit **Edit** action replaces
the five approved values with accessible controls prefilled from the selected
node. **Cancel** returns to view mode without a request. **Save** validates and
submits the draft once; repeated submission is disabled while it is in flight.

Entering edit mode records the active repository, selected bead ID, and current
snapshot hash. Auto-refresh may continue updating the graph, but it never
rewrites an active form. If the snapshot changes, the form indicates that its
base is stale. Save then receives a conflict response and retains the draft so
the user can explicitly reload current values or cancel.

After a successful save, the client applies the server's fresh canonical graph,
keeps the existing viewport and scope where possible, reselects the edited bead,
returns the panel to view mode, and shows a short **Saved** confirmation. A
validation or `bd` failure leaves both the last good graph and the draft intact.

Switching repository, changing epic scope, or selecting another bead while a
draft differs from its original values requires an explicit discard decision.
An unchanged draft may be dismissed silently.

## Server contract

The local server adds `POST /api/issues/update`. It accepts JSON shaped as:

```json
{
  "repository": "/canonical/selected/repository",
  "issueId": "project-123",
  "snapshotHash": "expected-current-hash",
  "fields": {
    "title": "Updated title",
    "description": "Updated description",
    "priority": 2,
    "assignee": "Person or empty string",
    "labels": ["label-a", "label-b"]
  }
}
```

The endpoint requires same-origin browser behavior plus `X-Beads-Map: 1`. It
rejects unknown top-level keys and field names, malformed or oversized JSON,
repository paths other than the currently selected catalog entry, issue IDs
that are not in the refreshed snapshot, and invalid field values.

Before writing, the server refreshes the selected repository and compares its
hash with `snapshotHash`. A mismatch returns HTTP 409 with the fresh hash and a
concise conflict message; it performs no application-initiated write. The check
prevents ordinary stale-form overwrites. It cannot make an external `bd` command
that races in the tiny interval after the check transactional, but Beads remains
responsible for database locking and integrity.

For a valid request, the server constructs one subprocess argument list for
`bd -C <repository> update <issue-id>`; it never invokes a shell. Scalar fields
map only to their corresponding allowlisted flags. Label additions/removals are
computed against the refreshed node so the requested exact set, including no
labels, can be expressed without a generic command escape hatch. A successful
command is followed by a forced canonical snapshot refresh. The response
contains that graph and snapshot hash.

Expected response classes are:

| Status | Meaning | Client behavior |
| --- | --- | --- |
| 200 | Saved and refreshed | Apply graph, reselect bead, show Saved |
| 400 | Malformed or invalid fields | Keep draft and show field/general error |
| 403 | Missing mutation header | Keep graph; reject request |
| 404 | Selected repository or bead no longer available | Keep graph and draft |
| 409 | Snapshot changed since edit began | Keep draft; offer reload or cancel |
| 500 | `bd` write or refresh failed | Keep last good graph and draft |

## Safety and consistency rules

- The selected catalog repository is authoritative; a request cannot nominate
  an arbitrary working copy.
- The issue must exist in the immediately refreshed snapshot.
- Only the five documented fields cross the mutation boundary.
- Commands use subprocess argument arrays with no shell interpolation.
- The server does not write Dolt tables or `.beads/issues.jsonl` directly.
- Failed or partial reads never replace the last good graph.
- The mutation endpoint is serialized with snapshot access inside the one
  foreground process; concurrent Save clicks are also disabled in the client.
- Logs and errors use the existing path-redaction rules.
- No issue snapshots or edit drafts are persisted by Beads Map.

## Verification

Python tests cover request size and parsing, header/repository/issue checks,
field validation, command argument construction, exact label-set changes,
stale-hash rejection, `bd` failure, refresh failure, and successful canonical
response. Existing snapshot, catalog, and graph normalization tests remain
green.

Browser checks run against an isolated temporary Beads repository and cover all
five fields, empty optional values, Save, Cancel, duplicate-submit protection,
auto-refresh during editing, stale conflict with draft retention, failed write,
repository/scope/selection discard protection, graph reselection, and the narrow
layout. The test repository is disposable and no real project issue is mutated.

The boundary change ships as 0.2.0. README, package description, details-panel
wording, and `docs/specification.md` will state precisely which metadata is
editable and which operations remain read-only.

## Delivery sequence

| Bead | Deliverable | Dependencies |
| --- | --- | --- |
| `beads-map-bz4.4` | Allowlisted mutation endpoint and Python tests | None |
| `beads-map-bz4.2` | Explicit Edit/Save/Cancel details UI | None |
| `beads-map-bz4.3` | Conflict-safe save, refresh, draft retention, and feedback | `.4`, `.2` |
| `beads-map-bz4.1` | Isolated browser verification, documentation, packaging, and 0.2.0 release | `.3` |

The backend and form can be developed independently. Integration begins only
after both contracts exist, and the release task remains blocked until the full
round trip is complete.
