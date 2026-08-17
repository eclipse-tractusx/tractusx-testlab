################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Tests for test-level skip / disable configuration (Issue #38)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models.authoring.definitions import TckTestEntry
from tractusx_testlab.models.primitives.enums import ScriptStatus
from tractusx_testlab.models.primitives.exceptions import SkipNotAllowedError
from tractusx_testlab.models.runtime.inspection import ScriptInspection
from tractusx_testlab.player.execution._trace_formatter import (
    build_tck_result,
    make_intentionally_skipped_result,
)
from tractusx_testlab.scripting.script import Tck, TestScript

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

def _make_script_def(script_id: str = "test-a") -> MagicMock:
    """Return a minimal ScriptDefinition mock sufficient for TestScript."""
    d = MagicMock()
    d.metadata.name = script_id.replace("-", " ").title()
    d.dataspace_version = "saturn"
    d.id = script_id
    return d


def _make_test_script(
    script_id: str = "test-a",
    skippable: bool = False,
    test_id: str = "test-a.yaml",
) -> TestScript:
    """Factory for a TestScript with the given skippable flag."""
    return TestScript(_make_script_def(script_id), skippable=skippable, test_id=test_id)


def _make_tck_with_scripts(
    *scripts: tuple[str, bool],  # (test_id_stem, skippable)
) -> Tck:
    """Build a minimal Tck populated with TestScript objects.

    Each entry in *scripts* is (stem, skippable) where stem produces
    test_id ``{stem}.yaml``.
    """
    tck_def = MagicMock()
    tck_def.metadata.name = "Test TCK"
    tck_def.metadata.version = "1.0"
    tck_def.env = None
    tck_def.tests = []
    tck = Tck(tck_def)
    tck._scripts = [
        _make_test_script(stem, skippable=skip, test_id=f"{stem}.yaml")
        for stem, skip in scripts
    ]
    return tck


def _make_script_result(name: str, status: ScriptStatus) -> MagicMock:
    from tractusx_testlab.models.runtime.results import AssertionSummary, ScriptResult

    now = datetime.now(UTC)
    return ScriptResult(
        script_name=name,
        dataspace_version="saturn",
        status=status,
        execution=[],
        started_at=now,
        finished_at=now,
        total_duration_s=0.0,
        assertion_summary=AssertionSummary(total=0, passed=0, failed_hard=0, failed_soft=0),
    )


# ---------------------------------------------------------------------------
# TckTestEntry model
# ---------------------------------------------------------------------------

class TestTckTestEntry:

    def test_skippable_defaults_false(self):
        entry = TckTestEntry(id="test-cert.yaml")
        assert entry.skippable is False

    def test_skippable_true_is_preserved(self):
        entry = TckTestEntry(id="test-cert.yaml", skippable=True)
        assert entry.skippable is True

    def test_skippable_false_is_explicit(self):
        entry = TckTestEntry(id="test-cert.yaml", skippable=False)
        assert entry.skippable is False


# ---------------------------------------------------------------------------
# TestScript.skippable and .test_id properties
# ---------------------------------------------------------------------------

class TestTestScriptSkippable:

    def test_default_skippable_is_false(self):
        script = _make_test_script()
        assert script.skippable is False

    def test_skippable_true_propagates(self):
        script = _make_test_script(skippable=True)
        assert script.skippable is True

    def test_test_id_is_stored(self):
        script = _make_test_script(test_id="my-test.yaml")
        assert script.test_id == "my-test.yaml"

    def test_test_id_default_empty_string(self):
        script = TestScript(_make_script_def())
        assert script.test_id == ""


# ---------------------------------------------------------------------------
# Tck.skippable_tests()
# ---------------------------------------------------------------------------

class TestTckSkippableTests:

    def test_no_skippable_tests_returns_empty(self):
        tck = _make_tck_with_scripts(("test-a", False), ("test-b", False))
        assert tck.skippable_tests() == []

    def test_all_skippable_tests_returned(self):
        tck = _make_tck_with_scripts(("test-a", True), ("test-b", True))
        assert sorted(tck.skippable_tests()) == ["test-a.yaml", "test-b.yaml"]

    def test_only_skippable_tests_returned(self):
        tck = _make_tck_with_scripts(("test-a", True), ("test-b", False))
        assert tck.skippable_tests() == ["test-a.yaml"]


# ---------------------------------------------------------------------------
# make_intentionally_skipped_result
# ---------------------------------------------------------------------------

class TestMakeIntentionallySkippedResult:

    def test_status_is_skipped(self):
        script = _make_test_script()
        result = make_intentionally_skipped_result(script)
        assert result.status == ScriptStatus.SKIPPED

    def test_no_error_message(self):
        script = _make_test_script()
        result = make_intentionally_skipped_result(script)
        assert result.error is None

    def test_execution_list_is_empty(self):
        script = _make_test_script()
        result = make_intentionally_skipped_result(script)
        assert result.execution == []


