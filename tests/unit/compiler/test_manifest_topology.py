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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The compiled manifest states what a package needs bound before it can run.

A `.tck` travels to whoever operates the engine, and the question they ask of
it is "what must I bind, and what does this certify against". These tests pin
that the answer is in the package manifest, resolved the same way the player
resolves it at run time.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tractusx_testlab.compiler.ir.builder import build_ir


def _test_doc(test_id: str, infrastructure: dict | None = None) -> dict:
    doc: dict = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": test_id,
        "namespace": "topology-tck",
        "metadata": {"name": test_id, "version": "1.0"},
        "execution": [
            {"id": "noop", "uses": "utility/data/parse_kv", "with": {"text": "a=b"}},
        ],
    }
    if infrastructure is not None:
        doc["infrastructure"] = infrastructure
    return doc


def _write_tck(
    tmp_path: Path,
    *,
    manifest_extra: dict | None = None,
    tests: dict[str, dict | None] | None = None,
) -> Path:
    """Write a TCK package on disk and return its ``index.yaml`` path."""
    tests = tests or {"first.yaml": None}
    manifest: dict = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "topology-tck",
        "metadata": {
            "name": "Topology TCK",
            "version": "1.0",
            "description": "States its topology.",
            "authors": [{"name": "T", "email": "t@example.com", "company": "T"}],
            "license": "Apache-2.0",
            "standards": [{"id": "CX-0018", "version": "v4.2.0"}],
        },
        "env": {},
        "tests": [{"id": name} for name in tests],
        **(manifest_extra or {}),
    }

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    for name, infrastructure in tests.items():
        (tests_dir / name).write_text(
            yaml.dump(_test_doc(Path(name).stem, infrastructure)), encoding="utf-8",
        )

    index = tmp_path / "index.yaml"
    index.write_text(yaml.dump(manifest), encoding="utf-8")
    return index


def _tck_section(index: Path) -> dict:
    manifest, _ = build_ir(index)
    return manifest["tck"]


class TestDeclaredTopology:
    """What the manifest declares is carried into the package verbatim."""

    def test_infrastructure_reaches_the_manifest(self, tmp_path: Path) -> None:
        index = _write_tck(tmp_path, manifest_extra={
            "infrastructure": {
                "engine": {"connector": {"required": True}},
                "sut": {"dtr": {"required": True}},
            },
        })

        assert _tck_section(index)["infrastructure"] == {
            "engine": {"connector": {"required": True}},
            "sut": {"dtr": {"required": True}},
        }

    def test_standard_constraints_survive(self, tmp_path: Path) -> None:
        index = _write_tck(tmp_path, manifest_extra={
            "infrastructure": {
                "sut": {
                    "connector": {
                        "required": True,
                        "standard": {"id": "CX-0018", "version": "v4.2.0"},
                    },
                },
            },
        })

        assert _tck_section(index)["infrastructure"]["sut"]["connector"]["standard"] == {
            "id": "CX-0018",
            "version": "v4.2.0",
        }

    def test_dataspace_reaches_the_manifest(self, tmp_path: Path) -> None:
        index = _write_tck(tmp_path, manifest_extra={
            "dataspace": {"ecosystem": "Catena-X", "version": "jupiter"},
        })

        assert _tck_section(index)["dataspace"] == {
            "ecosystem": "Catena-X",
            "version": "jupiter",
        }


class TestResolvedTopology:
    """The manifest answers what the run needs, not where the author wrote it."""

    def test_per_test_blocks_are_merged_when_the_manifest_states_none(
        self, tmp_path: Path,
    ) -> None:
        index = _write_tck(tmp_path, tests={
            "first.yaml": {"sut": {"connector": {"required": True}}},
            "second.yaml": {"sut": {"dtr": {"required": True}}},
        })

        assert _tck_section(index)["infrastructure"]["sut"] == {
            "connector": {"required": True},
            "dtr": {"required": True},
        }

    def test_a_required_capability_wins_over_an_optional_one(self, tmp_path: Path) -> None:
        index = _write_tck(tmp_path, tests={
            "first.yaml": {"sut": {"dtr": {"required": False}}},
            "second.yaml": {"sut": {"dtr": {"required": True}}},
        })

        assert _tck_section(index)["infrastructure"]["sut"]["dtr"]["required"] is True

    def test_the_manifest_block_wins_over_the_test_blocks(self, tmp_path: Path) -> None:
        index = _write_tck(
            tmp_path,
            manifest_extra={"infrastructure": {"engine": {"connector": {"required": True}}}},
            tests={"first.yaml": {"sut": {"dtr": {"required": True}}}},
        )

        assert _tck_section(index)["infrastructure"]["sut"] == {}


class TestUnstatedTopology:
    """A TCK that states nothing has nothing claimed on its behalf."""

    def test_no_infrastructure_section_when_nothing_is_required(self, tmp_path: Path) -> None:
        assert "infrastructure" not in _tck_section(_write_tck(tmp_path))

    def test_no_dataspace_section_when_no_release_is_named(self, tmp_path: Path) -> None:
        assert "dataspace" not in _tck_section(_write_tck(tmp_path))


class TestRejectedTopology:
    """A package never ships a requirement the engine could not bind."""

    def test_a_capability_the_engine_cannot_bind_fails_the_compile(
        self, tmp_path: Path,
    ) -> None:
        index = _write_tck(tmp_path, manifest_extra={
            "infrastructure": {"sut": {"submodel_server": {"required": True}}},
        })

        with pytest.raises(ValueError, match="index.yaml"):
            build_ir(index)

    def test_a_bad_test_block_names_its_file(self, tmp_path: Path) -> None:
        index = _write_tck(tmp_path, tests={
            "first.yaml": {"engine": {"conector": {"required": True}}},
        })

        with pytest.raises(ValueError, match="tests/first.yaml"):
            build_ir(index)
