################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""``flow/if`` and ``flow/retry`` wrapped around steps that really do something.

The flow steps are tested elsewhere against ``util/log``, which cannot fail on
its own. Here they wrap HTTP calls that can, and are driven by conditions read
from earlier steps — which is how a TCK uses them and where the seams show.
"""

from __future__ import annotations

import pytest

from combinations.harness import Harness
from combinations.http_double import HttpDouble, Response

pytestmark = pytest.mark.asyncio


def _get(url: str, step_id: str = "call") -> dict:
    """A nested GET, spelled the way a nested step is spelled in YAML."""
    return {"id": step_id, "uses": "http/http_request", "with": {"method": "GET", "url": url}}


class TestBranchingOnAnEarlierStep:
    """The condition reads a previous step's declared return."""

    async def test_a_status_code_decides_the_branch(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route("GET", "/probe", Response(status=404, body={}))
        http.json_route("GET", "/create", {"created": True})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "probe",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/probe"},
                "returns": {"status_code": {"type": "integer"}},
            },
            {
                "id": "ensure",
                "uses": "flow/if",
                "with": {
                    "conditions": [
                        {
                            "input": "${{ execution.probe.status_code }}",
                            "operator": "equals",
                            "value": 404,
                        }
                    ],
                    "then": [_get(f"{base}/create", "create")],
                },
                "returns": {"branch_taken": {"type": "string"}},
            },
        )

        assert outcome.passed, outcome.failures
        assert outcome.variables["branch_taken"] == "then"
        assert http.calls_to("GET", "/create")

    async def test_the_else_branch_runs_when_the_probe_succeeds(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/probe", {"present": True})
        http.json_route("GET", "/reuse", {"ok": True})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "probe",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/probe"},
                "returns": {"status_code": {"type": "integer"}},
            },
            {
                "id": "ensure",
                "uses": "flow/if",
                "with": {
                    "conditions": [
                        {
                            "input": "${{ execution.probe.status_code }}",
                            "operator": "equals",
                            "value": 404,
                        }
                    ],
                    "then": [_get(f"{base}/create", "create")],
                    "else": [_get(f"{base}/reuse", "reuse")],
                },
                "returns": {"branch_taken": {"type": "string"}},
            },
        )

        assert outcome.variables["branch_taken"] == "else"
        assert http.calls_to("GET", "/reuse")
        assert not http.calls_to("GET", "/create")

    async def test_a_condition_reads_into_a_response_body_by_path(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/state", {"content": {"state": "RECEIVED"}})
        http.json_route("POST", "/ack", {"acked": True})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "poll",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/state"},
                "returns": {"response_body": {"type": "object"}},
            },
            {
                "id": "ack",
                "uses": "flow/if",
                "with": {
                    "conditions": [
                        {
                            "input": "${{ execution.poll.response_body }}",
                            "path": "content.state",
                            "operator": "equals",
                            "value": "RECEIVED",
                        }
                    ],
                    "then": [
                        {
                            "id": "send",
                            "uses": "http/http_request",
                            "with": {"method": "POST", "url": f"{base}/ack", "body": {}},
                        }
                    ],
                },
                "returns": {"condition_result": {"type": "boolean"}},
            },
        )

        assert outcome.variables["condition_result"] is True
        assert http.calls_to("POST", "/ack")


