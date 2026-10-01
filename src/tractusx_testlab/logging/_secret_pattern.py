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

"""How a set of registered secrets is looked for in text, and in which spellings.

The registry (:mod:`tractusx_testlab.logging.masking`) decides *which* values are
secret; this module decides what finding one in a record means. Three things,
each a way a value escaped a mask that only knew its plain spelling:

* **Spellings.** A value is rarely written down as it was handed over. An HTTP
  client that refuses a header quotes it with ``repr`` (a trailing newline
  becomes ``\\n``), a JSON document escapes it, a URL percent-encodes it, a
  basic credential base64-encodes it. :func:`forms_of` gives every spelling a
  record is likely to carry, so each is masked as the value itself is.
* **One pass over the text.** A long-lived engine masks against a thousand
  secrets or more. An alternation of a thousand literals is tried literal by
  literal at every position of every event; :func:`pattern_for` folds the
  secrets into a trie first, so a position costs the length of the longest
  common prefix rather than the number of secrets. The longest secret that
  matches at a position is still the one masked.
* **A cut secret.** The tracer clips a long body and appends
  ``...[truncated N chars]``. A secret that straddled the cut is no longer
  whole, so the full-value pattern misses the part that was kept;
  :func:`mask_cut_prefix` masks a prefix of a secret — at least
  :data:`MIN_CUT_PREFIX` characters — that ends exactly at a cut.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterable
from urllib.parse import quote, quote_plus

from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

#: The shortest part of a secret worth masking where a cut took the rest of it.
MIN_CUT_PREFIX = 8

#: The marker the tracer puts where it clipped a string (``TRUNCATED_MARKER``).
_CUT = re.compile(r"\.\.\.\[truncated \d+ chars\]")

#: Deeper than this, a trie pattern is not worth the parser's recursion: the
#: plain alternation of literals is used instead, with the same result.
_MAX_NESTING = 200


def forms_of(value: str, floor: int) -> list[str]:
    """Every spelling of *value* a record may carry, the value itself last.

    A spelling is kept only when it differs from the value and is at least
    *floor* characters long — a shorter one would mask by accident. The value
    comes last so that, of all its spellings, it is the newest in the registry
    and the last to be evicted.
    """
    raw = value.encode("utf-8", errors="surrogatepass")
    encoded = base64.b64encode(raw).decode("ascii")
    url_safe = base64.urlsafe_b64encode(raw).decode("ascii")
    candidates = (
        value.strip(),
        repr(value)[1:-1],
        json.dumps(value)[1:-1],
        quote(value, safe=""),
        quote(value),
        quote_plus(value),
        encoded,
        encoded.rstrip("="),
        url_safe,
        url_safe.rstrip("="),
    )
    forms = list(dict.fromkeys(form for form in candidates if form != value and len(form) >= floor))
    forms.append(value)
    return forms


def pattern_for(secrets: Iterable[str]) -> re.Pattern[str] | None:
    """One pattern matching any of *secrets*, the longest first at a position."""
    ordered = sorted(set(secrets), key=len, reverse=True)
    if not ordered:
        return None
    trie: dict[str, dict] = {}
    for secret in ordered:
        node = trie
        for char in secret:
            node = node.setdefault(char, {})
        node[""] = {}
    try:
        return re.compile(_branches(trie, 0))
    except (RecursionError, re.error):
        return re.compile("|".join(re.escape(secret) for secret in ordered))


def _branches(node: dict[str, dict], depth: int) -> str:
    """The pattern below *node*: a greedy optional tail where a secret also ends."""
    if depth > _MAX_NESTING:
        raise RecursionError("secret trie too deep")
    parts: list[str] = []
    for char, child in node.items():
        if char == "":
            continue
        text = char
        while len(child) == 1 and "" not in child:
            ((char, child),) = child.items()
            text += char
        parts.append(re.escape(text) + _branches(child, depth + 1))
    if not parts:
        return ""
    body = parts[0] if len(parts) == 1 else f"(?:{'|'.join(parts)})"
    return f"(?:{body})?" if "" in node else body


def cut_prefixes(secrets: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Secrets long enough to be cut, by their first :data:`MIN_CUT_PREFIX` characters."""
    index: dict[str, list[str]] = {}
    for secret in secrets:
        if len(secret) > MIN_CUT_PREFIX:
            index.setdefault(secret[:MIN_CUT_PREFIX], []).append(secret)
    return {head: tuple(found) for head, found in index.items()}


def mask_cut_prefix(text: str, prefixes: dict[str, tuple[str, ...]], longest: int) -> str:
    """*text* with any secret's prefix that ends at a truncation marker masked.

    Only where the tracer cut a string, so a text without a marker costs one
    substring test. The longest prefix that ends at the marker wins.
    """
    if not prefixes or "...[truncated " not in text:
        return text
    pieces: list[str] = []
    start = 0
    for cut in _CUT.finditer(text):
        before = text[start : cut.start()]
        window = max(0, len(before) - longest)
        for position in range(window, len(before) - MIN_CUT_PREFIX + 1):
            tail = before[position:]
            heads = prefixes.get(tail[:MIN_CUT_PREFIX], ())
            if any(secret.startswith(tail) for secret in heads):
                before = before[:position] + REDACTED_VALUE
                break
        pieces.append(before)
        pieces.append(cut.group())
        start = cut.end()
    pieces.append(text[start:])
    return "".join(pieces)
