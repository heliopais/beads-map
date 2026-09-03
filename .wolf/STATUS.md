# STATUS — beads-map

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Update this file at the end of every work phase so the next `/clear` resumes in 1 read.
> Last updated: 2026-09-03

---

## ✅ Done

<!-- Move items here from "🚀 Next phase" when finished. Group by area. -->

- Initialized Beads as the canonical issue tracker and OpenWolf as the context-management layer.
- Configured engineering skills for Beads, default triage labels, and single-context domain documentation; recorded completion in `Configure engineering skills for Beads`.
- Configured and pushed the Beads Dolt remote through the repository's GitHub origin.
- Built and verified a dependency-free, one-repository Beads graph POC with read-only loading, a status-coded DAG, refresh, and selected-item details; recorded completion in `Build the simple read-only dependency graph POC`.
- Added explicit direct-file launch guidance so opening `web/index.html` no longer fails with an unexplained fetch error.
- Confirmed the POC works against a second Beads repository and added dependency-free zoom in, zoom out, and viewport Fit controls for larger graphs.
- Added persistent multi-repository support: a local paths-only catalog, last-selection restoration, header switching, and Add/Remove controls while retaining one isolated DAG at a time.
- Replaced manual absolute-path entry with the native macOS folder chooser for adding repositories.
- Added interactive filters for Completed, In progress, Ready, Blocked, and Deferred work, including visible counts and a Show all reset.
- Added mouse navigation: drag empty canvas space to pan and Cmd-drag vertically to zoom around the pointer, without interfering with node selection or the existing zoom/Fit controls.
- Improved dense DAG readability with crossing-aware task ordering, roomier rows and columns, and orthogonal dependency routes whose vertical turns stay in column gutters.
- Defined minimal progress semantics for the eventual product: execution-state counts only, plus optional direct-child `completed / total` epic roll-ups that include deferred work as incomplete, exclude system records, and remain independent of raw epic status.
- Defined the CLI lifecycle and distribution contract: an `uv tool`-installed `beads-map` foreground command, loopback server with implicit free-port fallback, browser auto-open, catalog-first repository launch, explicit upgrades, `Ctrl-C` shutdown, and macOS-first support.
- Completed all seven Wayfinder decisions and consolidated the build-ready first-release product and technical contract in `docs/specification.md`.
- Chose the minimal implementation architecture: one foreground Python process, native SVG, and at most three focused Python responsibilities with no additional framework.
- Packaged the working POC as the dependency-free `beads-map` 0.1.0 uv tool, including its web asset, source fallback, port behavior, Beads version diagnostic, and standard-library tests.
- Migrated the designated Beads database from schema v32 to v53, restored its 18 recorded relationships, audited 12 additional implementation/provenance links, and updated Beads Map 0.1.1 to distinguish prerequisite, follow-on, and hierarchy edges without changing blocked-state semantics.
- Hardened Beads Map 0.1.2 with serialized canonical snapshots, five-second hash polling, visible stale-last-good fallback, locked atomic catalog merging, and per-repository view restoration; 18 tests, wheel smoke, and live browser verification pass.
- Added Beads Map 0.1.3 locate-only graph search with title/ID matches, match highlighting, previous/next and keyboard cycling, filter-preserving navigation, and clean tab-disconnect handling.
- Added Beads Map 0.1.4 direct relationship context: selecting a bead highlights upstream and downstream neighbors and connecting edges, fades unrelated work without relayout, and restores normal styling when cleared.
- Added Beads Map 0.1.5 relationship keyboard navigation: Left/Right enter direct upstream/downstream choices, Up/Down cycle them, and the opposite horizontal direction returns to the starting bead.
- Added Beads Map 0.1.6 repository-derived work-type filters that combine with status visibility, share one reset, and persist per repository.
- Added Beads Map 0.1.7 direct-child epic progress: epic nodes and details show closed/total human-facing children without percentages, weighting, recursion, or status override.
- Added Beads Map 0.1.8 filtered-empty guidance: the canvas distinguishes filters hiding all work from a repository that genuinely has no work, while Show all restores the graph.
- Added Beads Map 0.1.9 epic sub-maps: double-clicking an epic scopes the canvas to that epic and its recursive child work, with a compact return to the full repository graph.
- Added Beads Map 0.1.10 epic sub-map discovery cues: the graph header explains the interaction and each epic exposes a compact mouse- and keyboard-operable `⤢` control.
- Fixed Beads Map 0.1.11 epic sub-map filter isolation: sub-maps start with all statuses and types visible, and Back restores the prior full-map filters.
- Added Beads Map 0.1.12–0.1.17 exploration improvements: compact epic overview, What’s ready preset, interactive minimap, transient refresh-change cues, richer relationship-aware details, and current-scope SVG export.
- Shipped Beads Map 0.2.0 safe metadata editing: explicit five-field Edit/Save/Cancel, an allowlisted `bd update` endpoint, optimistic conflict protection, canonical refresh, draft retention, isolated browser verification, and updated product documentation.
- Added Beads Map 0.2.1 label and assignee facets plus expanded ID/title/description/label/assignee search; facet selections compose with existing filters and persist per repository.
- Added Beads Map 0.2.2 transitive prerequisite path focus with Direct, Blockers, Dependents, and Both modes that preserve the current layout and filter scope.
- Added Beads Map 0.2.3 path-preserving filters: hidden prerequisite intermediaries remain as compact, inspectable Filter context cards without changing match counts or inventing relationships.
- Added Beads Map 0.2.4 stable in-memory layouts per repository/scope, component-aware topology updates, viewport anchoring, and an explicit Re-layout action.
- Added Beads Map 0.2.5 complete read-only work definitions in details: acceptance criteria, design, notes, and timestamped comments, with safe omission of absent fields.
- Added Beads Map 0.2.6 recoverable unavailable repository entries: missing or invalid catalog paths remain visible with Retry and Locate controls, failed switches preserve the current graph, and locating a replacement migrates saved view state.
- Added Beads Map 0.2.7 browser scale verification and an explicit large-graph gate: normal rendering supports up to 1,000 displayed issues/3,000 relationships, larger scopes recommend filtering and offer an explicit best-effort override.
- Completed and closed the seven-child `beads-map-6vs` release-hardening epic.
- Added the first GitHub Actions CI gate: pull requests and pushes to `main` run the Python 3.11 unit suite, build distributions, and smoke-test the installed wheel/CLI with minimal permissions, cancellation of superseded work, and immutable action pins; the first hosted run passed all steps in 21 seconds.
- Opened the five-child `beads-map-l8m` external-beta epic and completed its onboarding front door: the README now leads with an authentic product screenshot, an honest invited-beta audience and platform boundary, a three-step quickstart, local-data/edit safety, and focused troubleshooting.
- Added Beads Map 0.2.8 guided empty first run: a semantic, responsive three-step welcome keeps repository choice primary, explains graph exploration and the five-field edit boundary, and remains visible alongside actionable add failures.
- Created and visually verified the StepStone-branded eight-slide AI Engineering Fridays deck `presentation/When the plan outlives the session - v1.pptx`, including speaker notes, authentic Beads Map screenshots, and a three-minute deterministic demo runbook.
- Revised the talk opening in `presentation/When the plan outlives the session - v2.pptx` around Steve Yegge's original Beads launch essay: 605 decaying Markdown plans, his issue-graph terminal screenshot, visible attribution, and an explicit historical-architecture caveat in the speaker notes.
- Reworked the presentation opening in `presentation/When the plan outlives the session - v3.pptx`: the familiar Claude Code loop now opens the talk, Steve Yegge's complex-work example follows, and the exact “The Stages of AI Adoption” slide from the prior sprint review bridges into the session-boundary pressure points. The nine-slide deck, speaker notes, preview, and demo slide references are verified.
- Added the evidence-backed team-repository answer in `presentation/When the plan outlives the session - v4.pptx`: slide 9 presents Beads collaboration as a qualified yes with a Git-like local-Dolt/pull/push model, explicit synchronization caveats, and official-source notes; the closing slide is now slide 10 and the deck passed visual, overflow, and template-fidelity checks.
- Corrected the collaboration section for StepStone's Bitbucket/Stash environment in `presentation/When the plan outlives the session - v5.pptx`: slide 9 now shows local Dolt → export → Git-tracked `.beads/issues.jsonl` → import → local Dolt, slide 10 demonstrates a pull-request hand-off in practice, and the closing is slide 11. The deck and notes explicitly call this a JSONL compatibility convention rather than native Beads remote sync and pass full presentation QA.
- Replaced slide 2's mismatched terminal visual in `presentation/When the plan outlives the session - v6.pptx` with a first-party screenshot of Steve Yegge's original “605 markdown plan files” passage. The slide retains its StepStone styling, explicitly treats the screenshot as source evidence in its notes, and passes visual, overflow, exported-PPTX, and template-fidelity checks.

