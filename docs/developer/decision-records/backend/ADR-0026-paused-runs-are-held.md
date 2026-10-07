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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0026: Paused Runs Are Held

## Status

Accepted

## Date

2026-09-29

## Context

A running job can be paused (`JobManager.pause`) and resumed. Until now a pause
was a gate: the phase runner waited on an `asyncio.Event` before each setup and
execution step. The step in flight was not touched, and nothing the run had
published to the outside was withdrawn.

That was enough for a run that only calls out. It is not enough for one the
system under test (SUT) calls back into, which is most of the TCKs that
matter. In a push test such as CX-0135's
`validate_certificate_push.yaml`, the run:

1. registers a mock (`mock/api`) and offers it on the engine connector
   (`connector/provider/create_mock_asset`, a policy,
   `connector/provider/create_contract_definition`);
2. blocks on `mock/wait/dataplane/http_request`, with a timeout, until the SUT
   negotiates that offer and calls the mock through its data plane.

Paused during step 2, the run showed "PAUSED", but the offer stayed in the
catalog and the mock kept answering. The SUT could negotiate and call as if
nothing had happened. The wait kept counting its timeout on the server, so
the timeout could expire while the run was paused, and the step failed as soon
as the run was resumed. The operator saw a paused run with a clock still
running, and that clock was right: the backend really was still waiting. What
an operator means by pause is that the run stops, and that the SUT cannot use
it until they press play.

## Decision

**A paused run is held.** Once it stops, it behaves toward the SUT like a run
that is not going: its offers are withdrawn and its mocks do not answer. On
resume it puts back what it withdrew, and a wait carries on for the time it
had left.

### What is withdrawn

- **Contract definitions the run created.** They are withdrawn, and nothing
  else on the connector is. A contract definition is what makes an asset appear
  in the catalog. Without it the SUT finds nothing to negotiate. The assets
  and policies stay, so putting the offer back is one create call, not a
  re-provisioning, and nothing breaks for agreements that already reference
  the asset.
- **The run's mocks.** They answer 404, and the call neither resolves a wait nor
  fails one. This covers what withdrawing the offer does not: an agreement
  negotiated *before* the pause still carries an EDR, and the data plane would
  still forward a call on it.

A contract definition that already existed (the create answered 409) is not
the run's to withdraw, and is left alone. One the run deleted itself
(`connector/provider/delete_contract_definition`) is forgotten, and not put
back.

### How it works

`player/execution/hold.py` holds one `RunHold` per run, on the `StepContext`,
bound to the job by the player before the first step.

- `connector/provider/create_contract_definition` records every definition it
  creates on the hold: its id, a call that deletes it, and a call that posts
  the same model again. `delete_contract_definition` drops it from the record.
- `JobManager.pause` closes the gate as before and also sets a *pause
  request* (`get_pause_request`). That is an event a step can wait on, so a
  pause can reach a step that is blocked.
- The gate between steps is `RunHold.gate` → `pause_point`. If the run is
  paused, it:
  1. marks the job held (`JobManager.hold` / `is_held`);
  2. deletes the recorded definitions, last created first, and publishes
     `job_held` with what it withdrew and what the connector refused to
     delete;
  3. waits for the gate to open;
  4. posts the withdrawn definitions again, in creation order, clears the hold
     and publishes `job_restored`.
- `mock/wait/*` races the callback against the pause request
  (`steps/mock/_paused_wait.py`). If the pause comes first, the listener is
  cancelled (which closes it), and `step_suspended` reports the remaining
  timeout. The step then goes to the same `pause_point`. After the hold, it
  registers the listener again, publishes a fresh `step_waiting` with
  `timeout_s` set to the remaining time, and waits again. A call that arrives
  at the same instant as the pause wins. `elapsed_ms` counts only the time
  spent waiting.
- Mocks: testlab's server answers 404 on every mock route while any run of its
  player is held (`routes.callbacks.on_hold`). Its mocks are not kept per run,
  so there is nothing finer to hold. A host that serves each run's mocks under
  its own address (the Catena-X engine's `/mock/<job_id>/…`) checks
  `JobManager.is_held(job_id)` and answers 404 for that run alone.

### Ordering and cancellation

```text
job_paused
  [step_suspended]           a wait was blocked when the pause came
  job_held                   definitions deleted, mocks turned away
job_resumed
  job_restored               definitions posted again, mocks answer
  [step_waiting]             timeout_s = what was left
```

A paused run that is cancelled opens its gate without being resumed. The hold
still puts the definitions back before the run stops. The teardown then finds
and deletes what the run created, just as it would for a run that was never
paused, and the teardown's delete assertions stay true. The pause request the
cancellation leaves behind is cleared, so it cannot stop the next wait.

Teardown never pauses, as before.

## Consequences

- A pause takes effect as soon as the step in flight ends, and immediately for
  a step blocked on the SUT. Only waits for a callback are interrupted. A call
  out to the SUT (a negotiation, a catalog query) runs to its end first,
  because stopping it half way would leave the SUT in a state the run cannot
  describe.
- While held, the SUT sees an empty catalog and a mock that answers 404. That
  is what it sees for a cancelled run, which is the point: nothing it does
  while the run is paused can count toward the run.
- Posting a definition again gives it the same id and the same model. A
  connector that refuses (the definition was re-created by someone else in the
  meantime, or the connector is unreachable) is reported in `job_restored.lost`,
  and the run goes on. The SUT will then not find the offer, and the wait
  times out saying so.
- Negotiations already under way at the pause are not undone. An agreement the
  SUT concluded before the pause is still valid after it, so a wait that
  resumes can be satisfied without a new negotiation.
- The hold changes nothing for a context built outside the player: an unbound
  `RunHold` records but never holds, and the gate falls back to waiting on the
  `JobManager` event.

## Alternatives considered

- **Keep the gate, and show the clock as running.** It is honest about what
  the backend does, but it is not what an operator means by pause. The
  operator wants the run frozen.
- **Tear down the whole provisioning (assets, policies, definitions) and
  re-run it on resume.** Deleting an asset that an agreement references is
  refused by the EDC. Re-creating a mock asset would also need the run's key
  again. That is more calls and more failure modes, for no difference the SUT
  can observe: without a definition there is no offer.
- **Re-run the setup phase on resume.** Setup steps are not idempotent
  (fresh UUIDs, one-shot registrations), and they publish outputs that later
  steps have already read.
- **Pause the timeout but leave the offer and the mocks up.** The SUT could
  then call while the run is paused, and the call would be buffered and
  counted once the run resumed. That is a result produced during a pause.
