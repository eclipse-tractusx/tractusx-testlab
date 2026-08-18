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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Contract tests for ``digital-twin/submodel/upload`` and ``digital-twin/submodel/delete``.

The submodel server is the engine's, not the script's: what these tests hold to
is that the steps read it from the engine configuration and refuse to run when
there is none, rather than taking an address from whoever wrote the test. The
path under that server is the half a script does decide, so the rest of these
hold the two apart — what the caller chose, and what the engine was configured
with — and hold the steps to publishing both. The delete tests hold the pair
together: what the upload published as ``path`` is what the delete removes.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import StepConfigError, StepDefinition
from tractusx_testlab.models.domain.infrastructure import (
    EngineBindings,
    EngineDtrBinding,
    Infrastructure,
)
from tractusx_testlab.steps.digital_twin.submodel import (
    DeleteBackendDataParams,
    DeleteBackendDataStep,
    UploadBackendDataParams,
    UploadBackendDataStep,
)

_USES = "digital-twin/submodel/upload"
_DELETE_USES = "digital-twin/submodel/delete"
_SEMANTIC_ID = "urn:samm:io.catenax.serial_part:3.0.0#SerialPart"
_ENCODED_SEMANTIC_ID = (
    "urn%3Asamm%3Aio.catenax.serial_part%3A3.0.0%23SerialPart"
)


def _context(submodel_server_url: str) -> MagicMock:
    ctx = MagicMock()
    config = TestlabConfig(
        infrastructure=Infrastructure(
            engine=EngineBindings(
                dtr=EngineDtrBinding(submodel_base_url=submodel_server_url),
            ),
        ),
    )
    ctx.config = config
    ctx.infrastructure = config.infrastructure
    return ctx


def _capture_post(monkeypatch) -> dict[str, object]:
    """Record the request the step makes instead of sending it."""
    captured: dict[str, object] = {}

    async def fake_post(self, url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(201, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return captured


@pytest.mark.asyncio
async def test_it_posts_under_the_configured_server(monkeypatch) -> None:
    captured = _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}, "semantic_id": _SEMANTIC_ID},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    url = str(captured["url"])
    assert url.startswith(f"https://backend.example.com/data/{_ENCODED_SEMANTIC_ID}/urn:uuid:")
    assert captured["json"] == {"test": True}
    assert output.value["backend_url"] == url


@pytest.mark.asyncio
async def test_the_aspect_is_the_segment_the_submodel_is_stored_under(monkeypatch) -> None:
    captured = _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {
            "data": {"test": True},
            "semantic_id": _SEMANTIC_ID,
            "submodel_id": "urn:uuid:00000000-0000-4000-8000-000000000001",
        },
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    # The Industry Core layout: aspect first, then the submodel's own id. A raw
    # '#' in the URN would start a fragment and cut the id off the address, so
    # the aspect segment is percent-encoded — the id is not, because
    # '.../urn:uuid:<uuid4>' is the resource every existing test stores under.
    assert captured["url"] == (
        "https://backend.example.com/data/"
        f"{_ENCODED_SEMANTIC_ID}/urn:uuid:00000000-0000-4000-8000-000000000001"
    )
    assert "%23SerialPart" in str(captured["url"])
    assert output.value["path"] == (
        f"{_ENCODED_SEMANTIC_ID}/urn:uuid:00000000-0000-4000-8000-000000000001"
    )


@pytest.mark.asyncio
async def test_data_with_no_aspect_is_stored_under_the_id_alone(monkeypatch) -> None:
    captured = _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}, "submodel_id": "urn:uuid:abc"},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    # Nothing to group by, so nothing to group under: an empty aspect segment
    # would be a double slash naming a resource nobody asked for.
    assert captured["url"] == "https://backend.example.com/data/urn:uuid:abc"
    assert output.value["path"] == "urn:uuid:abc"
    assert output.value["semantic_id"] is None