---

## 🚀 Next phase

**Goal:** Complete the external-beta children of `beads-map-l8m`; local HTTP origin hardening is the next prerequisite for automated browser and real-Beads confidence checks.

**Presentation:** Rehearse the 15-minute Beads talk, tighten the talk track from live timing, verify the “49 completed beads” evidence immediately before delivery, and choose the 2026-09-04 or 2026-09-18 slot.

### Closed decisions
- Beads is the canonical issue tracker; OpenWolf manages project context.
- Default triage label names are used.
- Domain documentation uses a single root context.
- The Wayfinder destination is a build-ready product and technical specification, not an implementation.
- The first release is a read-only explorer; issue mutations are outside its boundary.
- The first release displays one Beads repository at a time; aggregation is outside its boundary.
- Beads Map runs as a local web application launched from the CLI inside or against a Beads repository.
- The primary DAG shows prerequisite, follow-on provenance, and hierarchy as distinct edge styles; only prerequisites affect execution state, while epics remain distinguished through node styling.
- Human-facing work types are normal nodes. Infrastructure, templates, memories, and agent records are hidden unless required as compact system nodes to preserve a blocking path.
- Closed work remains connected and visually de-emphasized by default, with a quick control to hide it.
- The overview derives five execution states—Completed, In progress, Ready, Blocked, and Deferred—while preserving raw Beads status in item details.
- The graph workspace is the primary landing surface; it combines the DAG with a compact progress summary and in-context work-item details.
- The primary user is a developer or maintainer supervising agent-assisted work and asking what is done, blocked, or ready next.
- Users can switch among known Beads repositories, but only one repository and one dependency graph are active at a time; graphs are never aggregated.
- Launching from a repository adds it to a local recent/pinned catalog; users may also add one through a directory picker, and the app does not scan the machine recursively.
- The active graph refreshes automatically when Beads changes while preserving view state; last-updated, refresh-error, and manual-refresh affordances remain visible.
- The first release visualizes current Beads state only; historical snapshots, playback, and time travel are outside its boundary.
- The default graph includes all human-facing work, including completed, deferred, and unlinked items; search locates without filtering, explicit filters preserve paths with compact context nodes, and path focus can show blockers, dependents, or both.
- Graph exploration preserves node positions; dependency changes incrementally relayout affected components. The supported envelope is 1,000 displayed nodes/3,000 edges, larger graphs receive an explicit scale gate, semantic clustering is excluded, and invisible virtualization must preserve full-graph behavior.
- Repository entries identify local working copies without merging distinct copies; missing or invalid entries remain recoverable. Catalog paths stay local, issue data is not persisted, Beads Map mutates only the five allowlisted metadata fields through `bd update`, and failed reads retain only a visibly stale in-memory graph.
- Progress reporting is unweighted and count-based: no overall completion percentage; epic roll-ups count closed direct human-facing children over all direct human-facing children, including deferred work as incomplete, and never replace raw epic status.
- The public `beads-map` command is installed and upgraded through `uv tool`, runs a foreground loopback server, opens the browser, falls back from an occupied implicit port, restores or accepts repositories, stops with `Ctrl-C`, and is officially macOS-first without automatic update checks.

