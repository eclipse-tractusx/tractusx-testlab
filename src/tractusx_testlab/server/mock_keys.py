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

"""What a mock requires of a caller: the run's API key, and why a call lacks it.

Every mock ``mock/api`` registers requires the key of the run that registered
it, in a header; a mock behind a connector asset gets it into the asset's
private data address, so only a call through the connector carries it. This
module mints the keys, keeps what each address requires, and says of a call
whether it may be answered — and if not, why.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import OrderedDict

# path+method -> (header name, lower-cased; the value a caller must send in it)
_guards: dict[str, tuple[str, str]] = {}

# run id -> the key every mock of that run requires; bounded like logging.masking
_run_keys: OrderedDict[str, str] = OrderedDict()
_MAX_RUN_KEYS = 1024

# The BLAKE2b key a mock API key is derived under: random per process and never
# written anywhere, so knowing a run's id and when it started is not enough to
# recompute its key. Keys only need to outlive the process that serves them.
_KEY_SALT = secrets.token_bytes(hashlib.blake2b.MAX_KEY_SIZE)
# Domain separation, so the same inputs hashed for another purpose never
# produce a mock key (BLAKE2b's personalisation, at most 16 bytes).
_KEY_PERSON = b"testlab-mock-key"
_KEY_NONCE_BYTES = 32


def _key(path: str, method: str) -> str:
    return f"{method.upper()}:{path}"


def run_key(run_id: str) -> str:
    """The key every mock of run *run_id* requires, minted on first use.

    One per run rather than one per mock: an asset carries one key in its data
    address, and one asset may front several mocks — CX-0135's CCMAPI serves
    push and status — or a mock re-armed between two waits. A new run is a new
    key, so an offer an earlier run left behind forwards one no mock accepts.
    """
    key = _run_keys.get(run_id)
    if key is None:
        key = _run_keys[run_id] = _mint_key(run_id)
        while len(_run_keys) > _MAX_RUN_KEYS:
            _run_keys.popitem(last=False)
    return key


def _mint_key(run_id: str) -> str:
    """A 256-bit BLAKE2b digest of a fresh nonce, the run id and the time.

    The message is ``nonce ‖ run id ‖ nanosecond timestamp``, hashed with the
    per-process secret salt as the BLAKE2b key (keyed hashing, i.e. a MAC) and
    a fixed personalisation. The nonce — 32 bytes from the operating system's
    CSPRNG — comes first and carries the unpredictability on its own; the salt
    means the digest cannot be recomputed outside this process even from a
    known nonce; the run id and timestamp bind the key to the run it was minted
    for and make two mintings distinct by construction. Hex-encoded: 64
    characters, safe in any HTTP header.
    """
    nonce = secrets.token_bytes(_KEY_NONCE_BYTES)
    message = b"\x00".join((nonce, run_id.encode("utf-8"), str(time.time_ns()).encode()))
    return hashlib.blake2b(message, key=_KEY_SALT, digest_size=32, person=_KEY_PERSON).hexdigest()


def require_header(path: str, method: str, header: str, value: str) -> None:
    """Admit a call on *path*/*method* only when it carries *value* in *header*.

    For a mock that stands behind a connector: its address is published, so
    anyone who reads the run can dial it, but only the connector's data plane
    was given the value — it sits in the private data address of the asset the
    system under test negotiates. A call without it did not come through the
    connector, and the mock refuses it rather than let it pass for one that did.
    """
    _guards[_key(path, method)] = (header.lower(), value)


def required_header(path: str, method: str) -> tuple[str, str] | None:
    """The ``(name, value)`` a call on *path*/*method* must carry, or ``None``.

    Read by the step that fronts a mock with a connector asset: it hands the
    same pair to the asset's data address, so the data plane sends what the
    mock requires without the test ever naming the key.
    """
    return _guards.get(_key(path, method))


#: Why a call was turned away, as the wait that fails on it says. Neither names
#: the header or the value the mock expects.
MISSING_KEY = "the call carried no API key"
WRONG_KEY = "the call carried an API key that is not this run's"


def admits(path: str, method: str, headers: dict) -> bool:
    """Whether a call on *path*/*method* with *headers* may reach the mock.

    ``True`` for a mock nothing was required of. Header names are compared
    without regard to case, as HTTP does; the value in constant time.
    """
    return refusal(path, method, headers) is None


def refusal(path: str, method: str, headers: dict) -> str | None:
    """Why a call on *path*/*method* with *headers* may not reach the mock, or ``None``.

    Two findings, told apart because they send the reader to different places:
    no key at all is a call that skipped the connector, a wrong one is a call
    that was forged or replayed from another run.
    """
    guard = _guards.get(_key(path, method))
    if guard is None:
        return None
    name, expected = guard
    sent = _header(headers, name)
    if sent is None:
        return MISSING_KEY
    if not hmac.compare_digest(sent.encode(), expected.encode()):
        return WRONG_KEY
    return None


def carries_key_of(path: str, method: str, headers: dict) -> bool:
    """Whether *headers* carry the key the mock on *path*/*method* requires.

    Asked of a call that reached no mock at all: one carrying a waiting mock's
    key was made for that mock's run and sent to the wrong address. ``False``
    for a mock that requires nothing — its callers cannot be told apart.
    """
    guard = _guards.get(_key(path, method))
    if guard is None:
        return False
    name, expected = guard
    sent = _header(headers, name)
    return sent is not None and hmac.compare_digest(sent.encode(), expected.encode())


def _header(headers: dict, name: str) -> str | None:
    """The value of header *name* in *headers*, whatever case either is written in."""
    return next((str(value) for key, value in headers.items() if str(key).lower() == name), None)


def drop_guard(path: str, method: str) -> None:
    """Require nothing more of a caller on *path*/*method*."""
    _guards.pop(_key(path, method), None)


def clear_guards() -> None:
    """Require nothing of any caller — the mocks they guarded are gone."""
    _guards.clear()
