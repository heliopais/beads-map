# Beads presentation demo runbook

This runbook supports the three-minute live section of the 15-minute AI Engineering Fridays talk. The demo uses the real `beads-map` repository and the presentation bead itself, so the audience sees durable work state rather than a staged toy project. The write-shaped example uses `--dry-run`; it demonstrates how discovered work would be linked without changing the repository during the talk.

## 1. One-minute summary

The demo tells one compact story: a fresh session restores the project's working conventions, finds available work, inspects one bounded task, and records a newly discovered follow-up with provenance. Beads Map then turns that durable task state into a visible hand-off.

Budget three minutes:

- 0:00–0:35 — restore context with `bd prime`
- 0:35–1:05 — find work with `bd ready`
- 1:05–1:55 — inspect the presentation task with `bd show beads-map-box`
- 1:55–2:25 — preview a discovered follow-up with `bd create --dry-run`
- 2:25–3:00 — switch to Beads Map and show the selected task and its children

## 2. Before the session

From `/Users/paishe01/repos/mngmt/beads-map`:

```bash
git status --short
bd doctor
bd show beads-map-box
python3 beads_map.py --port 8877 --no-browser .
```

Then open [http://127.0.0.1:8877](http://127.0.0.1:8877), select `beads-map-box`, choose the direct focus, and leave the browser ready behind the terminal. Increase terminal text size until it is readable from the back of the room. Close unrelated tabs and notifications.

## 3. Live path

### 3.1 Restore the repository context

```bash
bd prime
```

Narration: “Imagine this is tomorrow morning—or a new agent session. The chat is gone. `bd prime` restores the repository's workflow and the conventions the next session must follow.”

Do not read the output line by line. Point out the context-recovery purpose, essential commands, and completion protocol.

### 3.2 Find unblocked work

```bash
bd ready
```

Narration: “This is different from rereading a planning document and inferring what remains. Beads queries the current graph and shows work with no open blockers.”

### 3.3 Inspect one durable unit of work

```bash
bd show beads-map-box
```

Narration: “This presentation is itself a bead. Its goal, status, acceptance criteria, design decisions, and child tasks survive every conversation. A new session does not need me to reconstruct the story.”

Pause briefly on the child work: story, deck, demo, and rehearsal. Mention that the approved talk flow was recorded in the bead rather than left only in chat.

### 3.4 Preview discovered work with provenance

```bash
bd create \
  --title="Follow up on audience feedback" \
  --description="Capture concrete friction and useful patterns reported after the AI Engineering Fridays demo." \
  --type=task \
  --priority=2 \
  --deps discovered-from:beads-map-box \
  --dry-run
```

Narration: “Suppose the demo exposes a follow-up. I do not bury it in a checkbox or derail the current task. I capture it as its own bead and preserve where it came from. `--dry-run` keeps today's demo read-only.”

### 3.5 Make the hand-off visible

Switch to the prepared browser tab.

Narration: “Beads is the task and memory layer. Beads Map is simply a view over it. Here is the presentation task, its children, its status, and the details another session would need. The map itself was built through the same graph you are looking at.”

Point to only three things:

1. The selected `beads-map-box` task.
2. Its outgoing links to the four pieces of work.
3. The details panel containing durable context.

Then return directly to slide 7.

## 4. Fallback path

If the local server or browser misbehaves, stay in the deck. Slide 7 contains the prepared presentation-task view, and slide 8 contains the completed release-hardening subgraph. Say: “The live UI has volunteered to demonstrate why durable state matters. The screenshots come from this repository today; the CLI state we just inspected is the same data.”

If the terminal is the problem, stay on slide 6 and narrate the four commands shown there, then continue to slide 7. Do not spend presentation time debugging projectors, ports, fonts, or browser zoom.

## 5. Rehearsal checks

- Keep the complete talk between 13 and 14 minutes so questions fit inside the 15-minute slot.
- Keep the live demo below three minutes.
- Verify slide 8's “49 completed beads” figure shortly before presenting; update the wording if the repository history changes.
- On slides 9–10, say “JSONL compatibility workflow,” not “native Beads sync”; keep the local-Dolt-versus-Git-export distinction explicit.
- Test terminal font size, browser zoom, and the local port on the presentation machine.
- Keep [When the plan outlives the session - v5.pptx](</Users/paishe01/repos/mngmt/beads-map/presentation/When the plan outlives the session - v5.pptx>) available as the complete slide-based fallback.

## 6. Intended audience takeaway

The audience should leave with one precise idea: use Beads when the work—not merely the current chat—needs continuity across sessions, discoveries, dependencies, or hand-offs. Markdown planning remains useful for bounded work; Beads becomes valuable when the plan starts behaving like a stateful task system. At StepStone, asynchronous team hand-offs travel as exported JSONL with the code while each clone keeps its own local Dolt database.
