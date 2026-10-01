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

"""A credential handle renders as ``***`` everywhere and opens for its own origin only."""

from __future__ import annotations

import copy
import json
import pickle
from typing import Any

import pytest
from pydantic import BaseModel

from tractusx_testlab.security.credentials import (
    Credential,
    CredentialNotReleasedError,
    CredentialOriginMismatchError,
    find_credential,
    origin_of,
)

_SECRET = "platform-management-key-0123"
_NAME = "infrastructure.engine.connector.api_key"
_BOTH = frozenset({"engine", "sut"})


def _handle(origin: str = "https://connector.example.com:443", side: str = "engine") -> Credential:
    return Credential(_SECRET, name=_NAME, side=side, origins=[origin])


class TestRendering:
    def test_str_and_format_show_the_marker(self) -> None:
        handle = _handle()
        assert str(handle) == "***"
        assert f"key={handle}" == "key=***"

    def test_repr_names_the_reference_not_the_value(self) -> None:
        assert repr(_handle()) == f"Credential({_NAME}=***)"
        assert _SECRET not in repr(_handle())

    def test_json_dumps_with_a_str_fallback_writes_the_marker(self) -> None:
        assert json.dumps({"k": _handle()}, default=str) == '{"k": "***"}'

    def test_pydantic_dumps_it_as_the_marker_in_an_untyped_field(self) -> None:
        class Holder(BaseModel):
            inputs: dict[str, Any]

        holder = Holder(inputs={"headers": {"x-api-key": _handle()}})
        assert holder.model_dump()["inputs"]["headers"]["x-api-key"] == "***"
        assert holder.model_dump(mode="json")["inputs"]["headers"]["x-api-key"] == "***"
        assert _SECRET not in holder.model_dump_json()

    def test_pydantic_admits_it_as_itself_in_a_typed_field(self) -> None:
        class Holder(BaseModel):
            key: Credential

        handle = _handle()
        holder = Holder(key=handle)
        assert holder.key is handle
        assert holder.model_dump_json() == '{"key":"***"}'

    def test_it_cannot_be_pickled(self) -> None:
        with pytest.raises(TypeError):
            pickle.dumps(_handle())

    def test_copies_are_the_same_handle(self) -> None:
        handle = _handle()
        assert copy.copy(handle) is handle
        assert copy.deepcopy({"k": handle})["k"] is handle

    def test_it_is_immutable(self) -> None:
        with pytest.raises(AttributeError):
            _handle()._value = "other"  # type: ignore[misc]

    def test_it_is_never_equal_to_its_value(self) -> None:
        assert _handle() != _SECRET


class TestOrigin:
    @pytest.mark.parametrize(
        ("url", "origin"),
        [
            ("https://connector.example.com/management", "https://connector.example.com:443"),
            ("HTTPS://Connector.Example.com:443/x", "https://connector.example.com:443"),
            ("http://connector:8081/management", "http://connector:8081"),
            ("http://connector/management", "http://connector:80"),
            ("https://connector.example.com@evil.io/x", "https://evil.io:443"),
        ],
    )
    def test_the_origin_is_scheme_host_and_explicit_port(self, url: str, origin: str) -> None:
        assert origin_of(url) == origin

    @pytest.mark.parametrize("url", ["", "connector.example.com/x", "ftp://host/x", "/relative"])
    def test_anything_but_an_absolute_http_url_has_no_origin(self, url: str) -> None:
        assert origin_of(url) == ""


class TestRelease:
    def test_it_opens_for_its_own_origin(self) -> None:
        handle = _handle()
        assert handle.reveal_for("https://connector.example.com/management/v3/assets", _BOTH) == (
            _SECRET
        )

    @pytest.mark.parametrize(
        "url",
        [
            "https://connector.example.com.evil.io/management",
            "https://evil.io/?u=https://connector.example.com",
            "https://connector.example.com@evil.io/management",
            "http://connector.example.com/management",
            "https://connector.example.com:8443/management",
            "https://sub.connector.example.com/management",
            "not a url",
        ],
    )
    def test_it_refuses_any_other_origin(self, url: str) -> None:
        with pytest.raises(CredentialOriginMismatchError) as caught:
            _handle().reveal_for(url, _BOTH)
        assert caught.value.code == "CREDENTIAL_ORIGIN_MISMATCH"
        assert "may only be sent to https://connector.example.com:443" in str(caught.value)
        assert _SECRET not in str(caught.value)

    def test_a_side_the_run_keeps_back_is_refused_before_the_url_is_read(self) -> None:
        with pytest.raises(CredentialNotReleasedError) as caught:
            _handle().reveal_for("https://connector.example.com/management", {"sut"})
        assert caught.value.code == "CREDENTIAL_NOT_RELEASED"

    def test_a_released_sut_handle_still_opens(self) -> None:
        handle = _handle(side="sut")
        assert handle.reveal_for("https://connector.example.com/x", {"sut"}) == _SECRET

    def test_a_handle_without_an_origin_opens_nowhere(self) -> None:
        handle = Credential(_SECRET, name=_NAME, side="engine", origins=[""])
        with pytest.raises(CredentialOriginMismatchError):
            handle.reveal_for("https://connector.example.com/x", _BOTH)


def test_find_credential_reaches_into_documents() -> None:
    handle = _handle()
    assert find_credential({"a": [1, {"b": (handle,)}]}) is handle
    assert find_credential({"a": ["x"]}) is None
