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

import base64
import io
import json
import urllib.parse
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.logging import masking
from tractusx_testlab.logging.masking import (
    forget_secrets,
    mask,
    register_secret,
    release_run,
)
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


class TestPinnedForTheRun:
    """A run's own credentials cannot be evicted while it is still running."""

    def test_newer_secrets_never_evict_a_pinned_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(masking, "MAX_SECRETS", 2)
        register_secret(_KEY, run="run-1")
        for index in range(10):
            register_secret(f"other-secret-{index:04d}")
        assert mask(_KEY) == _MARK

    def test_released_secrets_stay_masked_until_newer_ones_evict_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_SECRETS", 2)
        register_secret(_KEY, run="run-1")
        release_run("run-1")
        assert mask(_KEY) == _MARK
        for index in range(2):
            register_secret(f"other-secret-{index:04d}")
        assert mask(_KEY) == _KEY

    def test_releasing_one_run_leaves_another_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(masking, "MAX_SECRETS", 1)
        register_secret(_KEY, run="run-1")
        register_secret(f"{_KEY}-two", run="run-2")
        release_run("run-1")
        register_secret("other-secret-0000")
        assert mask(f"{_KEY}-two") == _MARK
        assert mask(_KEY) == _KEY


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


class TestExplicitSecrets:
    """A value someone declared secret is masked however short, nested or numeric."""

    def test_a_short_explicit_secret_is_masked_and_a_short_implicit_one_is_not(self) -> None:
        register_secret("hunter2", run="run-1", explicit=True)
        register_secret("abcdefg", run="run-1")
        assert mask("login with hunter2 or abcdefg") == f"login with {_MARK} or abcdefg"

    def test_below_the_explicit_floor_nothing_is_registered(self) -> None:
        register_secret("abc", explicit=True)
        assert mask("abc def") == "abc def"

    def test_every_string_of_a_structured_secret_is_masked(self) -> None:
        register_secret(
            {"user": "u", "pw": "objsecretvalue1", "nested": ["innerkey1"]}, explicit=True
        )
        assert mask("objsecretvalue1 innerkey1 u") == f"{_MARK} {_MARK} u"

    def test_a_number_that_prints_as_an_explicit_secret_is_masked(self) -> None:
        register_secret(12345678, run="run-1", explicit=True)
        assert mask({"pin": 12345678, "count": 3, "flag": True}) == {
            "pin": _MARK,
            "count": 3,
            "flag": True,
        }
        assert mask("pin=12345678") == f"pin={_MARK}"

    def test_a_number_is_not_masked_for_an_implicit_secret(self) -> None:
        register_secret("12345678")
        assert mask({"pin": 12345678}) == {"pin": 12345678}


class TestSpellings:
    """A secret is masked in every spelling a record is likely to carry it in."""

    @pytest.mark.parametrize(
        "spelling",
        [
            pytest.param(lambda v: repr(v)[1:-1], id="repr"),
            pytest.param(lambda v: json.dumps(v)[1:-1], id="json"),
            pytest.param(lambda v: urllib.parse.quote(v, safe=""), id="percent"),
            pytest.param(urllib.parse.quote, id="percent-path"),
            pytest.param(urllib.parse.quote_plus, id="form"),
            pytest.param(lambda v: base64.b64encode(v.encode()).decode(), id="base64"),
        ],
    )
    def test_an_encoded_spelling_is_masked(self, spelling: Any) -> None:
        secret = 'S3cr3t+/=&? "x"\n'
        register_secret(secret, run="run-1", explicit=True)
        assert mask(f"seen: {spelling(secret)}") == f"seen: {_MARK}"

    def test_a_trailing_newline_quoted_by_an_http_client_is_masked(self) -> None:
        register_secret("PLATFORM-MGMT-KEY-0123\n", run="run-1", explicit=True)
        message = "Illegal header value b'PLATFORM-MGMT-KEY-0123\\n'"
        assert mask(message) == f"Illegal header value b'{_MARK}'"

    def test_a_spelling_shorter_than_the_floor_is_not_registered(self) -> None:
        assert masking.forms_of("abcd", 9) == ["abcd"]


