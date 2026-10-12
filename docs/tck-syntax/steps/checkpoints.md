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

# 5.5 Checkpoints

A **checkpoint** is a step at which a run needs someone to act. Most steps
call the system under test and check the answer on their own; at a checkpoint
the run waits for your system, or for you. Before a run starts, TestLab lists
its checkpoints, and while it runs, it reports each one as it is asked and
answered. See [ADR-0028](../../developer/decision-records/backend/ADR-0028-checkpoints.md)
for the design.

## Directions

Every checkpoint has a direction:

| Direction | What happens | Who acts |
|-----------|--------------|----------|
| `inbound` | Your system calls the Test Suite, and the Test Suite answers. | Your system, or you on its behalf. |
| `outbound` | The Test Suite calls your system, and your system has to answer. | Your system has to be ready. |
| `internal` | You choose in the Test Suite. Nothing is called. | You. |

These steps are checkpoints by their type:

| Step | Direction | `via` |
|------|-----------|-------|
| `mock/wait/http_request` | `inbound` | `direct` |
| `mock/wait/dataplane/http_request` | `inbound` | `dataplane` |
| `notification/consumer/send` | `outbound` | `dataplane` |
| `flow/select` | `internal` | — |
| `connector/datasets/select` | `internal` | — |

The [step reference](../../api-reference/steps/index.md) marks each one with a
**Checkpoint** line. A step type declares it on its `@step` decorator; see
[Creating a step](../../developer/creating-a-step.md).

## Marking a step: `checkpoint:`

Use the step's `checkpoint:` key to make any step a checkpoint, to name one,
or to switch one off:

```yaml
execution:
  - id: push_certificate
    uses: http/http_request
    with:
      method: POST
      url: ${{ env.sut_push_url }}
    checkpoint:
      label: Your system accepts the certificate
      description: Your connector has to answer the push with 2xx.
      direction: outbound

  - id: await_ack
    uses: mock/wait/http_request
    with:
      mock: ${{ execution.ack_endpoint.mock }}
    checkpoint:
      label: Send the acknowledgement   # relabel a declared checkpoint

  - id: pick_only_offer
    uses: flow/select
    with:
      options: [the-only-one]
    checkpoint: false                   # not a checkpoint in this test
```

| Value | Effect |
|-------|--------|
| `true` | The step is a checkpoint. A step type that declares none becomes `outbound`. |
| `false` | The step is not a checkpoint, even when its type declares one. |
| a mapping | The step is a checkpoint, with `label`, `description`, and — for a step type that declares no checkpoint — `direction` and `via`. |

A mapping cannot change the direction or `via` of a step type that declares a
checkpoint, and an `internal` checkpoint has no `via`. The compiler reports
both. Without a `label`, a checkpoint is named by the step's `with.action`
label, when it has one.

## What a run reports

A run publishes `checkpoints.planned` once, before its first test, then a
`checkpoint.updated` every time a checkpoint changes. The
[execution events](../../developer/execution-events.md#checkpoints) page has
the fields. A checkpoint goes through these states:

| State | Meaning |
|-------|---------|
| `ahead` | Not asked yet. |
| `now` | Asked: the run waits for whoever has to act. |
| `cleared` | Answered, and the step completed. |
| `timed_out` | Nobody answered in time. |
| `failed` | The step failed after the answer. |
| `skipped` | Not needed: a `flow/if` branch not taken, a choice of one option, a test left out with `skip_tests`. |
| `not_reached` | The run stopped before it. |

A checkpoint in a `flow/if` branch is `conditional`; one in a `flow/retry` or
a loop is `repeated` and may be asked more than once. Each ask counts as an
attempt; a question asked again after a pause is the same attempt.

Every call, request and choice at a checkpoint names it in the trace, with
`checkpoint: {index, attempt, direction}`. That is how you find both halves of
an exchange: what was sent and how it was answered.

## Listing them before a run

```bash
testlab inspect dist/my-tck.tck --checkpoints
testlab inspect dist/my-tck.tck --checkpoints --skip-tests optional.yaml --json
```

In Python, `Tck.checkpoints(skip_tests)` returns the same list.

## In `testlab run`

`testlab run` shows the checkpoints first and asks before it starts:

```text
================================================================================
  THIS RUN NEEDS YOU AT 2 CHECKPOINTS
--------------------------------------------------------------------------------
  Push the certificate
    1  await_push   inbound · your system calls us
       1m 00s to answer · Push the certificate to the Test Suite
  Choose the offer
    2  pick_offer   internal · you choose
       5m 00s to answer · Pick the offer to negotiate
================================================================================
Continue? [y/N]:
```

At an `internal` checkpoint it asks you to choose:

```text
================================================================================
  CHECKPOINT 2 of 2 · YOU CHOOSE                                    4m 52s left
--------------------------------------------------------------------------------
  Pick the offer to negotiate

     1  CCMAPI notification 3.0 · asset urn:uuid:7f3c… · Membership, FrameworkAgreement
     2  CCMAPI notification 3.0 · asset urn:uuid:a91e… · Membership
================================================================================
Choose [1-2] (4m 52s left, q to stop):
```

Type a number to choose, or `q` to stop the run. For the options to run
without a terminal, see the [CLI reference](../../api-reference/index.md#testlab-run-checkpoints).
