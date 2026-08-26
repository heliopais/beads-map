# Beads Map

Beads Map is the product context for visually understanding work recorded in Beads without changing that work.

## Language

**Beads Map**:
A read-only visual companion for understanding work and dependency relationships recorded in Beads.
_Avoid_: Beads editor, issue manager

**Beads Map command**:
The user-facing `beads-map` CLI entry point that opens the local Beads Map application for remembered or supplied repositories. The Python script invocation remains a development and fallback entry point rather than the product command.
_Avoid_: `python3 beads_map.py`, desktop launcher

**Beads Map session**:
The lifetime of one foreground Beads Map command and its loopback-only local server. It normally opens the default browser and ends explicitly with `Ctrl-C`; browser tabs do not own its lifetime, and it is not a daemon or background service.
_Avoid_: Daemon, tray application, hosted session

**Beads repository**:
The single repository whose recorded work Beads Map displays at one time.
_Avoid_: Workspace, project

**Repository catalog**:
The locally remembered set of recent and pinned Beads repositories available for the user to switch between. It never combines their dependency graphs.
_Avoid_: Multi-repository graph, aggregated workspace

**Repository entry**:
One local working copy in the repository catalog, identified by its canonical real path. A Beads project identity validates continuity when the user relocates it but does not merge distinct working copies.
_Avoid_: Project, path alias

**Beads project identity**:
The stable identity reported by Beads for continuity checks. Different repository entries may share it while retaining separate local state.
_Avoid_: Repository path, catalog key

**Unavailable repository**:
A repository entry whose local working copy is currently missing or unreadable. It stays in the catalog for retry, relocation, or explicit removal, but no persisted graph is presented as current.
_Avoid_: Deleted repository, stale graph

**Repository validation**:
A read-only admission check that resolves a selected directory to a supported Beads repository and confirms its identity. It never initializes, migrates, repairs, or synchronizes Beads data.
_Avoid_: Repository setup, automatic repair

**Repository display name**:
The repository basename shown in routine UI, extended with the shortest parent suffix needed to distinguish same-named entries. The full local path is revealed only on explicit request.
_Avoid_: Full path, project identity

**Stale graph**:
The last successfully loaded graph retained after its repository can no longer be read safely. It remains inspectable but is clearly marked as not current.
_Avoid_: Current graph, cached repository

**Repository view**:
The presentation state remembered for one Beads repository: graph viewport, selected work item, and completed-work visibility.
_Avoid_: Global view, shared graph state

**Dependency graph**:
The directed view of blocking relationships among displayed Beads work items. Parent–child organization is not part of this graph.
_Avoid_: Task tree, hierarchy graph

**Work item**:
A human-facing Beads record represented as a normal dependency-graph node, including epics, features, tasks, bugs, chores, and decisions.
_Avoid_: Task, system record

**System node**:
A compact representation of a non-work Beads record shown only when it participates in a blocking path.
_Avoid_: Work item, hidden blocker

**Filter context node**:
A compact, muted work-item node retained when an active filter would otherwise hide an intermediate item and falsely break a dependency path between visible results.
_Avoid_: Shortcut edge, system node

**Unlinked work**:
Work items with no blocking-dependency edges. They remain visible in a labeled region of the default graph rather than being omitted.
_Avoid_: Orphaned work, hidden work

**Completed work**:
Work items closed in Beads. They remain connected in the default dependency graph but are visually de-emphasized.
_Avoid_: Hidden work, archived work

**Outstanding work**:
Work items not yet closed in Beads, regardless of whether they are ready, blocked, deferred, or in progress.
_Avoid_: Open tasks

**Execution state**:
Beads Map's derived classification of a work item as Completed, In progress, Ready, Blocked, or Deferred. It answers how work can move, while raw Beads status remains supporting detail.
_Avoid_: Status

**Epic roll-up**:
An informational `completed / total` count over an epic's direct human-facing child work items. Deferred children remain incomplete, system records are excluded, and the count never overrides the epic's own Beads status; epics without children have no roll-up.
_Avoid_: Progress percentage, estimate roll-up, derived epic status

**Graph workspace**:
The primary Beads Map surface, combining repository selection, a compact execution summary, separate epic context, the dependency graph, and details for the selected work item.
_Avoid_: Dashboard, report

**Graph search**:
A graph-preserving locator across work-item ID, title, labels, assignee, and description. It highlights and navigates matches without removing nonmatching nodes or changing dependency topology.
_Avoid_: Search filter, query view

**Graph filter**:
An explicit narrowing of visible work by execution state, work-item type, label, or assignee. Choices within a facet combine with OR and facets combine with AND; active filters remain visible and never create synthetic dependency edges.
_Avoid_: Graph search, implicit filter

**Path focus**:
A reversible emphasis mode for the selected work item: all transitive upstream blockers, all transitive downstream dependents, or both. Unrelated nodes are dimmed rather than removed, preserving layout and orientation.
_Avoid_: Graph filter, neighborhood

**Scale gate**:
An explicit choice shown when a repository exceeds the first release's supported graph envelope of 1,000 displayed nodes or 3,000 dependency edges. It reports complete snapshot counts and recommends an outstanding-work filter without silently dropping work.
_Avoid_: Automatic truncation, hidden limit

**Graph virtualization**:
An implementation technique that may omit offscreen drawing work without changing the loaded graph's counts, search, filters, keyboard navigation, path focus, or dependency calculations.
_Avoid_: Clustering, data omission
