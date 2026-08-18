###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Tests for ADR-0019 dataspace/infrastructure parsing and reference resolution."""

from __future__ import annotations

import pytest

from tractusx_testlab.compiler.validation._expressions import resolve_expression
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    DataspaceContext,
    InfrastructureConfig,
)
from tractusx_testlab.scripting.parser import YamlParser


def _doc() -> dict:
    return {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "infra-doc",
        "namespace": "testlab.test",
        "metadata": {"name": "infra-doc", "version": "1.0"},
        "dataspace": {"ecosystem": "Catena-X", "version": "saturn"},
        "infrastructure": {
            "engine": {"connector": {"required": True}},
            "sut": {
                "connector": {"required": True, "standard": {"id": "CX-0018", "version": "2.1.3"}},
                "dtr": {"required": True},
            },
        },
        "execution": [],
    }


class TestDataspaceParsing:
    """The dataspace block becomes the single source of the dataspace version."""

    def test_dataspace_block_parses_into_model(self) -> None:
        script = YamlParser.parse_script_from_dict(_doc())

        assert script.dataspace == DataspaceContext(ecosystem="Catena-X", version="saturn")

    def test_dataspace_version_wins_over_default(self) -> None:
        doc = _doc()
        doc["dataspace"]["version"] = "jupiter"

        script = YamlParser.parse_script_from_dict(doc)

        assert script.dataspace.version == "jupiter"

    def test_legacy_string_dataspace_is_rejected(self) -> None:
        from pydantic import ValidationError

        doc = _doc()
        doc["dataspace"] = "saturn"  # legacy string form — must be a dict

        with pytest.raises(ValidationError):
            YamlParser.parse_script_from_dict(doc)


class TestInfrastructureParsing:
    """The infrastructure block parses into the keyed-capability model."""

    def test_sides_keep_capability_keys(self) -> None:
        script = YamlParser.parse_script_from_dict(_doc())

        assert script.infrastructure == InfrastructureConfig(
            engine={"connector": CapabilityRequirement(required=True)},
            sut={
                "connector": CapabilityRequirement(
                    required=True,
                    standard={"id": "CX-0018", "version": "2.1.3"},
                ),
                "dtr": CapabilityRequirement(required=True),
            },
        )

    def test_standard_version_inherits_dataspace_version(self) -> None:
        doc = _doc()
        del doc["infrastructure"]["sut"]["connector"]["standard"]["version"]

        script = YamlParser.parse_script_from_dict(doc)
        standard = script.infrastructure.sut["connector"].standard

        assert standard.version is None
        assert standard.effective_version(script.dataspace.version) == "saturn"

    def test_unknown_capability_key_is_rejected(self) -> None:
        doc = _doc()
        doc["infrastructure"]["engine"]["mock_server"] = {"required": True}

        with pytest.raises(ValueError):
            YamlParser.parse_script_from_dict(doc)

    @pytest.mark.parametrize("side", ["engine", "sut"])
    def test_the_submodel_server_is_not_a_capability_of_its_own(self, side: str) -> None:
        """It is part of the registry requirement — ``engine.dtr`` covers it."""
        doc = _doc()
        doc["infrastructure"][side]["submodel_server"] = {"required": True}

        with pytest.raises(ValueError, match="submodel_server"):
            YamlParser.parse_script_from_dict(doc)

    def test_unknown_side_is_rejected(self) -> None:
        doc = _doc()
        doc["infrastructure"]["backend"] = {"connector": {"required": True}}

        with pytest.raises(ValueError):
            YamlParser.parse_script_from_dict(doc)


class TestInfrastructureReferenceResolution:
    """`${{ infrastructure.* }}` resolves to a canonical $ref, never under env."""

    def test_capability_handle_resolves_verbatim(self) -> None:
        result = resolve_expression("${{ infrastructure.engine.connector }}")

        assert result == {"$ref": "infrastructure.engine.connector"}

    def test_binding_field_path_resolves_verbatim(self) -> None:
        result = resolve_expression("${{ infrastructure.sut.connector.counter_party_address }}")

        assert result == {"$ref": "infrastructure.sut.connector.counter_party_address"}