### Open decisions
- None required for the completed 0.2.0 metadata-editing boundary.

---

## 📁 Active architecture

- **POC runtime:** Python standard-library local HTTP server plus dependency-free HTML/CSS/JavaScript.
- **Distribution contract:** Package the app as an `uv tool` exposing `beads-map`; retain the Python script as a source fallback and require explicit user-driven upgrades.
- **Data source:** Beads issues and their native dependency graph in a local Dolt database.
- **Read boundary:** Short-lived `bd --readonly -C <repository> export` snapshots with targeted `show --json` hydration; require Beads `>=1.1.0,<2.0.0`.
- **Refresh:** Poll and canonical-hash snapshots; do not use direct Dolt/SQL, passive JSONL, long-lived `--watch`, implicit sync, or MCP as the data plane.
- **Current scope:** One active repository-scoped graph at a time, with a persistent paths-and-view-metadata catalog, native macOS add picker, header switching, epic overview and descendant sub-maps, locate-only title/ID search, direct relationship emphasis/navigation, execution-status/type filters plus a Ready preset, direct-child epic progress, distinct relationship edges, crossing-aware layout, pan/zoom/Fit and minimap navigation, hash refresh with stale recovery and transient change cues, rich details, browser-side SVG export, and explicit editing of title, description, priority, assignee, and labels. No aggregation, recursive or weighted roll-ups, additional filter facets, historical persistence, workflow/relationship mutation, creation/deletion, or sync.
- **Accepted workspace frame:** Repository switcher in app chrome, compact execution summary, separate epic context, graph-first canvas, and an in-context selected-item detail panel.
- **Accepted graph layout:** Layered left-to-right from blockers to dependent outcomes; preserve positions across refresh, support pan/zoom and explicit re-layout, and omit persisted manual node arrangement.
- **Accepted visual encoding:** Execution state uses border accent plus icon and text; type uses a text label with stronger epic accent; completed nodes retain legibility at reduced contrast; selection and its dependency path receive high-contrast emphasis.
- **Accepted inspection model:** Node activation opens in-context details; wide screens use a side panel and narrow screens place details below; relationship-aware arrow keys navigate nodes, Escape clears selection, and assistive output announces type, state, and relationship.
- **Accepted repository switching:** Each repository restores its own viewport, selection, and completed-work visibility; failed switches preserve the current graph.
- **Accepted graph exploration:** Whole-repository default scope; graph-preserving search; explicit state/type/label/assignee filters with compact path context; direct-neighbor selection plus transitive Blockers/Dependents/Both focus.
- **Accepted stability and scale:** Exploration never relayouts; dependency changes incrementally relayout affected components; 1,000-node/3,000-edge supported envelope with a scale gate above it; no semantic clustering; implementation-level virtualization preserves full-graph semantics.
- **Accepted repository safety:** Canonical local-working-copy identity with Beads identity continuity checks; recoverable unavailable entries; local private catalog metadata without issue snapshots; read-only validation; complete expected-project snapshot replacement; no interference with Beads writers.
- **Accepted implementation architecture:** One foreground Python process with standard-library HTTP, packaged vanilla web assets, and native SVG; at most three direct responsibilities for CLI/server, Beads snapshots, and catalog persistence; no framework or extra layering without a measured need.

---

## ⚠️ External blockers (don't block coding)

- None currently known.

---

## 🔧 Useful commands

```bash
bd ready
bd children <map-id>
bd dep cycles
bd dolt push
```

---

## 📚 References (read IF needed)

- `.wolf/cerebrum.md` — User Preferences + Do-Not-Repeat + Decision Log
- `.wolf/anatomy.md` — token-efficient file index
- `.wolf/buglog.json` — known bugs + fixes
