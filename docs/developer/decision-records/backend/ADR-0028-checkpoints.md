<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This work is made available under the terms of the
 Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
 which is available at
 https://creativecommons.org/licenses/by/4.0/legalcode.

 SPDX-License-Identifier: CC-BY-4.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0028: Checkpoints in TestLab

## Status

Proposed

## Date

2026-10-12

## Context

A TCK run is mostly the Test Suite calling the system under test (SUT) and
checking the answers. A few of its steps are different: the run cannot go on
until someone acts. The SUT has to call the Test Suite (`mock/wait/*`), has to
accept a call the Test Suite makes, or the operator has to choose
(`flow/select`, `connector/datasets/select`). These are the steps a person
running a certification has to know about before they start, and has to be
told about while the run is at them. We call them **checkpoints**.

The Catena-X engine introduced them first, outside TestLab (engine PR #242):

- `tck_moves.py` read a package and classified its steps by `uses`;
- `checkpoints.py` (`CheckpointFold`) folded the trace frames back onto that
  list, matching an event to a checkpoint by test id and step id, by `uses`
  in order for a nested step without an id, by the top-level step that last
  started for a step's end, and by comparing timeouts to tell a question
  resumed after a pause from a new attempt;
- `checkpoint_events.py` published `checkpoints.planned` and
  `checkpoint.updated` into the engine's stream.

All of that is a guess at facts the player has. The player knows which step is
running, which run of it this is, when it asks and when it is answered, and
how the step ended. The product decision is that checkpoints belong in
TestLab: steps declare them, the player follows them, and the engine consumes
what the player publishes.

## Decision

### 1. A step type declares a checkpoint on its decorator

`@step` takes a `checkpoint`, a typed `Checkpoint` with a `Direction`
(`models/primitives/checkpoint.py`):

```python
@step("mock/wait/http_request", checkpoint=Checkpoint(direction=Direction.INBOUND))
@step(
    "mock/wait/dataplane/http_request",
    checkpoint=Checkpoint(direction=Direction.INBOUND, via=Via.DATAPLANE),
)
@step(
    "notification/consumer/send",
    checkpoint=Checkpoint(direction=Direction.OUTBOUND, via=Via.DATAPLANE),
)
@step("flow/select", checkpoint=Checkpoint(direction=Direction.INTERNAL))
@step("connector/datasets/select", checkpoint=Checkpoint(direction=Direction.INTERNAL))
```

| Direction | Meaning | Steps |
|-----------|---------|-------|
| `inbound` | The SUT calls the Test Suite, and the Test Suite answers. | `mock/wait/http_request`, `mock/wait/dataplane/http_request` |
| `outbound` | The Test Suite calls the SUT, and the SUT has to be ready to answer. | `notification/consumer/send` |
| `internal` | The move happens inside the Test Suite: the operator decides, nothing is called either way. | `flow/select`, `connector/datasets/select` |

The decorator stamps `cls.checkpoint` on the class like it stamps `step_type`
and `dataspace_version`, so a subclass registered without one is not a
checkpoint because its parent was. The declaration is part of the step
contract (`BaseStep.describe()`, `testlab docs --json`) and of the generated
step reference.

The engine and its viewers read two older fields, `kind` and `via`. Both are
derived from the declaration, in one place:

| `direction` | `kind` | `via` |
|-------------|--------|-------|
| `inbound` | `wait` | `direct`, unless the step says `dataplane` |
| `outbound` | `wait` | as the step says, else `null` |
| `internal` | `select` | `null` (an internal checkpoint has no `via`) |

Flow steps say which `with:` keys carry steps and how they run them
(`nested_steps`): `flow/if`'s `then` and `else` are `conditional`,
`flow/retry`'s and `labs/flow/for_each`'s `steps` are `repeated`.

### 2. A test marks a step, or switches one off

A step's `checkpoint:` key, beside `if:` and `timeout_s:`:

```yaml
- id: push_certificate
  uses: http/http_request
  checkpoint:                       # this step is a checkpoint
    label: The SUT accepts the certificate
    description: Your connector answers the push with 2xx.
    direction: outbound             # only for a step type that declares none
    via: dataplane

- id: only_offer
  uses: flow/select
  with: { options: [the-only-one] }
  checkpoint: false                 # not this one, whatever its type declares

- id: note
  uses: util/log
  with: { message: Phase two starts }
  checkpoint: true                  # an outbound checkpoint, with no label
```

`true`, `false`, or a mapping (`CheckpointMark`: `label`, `description`,
`direction`, `via`). A mapping on a declared step relabels it; it cannot change
its direction or `via`, which the compiler refuses, as it refuses `via` on an
`internal` mark. A step type that declares nothing becomes an `outbound`
checkpoint unless the mark gives another direction. The key is in the JSON
Schema and is carried into the compiled IR.

### 3. Static inspection lists them in run order

`Tck.checkpoints(skip_tests=())` (ADR-0022's pattern: a frozen model,
`CheckpointEntry`, and a pure function, `authoring/_checkpoints.py`) lists
every checkpoint of the tests a run executes, in run order, the steps a flow
step carries depth first. `testlab inspect <package> --checkpoints
[--skip-tests a.yaml,b.yaml] [--json]` prints it.

```json
{"test_id": "wait-answered", "test_name": "wait-answered", "phase": "execution",
 "position": "execution/1", "step_id": "await_call", "uses": "mock/wait/http_request",
 "direction": "inbound", "kind": "wait", "via": "direct", "name": null,
 "label": "Push the certificate", "description": null, "timeout_s": 10,
 "conditional": false, "repeated": false}
```

`position` is where the step sits: `execution/2`, or `execution/2/then/0/steps/1`
inside flow steps. `label` and `description` are the mark's, else the step's
`with.action`'s; text still holding a `${{ }}` template is `null`. `timeout_s`
is the step's own, or its parameter model's default when the test gives none.

The player plans a run with the same function, so the list a briefing shows is
the list the run reports on, index for index. The run's plan then goes on with
the checkpoints of the tests `skip_tests` leaves out, already `skipped`: a
person may still run such a test on demand (`TckSession.run_test`), and what
it asks is then followed like any other checkpoint — at an index after the
briefing's, so no briefed index moves.

### 4. The player follows them and publishes two events

Every step runs in a frame (`player/checkpoints/frames.py`, a `ContextVar`):
its test, its position, which run of that position this is (`attempt`), and
the checkpoint it is. A flow step passes its nested steps their position
(`StepInvoker`'s `at`), so they have frames of their own. The
`CheckpointTracker` is told, by the runner and by the monitor right after it
published the event that says so, when a step starts and ends, when its
question is asked, paused and answered, when a test starts and ends, and when
the run ends. What it changes goes out at once:

| Event (wire, trace `type`) | `data.kind` | When |
|----------------------------|-------------|------|
| `checkpoints.planned` | `checkpoints_planned` | Once, after `job_started`, before the first test. Every checkpoint `ahead`; those of the tests `skip_tests` leaves out follow, `skipped`. |
| `checkpoint.updated` | `checkpoint_updated` | Right after the event that changed a checkpoint. One per changed checkpoint. |

`checkpoint.updated` keeps the engine's contract and adds `revision` (this
checkpoint's update count, so two updates never carry the same data) and
`cause` (the `kind` of the event that changed it):

```json
{"kind": "checkpoint_updated", "index": 0, "revision": 2,
 "cause": "step_received", "cause_sequence": 10,
 "checkpoint": {"test_id": "wait-answered", "step_id": "await_call", "direction": "inbound",
                "kind": "wait", "via": "direct", "label": "Push the certificate",
                "timeout_s": 10, "conditional": false, "repeated": false,
                "state": "cleared", "attempts": 1,
                "asked_at": "2026-10-12T08:31:37.292802Z",
                "answered_at": "2026-10-12T08:31:37.353380Z", "response_s": 0.06, "…": "…"}}
```

`cause_sequence` is the cause's `sequence` in the player's own trace, when it
writes one. A host that numbers events itself (the engine) reads `cause`: the
cause is the last event of that kind it published, since the update follows it
with nothing in between but other updates of the same cause. A change no event
announces — a nested step starting, a `flow/if` branch not taken — has neither.

The typed events are `CheckpointsPlannedEvent` and `CheckpointUpdatedEvent`;
they reach a host's monitor callbacks like every other event, and the trace
(`<data_dir>/<date>/<time>_<job>.jsonl`) gets the same `data`, under the
source `testlab/player/checkpoints`. A host registered with
`add_trace_callback` receives each with the envelope the trace wrote, its id
included (ADR-0016's amendment), as it does every exchange event.

### 5. States

The engine's states, and its rules, made exact
(`player/checkpoints/_transitions.py`):

| State | Meaning |
|-------|---------|
| `ahead` | Not asked yet. |
| `now` | Asked, and waiting for whoever has to act. |
| `cleared` | Answered, and its step completed. |
| `timed_out` | A question nobody answered before its step failed. |
| `failed` | Its step failed after the answer; or an `outbound` checkpoint whose step failed. |
| `skipped` | Its step was skipped, or not needed: a `flow/if` branch not taken, a choice of one option taken without asking, a test that passed without reaching it. |
| `not_reached` | Its test stopped before it, the run was cancelled, or the run ended first. |

- An `inbound` or `internal` checkpoint is asked by its step (`step_waiting`,
  `step_selecting`) and answered by it (`step_received`, `step_selected`).
  Any other checkpoint is asked when its step really runs — after `step_start`
  and its `if:`, so a step whose `if:` says no, or whose type is missing, was
  never asked (`skipped`, `not_reached`, `attempts` unchanged) — and answered
  when it completes.
- A call the mock turned away (`step_received` with `refused`) is no answer:
  the checkpoint stays `now`, and is `failed` when its step fails on it.
- `attempts` counts the asks. A question asked again after a pause is the
  same attempt: the frame says so, the event says how many pauses it has been
  through (`pauses`). A `flow/retry` that runs a checkpoint again asks a new
  attempt; so does a test run again, which first sets its checkpoints back to
  `ahead` (attempts go on counting). A test that is skipped is announced
  (`test_started`, then `test_completed` `SKIPPED`) without starting its
  checkpoints over. A question that is no checkpoint counts its pauses the
  same way.
- A test the run was interrupted in — cancelled mid-test (Ctrl-C, a host
  dropping a run), or an error the test did not catch — is not started again
  to be skipped when the session closes: it ends `CANCELLED` — in the trace
  `tck.test.failed` with `status: "CANCELLED"` and a `TEST_CANCELLED` error,
  never `tck.test.skipped` — and its checkpoints keep what they became
  (`cleared` stays `cleared`; the open question is `not_reached`).
- `response_s` is how long the question was open until it was answered —
  `waited_ms` of the answer, so the time the run was paused does not count.
- When the run ends, whatever is still `ahead` or `now` is `not_reached`.

### 6. Every exchange at a checkpoint names it

Every step event carries `attempt` and, at a checkpoint, `checkpoint:
{index, attempt, direction}`. That is how both halves of an exchange are found:

| Direction | How it went out | How it was answered |
|-----------|-----------------|---------------------|
| `outbound` | `step_call` (`tck.test.step.call`): `request` (method, URL, headers redacted, body) | the same event's `response` (status, headers, body, duration) |
| `inbound` | `step_received` (`tck.test.step.received`): `request` (method, path, headers redacted, body) | the same event's `response`: the Test Suite's answer, `status_code` and `body` — new |
| `internal` | `step_selecting`: the options offered | `step_selected`: the option chosen |

A call the mock turned away (no key, the wrong key) is now published as a
`step_received` too, with `refused` and the 401 it was answered with, before
the wait fails on it. Redaction is the existing one: headers by name, bodies
and query parameters by key.

A checkpoint's `checkpoint.updated` points at the exchange that cleared it by
`cause` / `cause_sequence`, and by `(index, attempt)`, which the exchange
carries.

### 7. Ids

Checkpoint events are named like every other (ADR-0016):
`<tck>/checkpoints/checkpoints.planned/<hash>` and
`<tck>/checkpoints/<index>/checkpoint.updated/<hash>`. ADR-0016 is amended so
that no two events of a run share an id: the data of an event that can repeat
at one place says which one it is (`attempt`, `pauses`, `occurrence`,
`revision`), and `logging.trace.event_id(tck, scope, type, data)` builds the
id for a host that writes an event of the run itself.

### 8. Who answers: the host, or an operator

The player never asks anyone anything on its own. `TestlabPlayer.run_tck` and
`open_session` — what the engine calls — do not prompt, read stdin or write a
window to stdout. The engine shows its own briefing before it starts a run and
answers a choice through `JobManager.selections`, as it always has.

`player/operator.py` is the seam for a host with a person at hand:
`run_with_operator(player, tck, operator)` shows an `Operator` the run's
checkpoints (`approve(checkpoints) -> bool`; no approval, no run:
`RunDeclined`) and puts every choice to it on a worker thread
(`choose(question) -> option id | None`), answering through the same question
board. The run cannot tell the two apart. `testlab run` brings a
`TerminalOperator`:

```text
================================================================================
  THIS RUN NEEDS YOU AT 2 CHECKPOINTS
--------------------------------------------------------------------------------
  Push the certificate
    1  await_push   inbound · your system calls us
       1m 00s to answer · Push the certificate to the Test Suite
  Choose the offer
    2  pick_offer   internal · you choose
       5m 00s to answer · only on some paths · may repeat · Pick the offer
================================================================================
Continue? [y/N]: y
Approved.
…
================================================================================
  CHECKPOINT 2 of 2 · YOU CHOOSE                                    4m 52s left
--------------------------------------------------------------------------------
  Pick the offer

     1  CCMAPI notification 3.0 · asset urn:uuid:7f3c… · Membership, FrameworkAgreement
     2  CCMAPI notification 3.0 · asset urn:uuid:a91e… · Membership
================================================================================
Choose [1-2] (4m 52s left, q to stop): 2
Chosen: 2 CCMAPI notification 3.0
```

- The window (`logging/window.py`) is pure ASCII — `=` rules, a `-` divider —
  at the terminal's width clamped to 60–100 columns; a row that does not fit is
  cut with an ellipsis, a paragraph is wrapped. The title row is bold where the
  run report is coloured (a terminal, `FORCE_COLOR`), never with `NO_COLOR`.
  The `ACTION REQUIRED` banner of a wait is drawn with the same window.
- `Continue? [y/N]` defaults to no. `--yes`/`-y` or `TESTLAB_YES` approves.
  Without a terminal and without it, the run stops, naming the flag.
- `Choose [1-N]` re-asks on anything but a number in range; `q` stops the run
  (its teardown runs, no further test starts); when the step's timeout runs
  out, the checkpoint times out as on any other path.
  `--choose <step_id>=<option id|n>` answers up front — the option with that
  id first, else the option numbered so; `--yes` never chooses.
- Exit codes: `0` passed, `1` failed, `2` the run could not get an answer (no
  terminal and no `--yes`/`--choose`, the input ended, a `--choose` value that
  names no option, or the operator could not be asked), `3` not approved, `4`
  stopped at a choice. A run with no checkpoints asks nothing.
- The briefing is asked before the event loop starts (`approve_run`), so a
  Ctrl-C at `Continue? [y/N]` ends the process at once. A choice is read in
  slices of 0.2 s — on a daemon thread where stdin cannot be `select()`-ed, a
  Windows console — so its deadline holds everywhere, and when the run ends or
  is interrupted while it is asked, the operator is stopped (`Operator.stop`)
  instead of being waited for: no prompt outlives the run, and none says it
  timed out when it was interrupted.
- While a window is up, the console's log lines from other threads wait
  (`logging.structured.hold_console`) and are written when it closes, so a
  `checkpoint.updated` line never lands inside the frame — on screen or in the
  transcript.
- What is shown goes to stdout, so the transcript has it; what the person typed
  is written back after it (`Approved.`, `Chosen: 2 …`).

## Where TestLab knows what the engine guessed

| The engine's fold | TestLab |
|-------------------|---------|
| Matched a nested step without an id by its `uses`, in order. | Knows its position from its frame. |
| Treated a repeated ask as a new attempt unless a `step_suspended` came first or the new timeout was shorter. | A re-ask in the same frame is the same attempt; a new frame (retry, restart) is a new one. |
| Closed a nested checkpoint when the flow step carrying it ended, as the flow step ended. | Closes it when the nested step itself ends, with its own outcome. A `flow/retry` checkpoint therefore shows each attempt: `now`, `timed_out`, `now`, `cleared`. |
| Marked a `flow/if` branch not taken `skipped` when the flow step completed, `not_reached` when it failed. | Marks it `skipped` the moment `flow/if` decides, whatever happens after — also a failure an earlier run of the same `flow/if` left there (a `flow/retry` whose next attempt took the other branch); a `cleared` one stays answered. |
| Called a select that failed while asked `failed`. | `timed_out` when nobody answered, `not_reached` when the run was cancelled. |
| Took `response_s` as `answered_at - asked_at`. | Takes the answer's `waited_ms`: pauses do not count. |
| Inferred "cancelled" from the end of the stream. | Reads the job's status (`JobManager.is_cancelled`); a cancelled run starts no further test, and their checkpoints are `not_reached`. |
| Listed `wait` and `select` only. | Adds `outbound` checkpoints (`notification/consumer/send`) and any step a test marks. `kind` stays `wait`/`select`; `direction` says which. |
| `timeout_s` only when the test wrote one. | The step's default otherwise. |

## What the engine changes to consume it

1. **Briefing** — call `Tck.checkpoints(skip_tests)` (or `testlab inspect
   --checkpoints --json`) instead of `tck_moves.package_moves`. The fields it
   reads are there under the same names; `direction`, `phase` and `position`
   are new. `kind` and `via` keep their values for `wait`/`select`; an
   `outbound` checkpoint is `kind: wait` too.
2. **Live checkpoints** — drop `CheckpointFold` and `CheckpointTrail`, and
   forward the player's `checkpoints.planned` / `checkpoint.updated` like any
   other monitor event. `GET /v1/jobs/{id}/checkpoints` is the last
   `checkpoint` per `index`. `CheckpointRead` ignores the new fields, or adds
   `direction`. `cause_sequence` is the player's trace sequence; a host that
   keeps its own numbering resolves the cause by `cause` (the last event of
   that kind).
3. **Ids** — register with `ExecutionMonitor.add_trace_callback` and store each
   event's `envelope["id"]` verbatim (ADR-0016's amendment): the engine's id,
   the trace file's id and the id the UI shows become one, and no data needs
   patching. Build the ids of the events the engine writes itself (a cancel
   after the runner is gone, a crash) with
   `tractusx_testlab.logging.trace.event_id`, instead of importing `_digest`
   (kept as an alias). A run whose player is gone still has its last
   `checkpoint.updated` per index in the stored trace; closing it means
   publishing `not_reached` for the ones still `ahead` or `now`, as the
   player's `job_ended` does.
4. **Uniqueness** — the player's payloads no longer repeat within a run
   (`attempt`, `pauses`, `occurrence`, `revision`), so `TraceIds`' occurrence
   numbering becomes a safety net rather than the rule.

## Consequences

- One definition of a checkpoint: the step type says it, the test can say
  otherwise, and the briefing, the run and the CLI read the same list.
- The states are facts, not inferences, and the engine loses three modules.
- Every step event grows by `attempt` and `checkpoint` (null off checkpoints).
  Consumers that compared payloads byte for byte see new fields; the select
  mechanism (`JobManager.selections`) is unchanged.
- `notification/consumer/send` is now a checkpoint: briefings of TCKs that
  push notifications list it.
- A cancelled run (`JobManager.cancel`) starts no further test. It used to run
  every remaining test after a cancellation.

## Alternatives considered

- **Keep the fold in the engine.** It is the status quo, and it is wrong in
  the cases above, which are exactly the ones a person reading a certification
  report cares about.
- **A `checkpoint` field on `BaseStep`, set in the class body.** One more way
  to declare step metadata; the decorator already carries `step_type` and
  `dataspace_version`.
- **An `actor` or `kind` on the declaration.** Two fields that can disagree;
  the direction alone says who acts and which way.
- **Prompt inside the player.** It would reach the engine, which has its own
  UI; the operator seam keeps the prompt in the CLI.