class TestRegistryCost:
    """Registering is cheap; the pattern is rebuilt once, on the next mask."""

    def test_registrations_do_not_rebuild_the_pattern(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        builds: list[int] = []
        real = masking.pattern_for

        def counting(secrets: Any) -> Any:
            builds.append(1)
            return real(secrets)

        monkeypatch.setattr(masking, "pattern_for", counting)
        for index in range(2000):
            register_secret(f"tenant-secret-{index:08d}", run="tenant")
        assert builds == []
        assert mask("tenant-secret-00001999") == _MARK
        assert mask("tenant-secret-00000000") == _MARK
        assert len(builds) == 1

    def test_the_longest_secret_at_a_position_is_masked_whole(self) -> None:
        for secret in ("abcdefgh", "abcdefghijkl", "abcdefghXYZW", "zzabcdefgh"):
            register_secret(secret)
        assert mask("abcdefghijkl abcdefghXYZW abcdefgh! zzabcdefgh") == " ".join(
            [_MARK, _MARK, f"{_MARK}!", _MARK]
        )

    def test_a_trie_too_deep_for_the_parser_still_masks(self) -> None:
        for depth in range(8, 400):
            register_secret("x" * depth + "y")
        assert mask("x" * 399 + "y") == _MARK
        assert mask("a" + "x" * 20 + "y") == f"a{_MARK}"


class TestDeclaredAllowance:
    """What a run's author hid pins at most so many values; the rest is handed back."""

    def test_past_the_allowance_values_are_returned_and_not_masked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_DECLARED_PER_RUN", 2)
        withheld = [
            value
            for index in range(3)
            for value in register_secret(f"junk-secret-{index:06d}", run="tenant", declared=True)
        ]
        assert withheld == ["junk-secret-000002"]
        assert mask("junk-secret-000001 junk-secret-000002") == f"{_MARK} junk-secret-000002"

    def test_a_value_already_pinned_does_not_count_twice(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_DECLARED_PER_RUN", 1)
        register_secret("junk-secret-000000", run="tenant", declared=True)
        assert register_secret("junk-secret-000000", run="tenant", declared=True) == []

    def test_explicit_secrets_are_never_turned_away(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(masking, "MAX_DECLARED_PER_RUN", 0)
        assert register_secret(_KEY, run="tenant", explicit=True) == []
        assert mask(_KEY) == _MARK

    def test_releasing_the_run_resets_its_allowance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(masking, "MAX_DECLARED_PER_RUN", 1)
        register_secret("junk-secret-000000", run="tenant", declared=True)
        release_run("tenant")
        assert register_secret("junk-secret-000001", run="tenant", declared=True) == []

    def test_mask_also_masks_what_the_registry_was_not_given(self) -> None:
        assert masking.mask_also({"v": "junk-secret-000002"}, ["junk-secret-000002"]) == {
            "v": _MARK
        }


class TestCutSecrets:
    """A secret the tracer clipped mid-way is masked up to the cut."""

    _SECRET = "MOCK-RUN-KEY-0123456789abcdef0123456789abcdef"

    def test_the_kept_prefix_of_a_cut_secret_is_masked(self) -> None:
        register_secret(self._SECRET, run="run-1")
        clipped = "x" * 30 + self._SECRET[:20] + "...[truncated 25 chars]"
        assert mask(clipped) == "x" * 30 + f"{_MARK}...[truncated 25 chars]"

    def test_a_prefix_shorter_than_the_floor_is_left(self) -> None:
        register_secret(self._SECRET, run="run-1")
        clipped = "x" * 30 + self._SECRET[:7] + "...[truncated 38 chars]"
        assert mask(clipped) == clipped

    def test_a_prefix_not_at_a_cut_is_left(self) -> None:
        register_secret(self._SECRET, run="run-1")
        assert mask(f"{self._SECRET[:20]} and more") == f"{self._SECRET[:20]} and more"
