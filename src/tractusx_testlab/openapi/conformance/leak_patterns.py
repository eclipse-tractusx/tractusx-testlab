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

"""What an error answer must not give away about the server behind it.

Each pattern names one kind of leak and is written for few false positives:
keywords are matched case-sensitively where a server writes them so (SQL in
capitals, exception class names in CamelCase), paths only with a source-file
extension or a well-known runtime directory, addresses only in the private
ranges. None has a nested or overlapping quantifier, and every repetition is
bounded, so a scan is linear in the text it reads — an answer chosen to make
the check backtrack cannot stall the run. At most :data:`SCAN_CHARS` of each
answer are read.

=================  ===========================================================
kind               matches
=================  ===========================================================
stack_trace        a Python traceback or frame, a Java/Kotlin frame, a .NET
                   frame, a Node.js frame, a Go panic, a PHP stack trace
exception_class    a fully-qualified exception class (``java.lang.IllegalState
                   Exception``) or a well-known runtime one (``KeyError``,
                   ``NullPointerException``, ``TypeError: Cannot read``)
sql                a SQL statement fragment or a database driver's error text
file_path          an absolute path to a source file, or into a runtime's
                   library directory (``site-packages``, ``node_modules``)
private_address    an RFC 1918 / link-local IPv4 address
internal_host      a cluster-internal host name (``*.svc.cluster.local``,
                   ``*.internal``, ``*.local``, ``*.corp``)
=================  ===========================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Characters of one answer that are scanned.
SCAN_CHARS = 64 * 1024
#: Characters around a match a finding quotes.
EXCERPT_CHARS = 60

_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "stack_trace",
        re.compile(
            r"Traceback \(most recent call last\)"
            r"|File \"[^\"\n]{1,300}\", line \d{1,7}"
            r"|\bat [\w$]{1,100}(?:\.[\w$<>]{1,100}){1,30}\([\w$]{1,100}\.(?:java|kt|scala):\d{1,7}\)"
            r"|\bat [\w.]{1,300}\([^)\n]{0,300}\) in [^\n]{1,300}:line \d{1,7}"
            r"|\bat [^\s()]{1,200} \((?:/|[A-Za-z]:\\|file:)[^)\n]{1,300}:\d{1,7}:\d{1,7}\)"
            r"|goroutine \d{1,7} \[[a-z ]{1,30}\]:"
            r"|Stack trace:\s{0,10}#0 "
        ),
    ),
    (
        "exception_class",
        re.compile(
            r"\b(?:java|javax|jakarta|org|com|io|net|kotlin|scala|System|Microsoft)"
            r"(?:\.[a-z_][\w]{0,60}){1,10}\.[A-Z]\w{0,80}(?:Exception|Error)\b"
            r"|\b(?:NullPointerException|IllegalArgumentException|IllegalStateException"
            r"|ClassCastException|NumberFormatException|ArrayIndexOutOfBoundsException"
            r"|ConcurrentModificationException|NullReferenceException|KeyError|AttributeError"
            r"|IndexError|ZeroDivisionError|UnboundLocalError|RecursionError)\b"
            r"|\b(?:TypeError|ReferenceError|RangeError): (?:Cannot|Invalid|undefined|null)"
        ),
    ),
    (
        "sql",
        re.compile(
            r"\bSELECT\b[^;\n]{1,200}?\bFROM\b"
            r"|\bINSERT INTO\b|\bDELETE FROM\b|\bUPDATE \w{1,64} SET\b"
            r"|SQLSTATE\[|\bORA-\d{5}\b|\bPSQLException\b|\bSQLException\b"
            r"|syntax error at or near|You have an error in your SQL syntax"
            r"|\b(?:psycopg2|sqlalchemy|sqlite3)\.\w"
        ),
    ),
    (
        "file_path",
        re.compile(
            r"(?:^|[\s\"'(=:])(?:/[\w.@-]{1,100}){1,30}\.(?:py|java|kt|js|ts|go|rb|php|cs|scala|class|jar)\b"
            r"|[A-Za-z]:\\(?:[\w .-]{1,100}\\){1,30}[\w .-]{1,100}"
            r"|/(?:site|dist)-packages/|/node_modules/|/usr/(?:local/)?lib/|/home/[\w.-]{1,64}/"
        ),
    ),
    (
        "private_address",
        re.compile(
            rf"(?<![\d.])(?:10\.{_OCTET}|172\.(?:1[6-9]|2\d|3[01])|192\.168|169\.254)"
            rf"\.{_OCTET}\.{_OCTET}(?![\d.]\d)"
        ),
    ),
    (
        "internal_host",
        re.compile(
            r"\b[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]{1,63}){0,5}"
            r"\.(?:svc\.cluster\.local|cluster\.local|svc|internal|local|lan|corp|intranet)\b"
            r"(?![.-]?\w)"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class Leak:
    """One leak found in an answer: what kind, and a clipped quote of it."""

    kind: str
    excerpt: str


def leaks_in(text: str) -> list[Leak]:
    """Every kind of leak in the first :data:`SCAN_CHARS` of *text*, once per kind."""
    sample = text[:SCAN_CHARS]
    found: list[Leak] = []
    for kind, pattern in LEAK_PATTERNS:
        match = pattern.search(sample)
        if match is not None:
            excerpt = match.group(0).strip()
            if len(excerpt) > EXCERPT_CHARS:
                excerpt = excerpt[: EXCERPT_CHARS - 1] + "…"
            found.append(Leak(kind, excerpt))
    return found
