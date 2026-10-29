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

"""Leak detection: what it catches, what it leaves alone, and that it stays linear."""

from __future__ import annotations

import time

import pytest

from tractusx_testlab.openapi.conformance import leaks_in


def _kinds(text: str) -> list[str]:
    return [leak.kind for leak in leaks_in(text)]


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ('Traceback (most recent call last):\n  File "/app/main.py", line 12', "stack_trace"),
        ('File "/srv/api/handlers.py", line 88, in get_part', "stack_trace"),
        ("at com.example.parts.PartService.find(PartService.java:42)", "stack_trace"),
        ("at Parts.Api.Find() in C:\\src\\Parts\\Api.cs:line 17", "stack_trace"),
        ("at Object.handler (/usr/src/app/index.js:10:5)", "stack_trace"),
        ("goroutine 1 [running]:", "stack_trace"),
        ("java.lang.IllegalStateException: no part", "exception_class"),
        ("org.hibernate.exception.ConstraintViolationException", "exception_class"),
        ("KeyError: 'manufacturerId'", "exception_class"),
        ("TypeError: Cannot read properties of undefined", "exception_class"),
        ("SELECT id, name FROM parts WHERE id = 7", "sql"),
        ('ERROR: syntax error at or near "FROM"', "sql"),
        ("ORA-00942: table or view does not exist", "sql"),
        ("sqlalchemy.exc.IntegrityError", "sql"),
        ("failed at /opt/app/services/parts.py", "file_path"),
        ("C:\\inetpub\\wwwroot\\api\\web.config", "file_path"),
        ("/usr/lib/python3.12/site-packages/fastapi/routing.py", "file_path"),
        ("upstream 10.42.0.17 refused", "private_address"),
        ("connect to 192.168.1.20:5432 failed", "private_address"),
        ("host 172.20.3.4 down", "private_address"),
        ("postgres.ich.svc.cluster.local:5432", "internal_host"),
        ("redis-master.cache.internal", "internal_host"),
    ],
)
def test_a_leak_is_found(text: str, kind: str) -> None:
    assert kind in _kinds(text)


@pytest.mark.parametrize(
    "text",
    [
        '{"title": "Not Found", "status": 404, "detail": "No part with id 7."}',
        "Select a file from the list.",
        "The value must be one of: select, from, where.",
        "Version 10.2.3 of the API is required.",
        "See https://example.com/docs/errors/not-found for details.",
        '{"instance": "/v1/part-management/catalog-part/BPNL0001/7"}',
        "Rate limit exceeded; retry after 30 seconds.",
        "Invalid value for 'type': expected one of A, B.",
        "Contact support@example.com.",
        "IP 8.8.8.8 is not allowed",
        "172.15.0.1 and 172.32.0.1 are public",
        "The field 'manufacturerPartId' is required.",
        "A validation error occurred (ValidationError) in field 'name'.",
    ],
)
def test_an_ordinary_error_message_is_not_a_leak(text: str) -> None:
    assert _kinds(text) == []


def test_each_kind_is_reported_once_with_a_clipped_excerpt() -> None:
    leaks = leaks_in("10.0.0.1 10.0.0.2 " + "SELECT " + "x" * 150 + " FROM t")
    assert [leak.kind for leak in leaks] == ["sql", "private_address"]
    assert all(len(leak.excerpt) <= 60 for leak in leaks)


@pytest.mark.parametrize(
    "hostile",
    [
        "a" * 200_000,
        "at " + "a." * 50_000,
        "/" + "a/" * 50_000,
        "SELECT " + "x" * 100_000,
        "1." * 100_000,
        "a-" * 100_000 + ".local",
        'File "' + "x" * 100_000,
    ],
)
def test_a_hostile_answer_is_scanned_in_bounded_time(hostile: str) -> None:
    started = time.perf_counter()
    leaks_in(hostile)
    assert time.perf_counter() - started < 1.0
