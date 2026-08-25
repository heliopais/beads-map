# Beads read model for Beads Map

Research date: 2026-08-25

## Decision

Beads Map should treat the installed `bd` 1.x CLI as its only Beads data
boundary. For each selected repository, a backend adapter should run short-lived
child processes with an explicit working directory and `--readonly`, consume a
complete current snapshot from `bd export` on stdout, and normalize that snapshot
into an app-owned model.

The first supported range should be `bd >= 1.1.0, < 2.0.0`. Beads 1.0.x has the
necessary JSON commands, but it does not provide the strict read-only guarantee
required by this product. In particular, an official 1.0.4 report demonstrates a
nominally read command deleting a passive JSONL export in an empty-embedded-store
edge case; the 1.1.0 release explicitly calls out that read-only operation is now
read-only through the embedded store.

The core snapshot command is:

```text
bd --readonly -C <repository> export
```

`bd export` emits one JSON object per issue and is explicitly documented for
interoperability. Each record includes labels, dependency records, and comments,
and the export spans all statuses. It is therefore a better consistency and
latency boundary than composing `list`, one `show` per issue, and one `comments`
call per issue.

At repository-open time, the adapter should also run:

```text
bd version --json
bd --readonly -C <repository> context --json
bd --readonly -C <repository> statuses --json
```

These calls gate the supported CLI major/minor, validate that the chosen directory
resolves to the expected Beads workspace, expose backend/project/schema identity,
and supply Beads' status vocabulary. They must not initiate `bd dolt pull`: Beads
Map displays current **local** state and does not silently cause network or merge
side effects.

## Normalized snapshot

The adapter, rather than the UI, owns all Beads-specific representation details:

- Work items come from every `bd export` record, including closed items.
- `labels` and `comments` are embedded arrays on each export record.
- The issue's raw `status` remains available. The product derives its five display
  states separately and preserves unknown future status strings instead of
  failing or coercing them.
- A dependency record is directed from `issue_id` to `depends_on_id`: the former
  depends on the latter.
- `parent-child` is structural. The child is `issue_id` and the parent is
  `depends_on_id`; it is not rendered as a blocking edge.
- In Beads 1.0.4's type model, `blocks`, `conditional-blocks`, and `waits-for` are
  blocking relationship types. Preserve the raw dependency type and metadata so
  later product decisions can render their distinct semantics without another
  storage migration. Other dependency types are associations, not DAG edges.
- Reverse/dependent adjacency is derived in memory from the complete set of
  dependency records; a second query is unnecessary.

The default export intentionally excludes infrastructure records and memories.
If a dependency endpoint is absent from the snapshot, use a bounded, short-lived
`bd --readonly -C <repository> show <id...> --json` call to hydrate only referenced
system nodes, recursively if required. This satisfies the product rule that a
path-relevant system record may appear compactly without loading all agent records
or sensitive memories via `export --all`.

Parsing must be tolerant at the boundary: ignore unknown fields, retain unknown
status/type/dependency strings, accept absent optional arrays as empty, and reject
a malformed record with a diagnostic that names the installed `bd` version. The
app should keep a small fixture/contract suite for each supported Beads minor.

## Change detection

There is no supported Beads HTTP event stream for this use case. Detect changes by
polling the same short-lived snapshot command, canonicalizing the parsed records
(stable issue and nested-array ordering), and comparing a content hash with the
last accepted snapshot. Only publish a new app snapshot when the hash changes.

Polls must be single-flight and time-bounded. A transient embedded-store lock,
schema migration, or concurrent write keeps the last good graph visible, marks it
stale, and retries with bounded backoff; manual refresh coalesces with any active
poll. Do not watch internal Dolt files or `.beads/issues.jsonl`, because neither is
a supported commit/change notification. Do not use `bd list --watch`: an official
open issue documents that the long-lived watcher holds the embedded-Dolt lock for
its lifetime and blocks other `bd` commands.

This strategy favors correctness over an unproven push channel. The polling
interval is a later implementation/performance choice, not part of the storage
contract.

## Alternatives considered

### CLI JSON commands — selected

Beads' v1.0.4 community-tool guidance explicitly tells tools to use the `bd` CLI
(`bd list --json`, etc.) for Dolt compatibility. The CLI owns repository discovery,
worktree redirects, backend selection, schema checks/migrations, locking, and the
current storage layout. `export` gives Beads Map a single complete snapshot while
remaining language- and architecture-neutral.