class TestRetryingSomethingThatCanFail:
    """A route that answers differently each call is the only honest fixture."""

    async def test_a_flaky_endpoint_is_retried_until_it_answers(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route(
            "GET",
            "/eventually",
            Response(status=503, body={"state": "PENDING"}),
            Response(status=503, body={"state": "PENDING"}),
            Response(status=200, body={"state": "READY"}),
        )
        base = http.start()

        outcome = await harness.run(
            {
                "id": "await_ready",
                "uses": "flow/retry",
                "with": {
                    "max_attempts": 5,
                    "delay_s": 0,
                    "steps": [
                        {
                            "id": "poll",
                            "uses": "http/http_request",
                            "with": {"method": "GET", "url": f"{base}/eventually"},
                            "validate": [
                                {
                                    "uses": "validate/assert",
                                    "with": {
                                        "input": "status_code",
                                        "operator": "equals",
                                        "value": 200,
                                    },
                                }
                            ],
                        }
                    ],
                },
            },
        )

        assert outcome.passed, outcome.failures
        assert len(http.calls_to("GET", "/eventually")) == 3

    async def test_exhausting_the_attempts_fails_and_says_which_step(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route("GET", "/never", Response(status=500, body={}))
        base = http.start()

        outcome = await harness.run(
            {
                "id": "await_ready",
                "uses": "flow/retry",
                "with": {
                    "max_attempts": 2,
                    "delay_s": 0,
                    "steps": [
                        {
                            "id": "poll",
                            "uses": "http/http_request",
                            "with": {"method": "GET", "url": f"{base}/never"},
                            "validate": [
                                {
                                    "uses": "validate/assert",
                                    "with": {
                                        "input": "status_code",
                                        "operator": "equals",
                                        "value": 200,
                                    },
                                }
                            ],
                        }
                    ],
                },
            },
        )

        assert not outcome.passed
        error = outcome.error("await_ready") or ""
        assert "2 attempt" in error
        assert "http/http_request" in error
        assert len(http.calls_to("GET", "/never")) == 2

    async def test_a_retried_sequence_runs_every_step_again(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """Documented so nested steps get written to be safe to repeat."""
        http.json_route("POST", "/side-effect", {"ok": True})
        http.route(
            "GET",
            "/gate",
            Response(status=500, body={}),
            Response(status=200, body={}),
        )
        base = http.start()

        await harness.run(
            {
                "id": "attempt",
                "uses": "flow/retry",
                "with": {
                    "max_attempts": 3,
                    "delay_s": 0,
                    "steps": [
                        {
                            "id": "effect",
                            "uses": "http/http_request",
                            "with": {
                                "method": "POST",
                                "url": f"{base}/side-effect",
                                "body": {},
                            },
                        },
                        {
                            "id": "gate",
                            "uses": "http/http_request",
                            "with": {"method": "GET", "url": f"{base}/gate"},
                            "validate": [
                                {
                                    "uses": "validate/assert",
                                    "with": {
                                        "input": "status_code",
                                        "operator": "equals",
                                        "value": 200,
                                    },
                                }
                            ],
                        },
                    ],
                },
            },
        )

        assert len(http.calls_to("POST", "/side-effect")) == 2


class TestWhatANestedStepPublishes:
    """A nested step is reachable by its field name, never by its step id.

    Two different mechanisms publish a step's output, and only one of them
    descends into a branch. Every step publishes its own fields flatly as it
    runs (``BaseStep.publish_output``), so ``bpn`` is set from inside a
    branch; the *namespaced* ``execution.<id>.<field>`` name is written by the
    phase runner, which never looks inside ``flow/if`` or ``flow/retry``.

    So a nested step's value survives, but only under a name that any later
    step could overwrite. Pinned here because the asymmetry is invisible from
    either step's contract.
    """

    async def test_a_nested_step_publishes_its_fields_flatly(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "branch",
                "uses": "flow/if",
                "with": {
                    "conditions": [{"input": "go", "operator": "not_null"}],
                    "then": [
                        {
                            "id": "endpoint",
                            "uses": "mock/api",
                            "with": {"path": "/callback"},
                            "returns": {"full_mock_url": {"type": "string"}},
                        }
                    ],
                },
            },
        )

        assert outcome.variables["full_mock_url"]

    async def test_a_nested_step_is_not_reachable_by_its_id(
        self, harness: Harness
    ) -> None:
        """``${{ execution.mint.value }}`` does not resolve from inside a branch."""
        outcome = await harness.run(
            {
                "id": "branch",
                "uses": "flow/if",
                "with": {
                    "conditions": [{"input": "go", "operator": "not_null"}],
                    "then": [
                        {
                            "id": "mint",
                            "uses": "util/generate_uuid",
                            "returns": {"value": {"type": "string"}},
                        }
                    ],
                },
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.mint.value }}"},
            },
        )

        assert "execution.mint.value" not in outcome.variables
        assert not outcome.passed
        assert "execution.mint.value" in (outcome.error("echo") or "")

    async def test_the_wrapper_carries_the_nested_outputs_instead(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "branch",
                "uses": "flow/if",
                "with": {
                    "conditions": [{"input": "go", "operator": "not_null"}],
                    "then": [{"id": "mint", "uses": "util/generate_uuid"}],
                },
                "returns": {"outputs": {"type": "array"}},
            },
            {
                "id": "read",
                "uses": "util/json_path_extract",
                "with": {"input": "${{ execution.branch.outputs }}", "path": "0"},
            },
        )

        assert outcome.passed, outcome.failures
        assert outcome.output("read")


class TestFlowStepsInsideFlowSteps:
    """Wrappers nest, and a failure inside one surfaces through the other."""

    async def test_an_if_inside_a_retry_is_retried_with_it(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route(
            "GET",
            "/gate",
            Response(status=500, body={}),
            Response(status=200, body={}),
        )
        base = http.start()

        outcome = await harness.run(
            {
                "id": "outer",
                "uses": "flow/retry",
                "with": {
                    "max_attempts": 3,
                    "delay_s": 0,
                    "steps": [
                        {
                            "id": "inner",
                            "uses": "flow/if",
                            "with": {
                                "conditions": [
                                    {"input": "always", "operator": "not_null"}
                                ],
                                "then": [
                                    {
                                        "id": "gate",
                                        "uses": "http/http_request",
                                        "with": {
                                            "method": "GET",
                                            "url": f"{base}/gate",
                                        },
                                        "validate": [
                                            {
                                                "uses": "validate/assert",
                                                "with": {
                                                    "input": "status_code",
                                                    "operator": "equals",
                                                    "value": 200,
                                                },
                                            }
                                        ],
                                    }
                                ],
                            },
                        }
                    ],
                },
            },
        )

        assert outcome.passed, outcome.failures
        assert len(http.calls_to("GET", "/gate")) == 2

    async def test_a_failure_inside_a_branch_names_the_branch(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route("GET", "/bad", Response(status=500, body={}))
        base = http.start()

        outcome = await harness.run(
            {
                "id": "branch",
                "uses": "flow/if",
                "with": {
                    "conditions": [{"input": "go", "operator": "not_null"}],
                    "then": [
                        {
                            "id": "call",
                            "uses": "http/http_request",
                            "with": {"method": "GET", "url": f"{base}/bad"},
                            "validate": [
                                {
                                    "uses": "validate/assert",
                                    "with": {
                                        "input": "status_code",
                                        "operator": "equals",
                                        "value": 200,
                                    },
                                }
                            ],
                        }
                    ],
                },
            },
        )

        assert not outcome.passed
        assert "'then' branch" in (outcome.error("branch") or "")


class TestDelayBetweenSteps:
    """``flow/delay`` sits in a chain without disturbing what flows through it."""

    async def test_a_delay_does_not_interrupt_the_chain(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_uuid",
                "returns": {"value": {"type": "string"}},
            },
            {"id": "wait", "uses": "flow/delay", "with": {"seconds": 0.01}},
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.mint.value }}"},
            },
        )

        assert outcome.passed, outcome.failures
        assert outcome.output("echo") == outcome.output("mint")
