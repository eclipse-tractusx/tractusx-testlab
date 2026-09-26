#################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A secret the run minted never reaches a record a viewer can read."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.logging import masking
from tractusx_testlab.logging.masking import forget_secrets, mask, register_secret
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.logging.transcript import _Tee
from tractusx_testlab.player.execution.monitor import ExecutionMonitor

_KEY = "s3cr3t-mock-key-0123456789"
_MARK = "***"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    yield
    forget_secrets()


class TestMask:
    def test_nothing_registered_leaves_the_value_as_it_was(self) -> None:
        value = {"x-api-key": _KEY}
        assert mask(value) is value

    def test_a_registered_value_is_replaced_wherever_it_occurs(self) -> None:
        register_secret(_KEY)
        assert mask(f"curl -H 'x-api-key: {_KEY}'") == f"curl -H 'x-api-key: {_MARK}'"

    def test_containers_are_walked_keys_included(self) -> None:
        register_secret(_KEY)
        masked = mask(
            {
                "dataAddress": {"header:x-api-key": _KEY, _KEY: "as a key"},
                "list": [_KEY, 3, None],
                "tuple": (_KEY,),
            }
        )
        assert masked == {
            "dataAddress": {"header:x-api-key": _MARK, _MARK: "as a key"},
            "list": [_MARK, 3, None],
            "tuple": (_MARK,),
        }

    def test_a_value_too_short_to_be_a_secret_is_not_registered(self) -> None:
        register_secret("abc")
        assert mask("abc def") == "abc def"

    def test_a_secret_containing_another_is_masked_whole(self) -> None:
        register_secret(_KEY)
        register_secret(f"{_KEY}-longer")
        assert mask(f"{_KEY}-longer") == _MARK

    def test_the_oldest_secret_is_forgotten_past_the_bound(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_SECRETS", 2)
        for index in range(3):
            register_secret(f"{_KEY}-{index}")
        assert mask(f"{_KEY}-0") == f"{_KEY}-0"
        assert mask(f"{_KEY}-2") == _MARK


class TestSinks:
    """Each record a viewer can read passes through the mask."""

    def test_the_trace_file_and_envelope_hold_no_secret(self, tmp_path: Path) -> None:
        register_secret(_KEY)
        trace = ExecutionTrace("tck", tmp_path / "trace.jsonl")

        envelope = trace.emit("tck.test.step.start", {"inputs": {"headers": {"k": _KEY}}})
        trace.close()

        assert envelope["data"] == {"inputs": {"headers": {"k": _MARK}}}
        written = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
        assert _KEY not in written
        assert json.loads(written)["data"]["inputs"]["headers"]["k"] == _MARK

    def test_an_embedder_callback_receives_the_masked_event(self) -> None:
        register_secret(_KEY)
        received: list[dict[str, Any]] = []
        monitor = ExecutionMonitor(MagicMock())
        monitor.add_callback(lambda _event, payload: received.append(payload))

        monitor._emit("step.completed", output={"api_key": _KEY})

        assert received == [{"output": {"api_key": _MARK}}]

    def test_the_transcript_masks_the_console_and_the_file(self) -> None:
        register_secret(_KEY)
        console, file = io.StringIO(), io.StringIO()
        tee = _Tee(console, file)

        written = tee.write(f"key={_KEY}\n")

        assert written == len(f"key={_KEY}\n")
        assert console.getvalue() == f"key={_MARK}\n"
        assert file.getvalue() == f"key={_MARK}\n"