The adapter should capture stdout and stderr separately, impose a timeout, and
check the exit code before parsing. It should never invoke a write verb. Passing
`--readonly` is defense in depth and the explicit product invariant.

### Direct Dolt or `bd sql` — rejected

Raw tables are an internal schema, so a direct client would inherit migrations,
backend topology, connection discovery, transaction isolation, and lock ownership.
It would also bypass the storage layer. The installed `bd sql --help` warns about
that bypass, and `bd sql` in the local v1.0.4 embedded repository returns “not yet
supported in embedded mode.” A direct SQL adapter therefore cannot cover the
default embedded topology and server topology through one supported contract.

Beads exports a Go package, but its v1.0.4 `Open`/`OpenFromConfig` constructors use
`CreateIfMissing: true`; embedding it would couple the app to Go/internal storage
interfaces and would not enforce this product's no-create, no-migrate boundary.

### Passive `.beads/issues.jsonl` — rejected

The Beads README says Dolt is the source of truth and calls JSONL an export for
viewers/interchange, not the source of truth or a backup. The v1.0.4 community-tool
guide is stronger: tools reading the old JSONL file directly are not compatible
with current versions. The file may be absent, disabled, stale, or updated on a
different cadence, so it cannot drive either snapshots or change detection.

`bd export` also produces JSONL, but this is materially different: it asks the
current CLI/storage layer for a fresh snapshot on demand instead of trusting the
passive file.

### HTTP, MCP, or another API — rejected for the app data plane

The `bd` 1.x CLI does not expose a documented local HTTP/REST read service. The
separately installed `beads-mcp` server is documented as an alternative for
MCP-only environments without shell access; the installation guide recommends
the CLI for terminal/scripts and notes MCP's extra schema and latency overhead.
It adds a dependency and a tool-oriented, mutation-capable protocol without
improving snapshot consistency or change notification for a local web app.

## Compatibility contract

1. Refuse `bd < 1.1.0` with an upgrade message because strict embedded read-only
   behavior is part of the safety contract; refuse unknown major versions.
2. Record and surface `bd version --json`, `context.schema_version`, backend, and
   project identity in diagnostics, but never persist issue data outside the
   in-memory/current-view cache.
3. Test adapters against supported minor-version fixtures and real embedded-mode
   smoke tests. Add server-mode smoke tests before claiming server topology support.
4. Treat additive JSON fields and enum values as compatible. Treat missing required
   identity/edge fields, invalid JSONL, command failure, or schema rejection as a
   stale/error state while retaining the last good snapshot.
5. Re-evaluate the boundary for Beads 2.x rather than assuming CLI JSON compatibility
   across a major version.

## Primary sources

- [Beads v1.0.4 community-tool guidance](https://github.com/gastownhall/beads/blob/v1.0.4/docs/COMMUNITY_TOOLS.md#beads-community-tools)
- [`bd export` v1.0.4 implementation and command contract](https://github.com/gastownhall/beads/blob/v1.0.4/cmd/bd/export.go)
- [Beads v1.0.4 public Go constructors](https://github.com/gastownhall/beads/blob/v1.0.4/beads.go)
- [Beads v1.0.4 issue and dependency types](https://github.com/gastownhall/beads/blob/v1.0.4/internal/types/types.go)
- [Current Beads storage and JSONL statement](https://github.com/gastownhall/beads#-storage-modes)
- [Beads v1.1.0 release notes](https://github.com/gastownhall/beads/releases/tag/v1.1.0)
- [Official v1.0.4 report: a read command can mutate/delete passive JSONL](https://github.com/gastownhall/beads/issues/4033)
- [Official embedded `bd list --watch` locking report](https://github.com/gastownhall/beads/issues/3415)
- [Beads installation guide: CLI versus MCP](https://github.com/gastownhall/beads/blob/main/docs/INSTALLING.md)

## Local verification

The repository was inspected with `bd version 1.0.4`. In this embedded worktree:

- `bd --readonly export` returned all 9 current issues, 16 labels, 18 dependency
  records, and the existing comment in a single JSONL snapshot.
- Export records carried status, labels, complete dependency records (including
  `type` and metadata), and comments where present.
- `bd --readonly show <id> --json` returned parent/dependency/dependent context.
- `bd statuses --json` returned the built-in status vocabulary and schema version.
- `bd --readonly sql 'SELECT ...' --json` failed because SQL is unsupported in
  embedded mode, confirming that it is not a topology-independent interface.