@pytest.mark.asyncio
async def test_the_id_the_script_gave_is_the_id_the_data_lands_under(monkeypatch) -> None:
    _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}, "semantic_id": _SEMANTIC_ID, "submodel_id": "urn:uuid:abc"},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    # A descriptor written ahead of the upload names an id; the step has to
    # honour it rather than inventing a UUID the descriptor cannot know.
    assert output.value["submodel_id"] == "urn:uuid:abc"


@pytest.mark.asyncio
async def test_a_generated_id_comes_back_beside_the_path_not_only_inside_it(
    monkeypatch,
) -> None:
    _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}, "semantic_id": _SEMANTIC_ID},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    # A descriptor, a lookup or a delete names the submodel by its id; without
    # this output a script would have to cut the id back out of the URL it is
    # buried in — and out from behind an encoded aspect segment at that.
    submodel_id = output.value["submodel_id"]
    assert submodel_id.startswith("urn:uuid:")
    assert output.value["path"] == f"{_ENCODED_SEMANTIC_ID}/{submodel_id}"


@pytest.mark.asyncio
async def test_it_publishes_the_server_and_the_path_apart(monkeypatch) -> None:
    _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}, "semantic_id": _SEMANTIC_ID, "submodel_id": "urn:uuid:abc"},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    # `source_url` is what an EDC asset is created against and `path` is what a
    # data plane appends to it; joined they are the descriptor's endpoint. A
    # test that only ever saw the joined URL would have to parse it back apart.
    assert output.value["source_url"] == "https://backend.example.com/data"
    assert output.value["path"] == f"{_ENCODED_SEMANTIC_ID}/urn:uuid:abc"
    assert (
        output.value["backend_url"]
        == f"{output.value['source_url']}/{output.value['path']}"
    )


@pytest.mark.parametrize(
    ("given", "stored"),
    [("/urn:uuid:abc/", "urn:uuid:abc"), ("  urn:uuid:abc  ", "urn:uuid:abc"), ("/", None)],
)
def test_surrounding_slashes_are_punctuation_not_id(given: str, stored: str | None) -> None:
    # `/urn:uuid:abc/` and `urn:uuid:abc` name the same submodel; the step must
    # not turn the difference into a double slash or an empty segment.
    assert (
        UploadBackendDataParams(data={"test": True}, submodel_id=given).submodel_id == stored
    )


@pytest.mark.asyncio
async def test_it_publishes_the_aspect_the_payload_claims(monkeypatch) -> None:
    _capture_post(monkeypatch)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}, "semantic_id": _SEMANTIC_ID},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    # The descriptor written next has to carry the same URN (CX-0002); reading
    # it off this step is what keeps the two from being answered twice. It is
    # the URN that comes back, not the encoding the path was built with.
    assert output.value["semantic_id"] == _SEMANTIC_ID


@pytest.mark.parametrize("given", ["", "   "])
def test_a_blank_aspect_is_read_as_no_aspect(given: str) -> None:
    # A blank string names no aspect model; taken at face value it would put an
    # empty segment in the storage path.
    assert UploadBackendDataParams(data={"test": True}, semantic_id=given).semantic_id is None


def test_there_is_no_upload_without_a_payload_to_upload() -> None:
    with pytest.raises(ValidationError) as error:
        UploadBackendDataParams(semantic_id=_SEMANTIC_ID)

    # A default payload would let a script upload a placeholder and then assert
    # against it — a test that passes without the provider's data ever being
    # named. The data is the point of the upload, so the step asks for it.
    assert "data" in str(error.value)


def test_an_id_cannot_name_a_server_of_its_own() -> None:
    with pytest.raises(ValidationError) as error:
        UploadBackendDataParams(
            data={"test": True},
            semantic_id=_SEMANTIC_ID,
            submodel_id="https://elsewhere.example.com/data",
        )

    assert "absolute URL" in str(error.value)