# ---------------------------------------------------------------------------
# build_tck_result — SKIPPED treated as non-failing
# ---------------------------------------------------------------------------

class TestBuildTckResult:

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def test_all_completed_gives_completed(self):
        results = [
            _make_script_result("a", ScriptStatus.COMPLETED),
            _make_script_result("b", ScriptStatus.COMPLETED),
        ]
        tck_r = build_tck_result("TCK", results, self._now(), self._now())
        assert tck_r.status == ScriptStatus.COMPLETED

    def test_skipped_plus_completed_gives_completed(self):
        results = [
            _make_script_result("a", ScriptStatus.COMPLETED),
            _make_script_result("b", ScriptStatus.SKIPPED),
        ]
        tck_r = build_tck_result("TCK", results, self._now(), self._now())
        assert tck_r.status == ScriptStatus.COMPLETED

    def test_all_skipped_gives_completed(self):
        results = [_make_script_result("a", ScriptStatus.SKIPPED)]
        tck_r = build_tck_result("TCK", results, self._now(), self._now())
        assert tck_r.status == ScriptStatus.COMPLETED

    def test_failed_script_gives_failed(self):
        results = [
            _make_script_result("a", ScriptStatus.COMPLETED),
            _make_script_result("b", ScriptStatus.FAILED),
        ]
        tck_r = build_tck_result("TCK", results, self._now(), self._now())
        assert tck_r.status == ScriptStatus.FAILED

    def test_skipped_plus_failed_gives_failed(self):
        results = [
            _make_script_result("a", ScriptStatus.SKIPPED),
            _make_script_result("b", ScriptStatus.FAILED),
        ]
        tck_r = build_tck_result("TCK", results, self._now(), self._now())
        assert tck_r.status == ScriptStatus.FAILED


# ---------------------------------------------------------------------------
# TestlabPlayer._validate_and_resolve_skip_ids
# ---------------------------------------------------------------------------

class TestValidateAndResolveSkipIds:

    def _resolve(self, tck, runtime_vars):
        from tractusx_testlab.player.execution._skip import resolve_skip_ids
        return resolve_skip_ids(tck, runtime_vars)

    def test_empty_runtime_vars_returns_empty_frozenset(self):
        tck = _make_tck_with_scripts(("test-a", True))
        result = self._resolve(tck, {})
        assert result == frozenset()

    def test_none_runtime_vars_returns_empty_frozenset(self):
        tck = _make_tck_with_scripts(("test-a", True))
        result = self._resolve(tck, None)
        assert result == frozenset()

    def test_valid_skippable_id_returns_frozenset(self):
        tck = _make_tck_with_scripts(("test-a", True), ("test-b", False))
        result = self._resolve(tck, {"skip_tests": ["test-a.yaml"]})
        assert result == frozenset({"test-a.yaml"})

    def test_non_skippable_id_raises_skip_not_allowed(self):
        tck = _make_tck_with_scripts(("test-a", True), ("test-b", False))
        with pytest.raises(SkipNotAllowedError) as exc_info:
            self._resolve(tck, {"skip_tests": ["test-b.yaml"]})
        assert "test-b.yaml" in str(exc_info.value)

    def test_unknown_id_raises_skip_not_allowed(self):
        tck = _make_tck_with_scripts(("test-a", True))
        with pytest.raises(SkipNotAllowedError) as exc_info:
            self._resolve(tck, {"skip_tests": ["does-not-exist.yaml"]})
        assert "does-not-exist.yaml" in str(exc_info.value)

    def test_multiple_valid_ids_accepted(self):
        tck = _make_tck_with_scripts(("test-a", True), ("test-b", True))
        result = self._resolve(tck, {"skip_tests": ["test-a.yaml", "test-b.yaml"]})
        assert result == frozenset({"test-a.yaml", "test-b.yaml"})


# ---------------------------------------------------------------------------
# ScriptInspection.skippable
# ---------------------------------------------------------------------------

class TestScriptInspectionSkippable:

    def test_skippable_false_by_default(self):
        insp = ScriptInspection(name="test", steps=())
        assert insp.skippable is False

    def test_skippable_true_is_stored(self):
        insp = ScriptInspection(name="test", skippable=True, steps=())
        assert insp.skippable is True

    def test_build_inspection_result_propagates_skippable(self):
        from tractusx_testlab.scripting._inspection import build_inspection_result

        tck = _make_tck_with_scripts(("test-a", True), ("test-b", False))
        # Provide minimal step lists for the inspection helper
        for script in tck._scripts:
            script.definition.setup = []
            script.definition.execution = []
            script.definition.teardown = []

        result = build_inspection_result(tck)
        assert result.scripts[0].skippable is True
        assert result.scripts[1].skippable is False
