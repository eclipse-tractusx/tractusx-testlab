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

"""An API file is read into JSON data, as its declared type, or refused with the line."""

from __future__ import annotations

import pytest

from tractusx_testlab.openapi.parsing import ParseError, parse

_YAML = "application/vnd.oai.openapi"
_JSON = "application/vnd.oai.openapi+json"


class TestYaml:
    @pytest.mark.parametrize("media_type", [_YAML, "application/yaml"])
    def test_a_yaml_type_reads_yaml(self, media_type: str) -> None:
        assert parse(b"a: 1\nb: [x, true, null]\n", media_type) == {"a": 1, "b": ["x", True, None]}

    def test_an_unquoted_date_stays_text(self) -> None:
        """JSON has no date; ``version: 2024-01-31`` is the string an author meant."""
        assert parse(b"version: 2024-01-31\n", _YAML) == {"version": "2024-01-31"}

    def test_an_integer_key_is_read_as_text(self) -> None:
        """``responses: {200: …}`` is how most documents write a status code."""
        assert parse(b"responses:\n  200: {description: ok}\n", _YAML) == {
            "responses": {"200": {"description": "ok"}}
        }

    def test_a_merge_key_is_still_honoured(self) -> None:
        document = parse(b"base: &b {a: 1}\nmore:\n  <<: *b\n  c: 2\n", _YAML)
        assert document["more"] == {"a": 1, "c": 2}

    @pytest.mark.parametrize(
        ("text", "problem"),
        [
            (b"a: !!python/object:os.system x\n", "python/object"),
            (b"a: !!binary aGk=\n", "tag 'tag:yaml.org,2002:binary' is not allowed"),
            (b"a: !!timestamp 2024-01-01\n", "tag 'tag:yaml.org,2002:timestamp' is not allowed"),
            (b"a: !!set {x}\n", "tag 'tag:yaml.org,2002:set' is not allowed"),
            (b"a: !custom x\n", "!custom"),
        ],
    )
    def test_a_tag_json_cannot_hold_is_refused(self, text: bytes, problem: str) -> None:
        with pytest.raises(ParseError, match="is not valid YAML") as caught:
            parse(text, _YAML)
        assert problem in str(caught.value)

    def test_a_duplicate_key_is_refused_with_its_line(self) -> None:
        with pytest.raises(ParseError, match=r"duplicate key 'a' \(line 3, column 1\)"):
            parse(b"a: 1\nb: 2\na: 3\n", _YAML)

    def test_a_key_that_collapses_onto_another_is_a_duplicate(self) -> None:
        with pytest.raises(ParseError, match="duplicate key '200'"):
            parse(b"'200': x\n200: y\n", _YAML)

    @pytest.mark.parametrize("key", [b"true", b"null", b"1.5"])
    def test_a_key_that_is_not_text_is_refused(self, key: bytes) -> None:
        with pytest.raises(ParseError, match="is not text; quote it"):
            parse(key + b": x\n", _YAML)

    @pytest.mark.parametrize("value", [b".nan", b".inf", b"-.inf"])
    def test_a_number_json_cannot_hold_is_refused(self, value: bytes) -> None:
        with pytest.raises(ParseError, match="is not a JSON number"):
            parse(b"a: " + value + b"\n", _YAML)

    def test_two_documents_in_one_file_are_refused(self) -> None:
        with pytest.raises(ParseError, match="is not valid YAML"):
            parse(b"a: 1\n---\nb: 2\n", _YAML)

    def test_a_syntax_error_names_its_line(self) -> None:
        with pytest.raises(ParseError, match=r"expected .*\(line 3, column 1\)"):
            parse(b"a: 1\nb: [unclosed\n", _YAML)


class TestJson:
    @pytest.mark.parametrize("media_type", [_JSON, "application/json"])
    def test_a_json_type_reads_json(self, media_type: str) -> None:
        assert parse(b'{"a": [1, 2.5, "x"]}', media_type) == {"a": [1, 2.5, "x"]}

    def test_a_byte_order_mark_is_tolerated(self) -> None:
        assert parse(b'\xef\xbb\xbf{"a": 1}', _JSON) == {"a": 1}

    def test_a_json_type_does_not_accept_yaml(self) -> None:
        with pytest.raises(ParseError, match=r"is not valid JSON: .*\(line 1, column 1\)"):
            parse(b"a: 1\n", _JSON)

    def test_a_duplicate_key_is_refused(self) -> None:
        with pytest.raises(ParseError, match="duplicate key 'a'"):
            parse(b'{"a": 1, "a": 2}', _JSON)

    @pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
    def test_a_constant_python_accepts_and_json_does_not_is_refused(self, constant: bytes) -> None:
        with pytest.raises(ParseError, match="is not a JSON number"):
            parse(b'{"a": ' + constant + b"}", _JSON)

    def test_nesting_too_deep_to_read_is_refused_not_crashed(self) -> None:
        with pytest.raises(ParseError, match="nests too deeply"):
            parse(b"[" * 100_000 + b"]" * 100_000, _JSON)


class TestText:
    def test_bytes_that_are_not_utf8_are_refused(self) -> None:
        with pytest.raises(ParseError, match=r"is not UTF-8 text \(invalid byte at offset 3\)"):
            parse(b"a: \xff\n", _YAML)

    def test_an_unknown_type_is_refused(self) -> None:
        with pytest.raises(ParseError, match="unknown type 'text/plain'"):
            parse(b"{}", "text/plain")