def test_an_id_with_a_slash_is_a_path_not_an_id() -> None:
    with pytest.raises(ValidationError) as error:
        UploadBackendDataParams(
            data={"test": True}, semantic_id=_SEMANTIC_ID, submodel_id="twins/serial-part-1"
        )

    # It would nest the submodel under its own aspect segment rather than name
    # it, and no lookup by that id would find it again.
    assert "not a path" in str(error.value)


@pytest.mark.asyncio
async def test_an_engine_without_a_submodel_server_says_so() -> None:
    with pytest.raises(StepConfigError) as error:
        await UploadBackendDataStep().invoke(
            {"data": {"test": True}, "semantic_id": _SEMANTIC_ID},
            _context(""),
            StepDefinition(id="s", uses=_USES),
        )

    assert "engine.dtr.submodel_base_url" in str(error.value)


def _capture_delete(monkeypatch, status: int = 204) -> dict[str, object]:
    """Record the delete the step makes instead of sending it."""
    captured: dict[str, object] = {}

    async def fake_delete(self, url, headers=None, timeout=None):
        captured["url"] = url
        return httpx.Response(status)

    monkeypatch.setattr(httpx.AsyncClient, "delete", fake_delete)
    return captured


@pytest.mark.asyncio
async def test_the_delete_removes_the_path_the_upload_published(monkeypatch) -> None:
    captured = _capture_delete(monkeypatch)
    path = f"{_ENCODED_SEMANTIC_ID}/urn:uuid:abc"

    await DeleteBackendDataStep().invoke(
        {"path": path},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_DELETE_USES),
    )

    # The teardown is wired straight from the upload: whatever address the data
    # landed on is the address the delete has to reach, encoded aspect segment
    # and all — not one rebuilt from the pieces here.
    assert captured["url"] == f"https://backend.example.com/data/{path}"


@pytest.mark.asyncio
async def test_the_delete_publishes_whether_the_data_was_there(monkeypatch) -> None:
    _capture_delete(monkeypatch, status=404)

    output = await DeleteBackendDataStep().invoke(
        {"path": "urn:uuid:abc"},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_DELETE_USES),
    )

    # 204 and 404 are different answers — one says the submodel was removed, the
    # other that it was already gone — and a teardown assertion is written on
    # that difference, so the code is a declared output and not only an HTTP
    # record.
    assert output.value["status_code"] == 404


@pytest.mark.parametrize("given", [None, "", "   ", "/"])
def test_there_is_nothing_to_delete_without_a_path(given: object) -> None:
    with pytest.raises(ValidationError) as error:
        DeleteBackendDataParams(path=given)

    # A blank path addresses the server itself; a DELETE sent there would ask a
    # provider to drop everything it holds rather than the one submodel.
    assert "'path' is required" in str(error.value)


def test_a_delete_with_no_path_at_all_is_refused() -> None:
    with pytest.raises(ValidationError):
        DeleteBackendDataParams()


def test_a_delete_path_cannot_name_a_server_of_its_own() -> None:
    with pytest.raises(ValidationError) as error:
        DeleteBackendDataParams(path="https://elsewhere.example.com/data/urn:uuid:abc")

    assert "absolute URL" in str(error.value)


@pytest.mark.parametrize(
    ("given", "used"),
    [("/urn:uuid:abc/", "urn:uuid:abc"), ("  urn:uuid:abc  ", "urn:uuid:abc")],
)
def test_surrounding_slashes_are_punctuation_on_a_delete_too(given: str, used: str) -> None:
    # The delete has to reach the same resource the upload wrote, so it reads a
    # path the same way — a trailing slash is not a different submodel.
    assert DeleteBackendDataParams(path=given).path == used


@pytest.mark.asyncio
async def test_a_delete_against_an_engine_without_a_submodel_server_says_so() -> None:
    with pytest.raises(StepConfigError) as error:
        await DeleteBackendDataStep().invoke(
            {"path": "urn:uuid:abc"},
            _context(""),
            StepDefinition(id="s", uses=_DELETE_USES),
        )

    assert "engine.dtr.submodel_base_url" in str(error.value)
