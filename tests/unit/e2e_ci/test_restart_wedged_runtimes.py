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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The deploy watcher's wedge rule, offline.

A wedged runtime is one whose JVM logged ``Runtime <id> ready`` and whose
container the kubelet still reports not ready well past boot. Everything
else — booting, crashing, a Helm hook — is left alone.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta

import pytest

from tests.paths import TESTS_DIR

_SCRIPT = TESTS_DIR / "e2e" / "connector-dtr-smoke" / "ci" / "restart_wedged_runtimes.py"
_spec = importlib.util.spec_from_file_location("restart_wedged_runtimes", _SCRIPT)
wedged = importlib.util.module_from_spec(_spec)
# Registered before execution: the script's dataclass resolves its
# postponed annotations through sys.modules.
sys.modules[_spec.name] = wedged
_spec.loader.exec_module(wedged)

NOW = datetime(2026, 9, 12, 9, 16, 0, tzinfo=UTC)
GRACE = timedelta(seconds=120)
READY_LOG = (
    "INFO 2026-09-12T09:12:15 57 service extensions started\n"
    "INFO 2026-09-12T09:12:15 Runtime 81aae30a-ef64-423b-b599-10a30058a618 ready\n"
)
BOOTING_LOG = "INFO 2026-09-12T09:12:00 Booting EDC runtime\n"


def _pod(
    *,
    ready: bool = False,
    phase: str = "Running",
    started_ago: int = 240,
    owner_kind: str = "ReplicaSet",
    state: str = "running",
) -> dict:
    started = (NOW - timedelta(seconds=started_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "metadata": {
            "name": "umbrella-consumer-identityhub-cc5d9c8b-xsmss",
            "ownerReferences": [
                {"kind": owner_kind, "name": "umbrella-consumer-identityhub-cc5d9c8b"}
            ],
        },
        "spec": {
            "containers": [
                {
                    "name": "tractusx-identityhub",
                    "readinessProbe": {"httpGet": {"path": "/api/check/readiness", "port": 8081}},
                    "livenessProbe": {"httpGet": {"path": "/api/check/liveness", "port": 8081}},
                }
            ]
        },
        "status": {
            "phase": phase,
            "podIP": "10.244.0.20",
            "containerStatuses": [
                {
                    "name": "tractusx-identityhub",
                    "ready": ready,
                    "restartCount": 0,
                    "state": {state: {"startedAt": started}} if state == "running" else {state: {}},
                }
            ],
        },
    }


class TestTheRule:
    def test_a_runtime_that_logged_ready_but_never_became_ready_is_wedged(self) -> None:
        wedge = wedged.assess(_pod(), READY_LOG, NOW, GRACE)
        assert wedge is not None
        assert wedge.pod == "umbrella-consumer-identityhub-cc5d9c8b-xsmss"
        assert wedge.owner == "umbrella-consumer-identityhub-cc5d9c8b"
        assert wedge.readiness_url == "http://10.244.0.20:8081/api/check/readiness"
        assert wedge.liveness_url == "http://10.244.0.20:8081/api/check/liveness"
        assert "240s" in wedge.reason

    def test_a_ready_pod_is_left_alone(self) -> None:
        assert wedged.assess(_pod(ready=True), READY_LOG, NOW, GRACE) is None

    def test_a_pod_still_inside_the_grace_period_is_left_alone(self) -> None:
        """The normal boot window: Jetty is up before Jersey has registered."""
        assert wedged.assess(_pod(started_ago=60), READY_LOG, NOW, GRACE) is None

    def test_a_runtime_that_has_not_logged_ready_is_left_alone(self) -> None:
        """Still booting, or broken: neither is a wedge, and neither is restarted here."""
        assert wedged.assess(_pod(), BOOTING_LOG, NOW, GRACE) is None

    def test_a_helm_hook_is_never_touched(self) -> None:
        assert wedged.assess(_pod(owner_kind="Job"), READY_LOG, NOW, GRACE) is None

    @pytest.mark.parametrize("state", ["waiting", "terminated"])
    def test_a_container_the_kubelet_is_already_handling_is_left_alone(self, state: str) -> None:
        assert wedged.assess(_pod(state=state), READY_LOG, NOW, GRACE) is None

    def test_a_pod_that_is_not_running_is_left_alone(self) -> None:
        assert wedged.assess(_pod(phase="Pending"), READY_LOG, NOW, GRACE) is None

    def test_the_ready_line_is_matched_through_ansi_colour(self) -> None:
        """0.4.0 images colour their log; the id and the word are what matter."""
        log = "\x1b[0;32mINFO 2026-09-12T09:12:15 Runtime 81aae30a-ef64-423b-b599-10a30058a618 ready\x1b[0m\n"
        assert wedged.assess(_pod(), log, NOW, GRACE) is not None


class TestTheRestartCap:
    def test_restarts_are_counted_per_owner(self, tmp_path) -> None:
        owner = "umbrella-consumer-identityhub-cc5d9c8b"
        assert wedged._restart_count(tmp_path, owner) == 0
        wedged._record_restart(tmp_path, owner)
        wedged._record_restart(tmp_path, owner)
        assert wedged._restart_count(tmp_path, owner) == 2
        assert wedged._restart_count(tmp_path, "another-owner") == 0
