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

"""Secrets a run minted, and the one place that keeps them out of every record.

Header redaction (:mod:`tractusx_testlab.logging.wire.records`) works by name:
``x-api-key`` is a secret whatever it holds. That is not enough for a value the
run itself creates and then hands on. A mock's API key is minted by
``mock/api``, published as a step output, wired into an asset's data address,
sent to the connector's management API in a request *body*, and comes back in
the headers of the call the data plane forwards. Under a header name the tracer
knows it is caught; as ``"header:x-api-key"`` inside a JSON body, as a step
input, or as a returned value, it is not.

So a secret is registered here by value when it is minted, and every sink a
viewer can read — the CloudEvents trace, the events handed to an embedder's
callbacks, the console transcript — passes what it writes through :func:`mask`
first. The value the run keeps is untouched: the step that needs the key still
gets it, only what is written down loses it. Every spelling a record is likely
to carry — escaped, percent-encoded, base64 — is registered with it
(:mod:`tractusx_testlab.logging._secret_pattern`).

A secret is *explicit* when someone said so — a ``secret: true`` variable, a
binding's credential, an output a step marks secret. Those are masked from
:data:`MIN_EXPLICIT_LENGTH` characters, in every string of a structured value,
and as a number when that is how a record holds them. Anything else registered
— a ``hidden: true`` return, a value filed under a credential's name — is
masked from :data:`MIN_SECRET_LENGTH`, so a short word nobody declared does not
vanish from every record that happens to contain it.

The registry is process-wide rather than per run. An engine runs several jobs
in one process, and one run's key showing up in another run's record would be
exactly as wrong as it showing up in its own. It is bounded, so a long-lived
engine does not mask against every key it ever minted: by the time
:data:`MAX_SECRETS` newer ones exist, the run that minted the oldest is over.

That reasoning holds only for a run that is over, so a secret registered *for a
run* (``register_secret(value, run=job_id)``) is pinned: no number of newer
secrets evicts it while the run is open. :func:`release_run` hands the run's
secrets to the bounded registry when it ends, so an event published after the
run closed is still masked. What a run's *author* declared (``declared=True``)
pins at most :data:`MAX_DECLARED_PER_RUN` values, so one test cannot grow the
registry every other run masks against.

Registering costs a set insertion; the pattern is rebuilt by the first
:func:`mask` after the registry changed, not by every registration.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from typing import Any, NamedTuple

from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.logging._secret_pattern import (
    cut_prefixes,
    forms_of,
    mask_cut_prefix,
    pattern_for,
)

#: How many secrets are remembered before the oldest is forgotten.
MAX_SECRETS = 4096

#: Shorter values are not masked. A short string is far more likely to occur by
#: accident — in a path, a count, an id — and masking it would corrupt the
#: record while protecting nothing worth protecting.
MIN_SECRET_LENGTH = 8

#: The floor for a value someone declared secret: short, but said to be one.
MIN_EXPLICIT_LENGTH = 4

#: Most values one run may pin from what its author declared hidden.
MAX_DECLARED_PER_RUN = 256


class _Compiled(NamedTuple):
    pattern: re.Pattern[str]
    #: Explicit secrets, as the text a number in a record would print as.
    numbers: frozenset[str]
    cut_prefixes: dict[str, tuple[str, ...]]
    longest: int


_lock = threading.Lock()
#: Released and unpinned secrets, oldest first — value -> explicit.
_secrets: OrderedDict[str, bool] = OrderedDict()
#: Secrets of runs still open, by run id — never evicted (see the module doc).
_pinned: dict[str, dict[str, bool]] = {}
#: How many declared values each open run has pinned.
_declared: dict[str, int] = {}
_compiled: _Compiled | None = None
_stale = False


def register_secret(
    value: Any,
    run: str | None = None,
    *,
    explicit: bool = False,
    declared: bool = False,
) -> list[str]:
    """Mask *value* wherever a record of the run would otherwise carry it.

    *run* pins it for as long as that run is open (:func:`release_run`).
    *explicit* says it was declared a secret (see the module doc); *declared*
    counts it against the run's :data:`MAX_DECLARED_PER_RUN`. A structured value
    registers every string in it — and every number, when explicit.

    Returns the values the run's allowance turned away: they are not masked
    by value, and the caller masks them where it can (``as_recorded``).
    """
    global _stale
    floor = MIN_EXPLICIT_LENGTH if explicit else MIN_SECRET_LENGTH
    leaves = [leaf for leaf in _leaves(value, explicit) if len(leaf) >= floor]
    if not leaves:
        return []
    withheld: list[str] = []
    with _lock:
        for leaf in leaves:
            if declared and run is not None and not _allowed(run, leaf):
                withheld.append(leaf)
                continue
            for form in forms_of(leaf, floor):
                if run is not None:
                    pins = _pinned.setdefault(run, {})
                    pins[form] = pins.get(form, False) or explicit
                else:
                    _remember(form, explicit)
        _stale = True
    return withheld


def release_run(run: str) -> None:
    """End the pin on *run*'s secrets; they stay masked until newer ones evict them."""
    global _stale
    with _lock:
        for value, explicit in _pinned.pop(run, {}).items():
            _remember(value, explicit)
        _declared.pop(run, None)
        _stale = True


def forget_secrets() -> None:
    """Drop every registered secret. For tests; a run never needs to."""
    global _compiled, _stale
    with _lock:
        _secrets.clear()
        _pinned.clear()
        _declared.clear()
        _compiled = None
        _stale = False


def _leaves(value: Any, numbers: bool) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, int | float):
        return [str(value)] if numbers else []
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list | tuple | set | frozenset):
        return [leaf for item in value for leaf in _leaves(item, numbers)]
    return []


def _allowed(run: str, value: str) -> bool:
    """Whether the run may pin one more declared value — or already pinned this one."""
    if value in _pinned.get(run, {}):
        return True
    if _declared.get(run, 0) >= MAX_DECLARED_PER_RUN:
        return False
    _declared[run] = _declared.get(run, 0) + 1
    return True


def _remember(value: str, explicit: bool) -> None:
    explicit = _secrets.pop(value, False) or explicit
    _secrets[value] = explicit
    while len(_secrets) > MAX_SECRETS:
        _secrets.popitem(last=False)


def _current() -> _Compiled | None:
    """The pattern for the registry as it is now, rebuilt only if it changed."""
    global _compiled, _stale
    if not _stale:
        return _compiled
    with _lock:
        if _stale:
            every: dict[str, bool] = dict(_secrets)
            for pins in _pinned.values():
                for value, explicit in pins.items():
                    every[value] = every.get(value, False) or explicit
            pattern = pattern_for(every)
            _compiled = (
                None
                if pattern is None
                else _Compiled(
                    pattern=pattern,
                    numbers=frozenset(value for value, explicit in every.items() if explicit),
                    cut_prefixes=cut_prefixes(every),
                    longest=max(map(len, every)),
                )
            )
            _stale = False
        return _compiled


def mask(value: Any) -> Any:
    """*value* with every registered secret replaced by the tracer's marker.

    Walks dicts, lists and tuples, and masks keys as well as values — a data
    address spells its extra headers as ``"header:<name>"`` keys, and nothing
    stops a test from building a key out of a value. A number is masked when it
    prints as an explicit secret; anything else that is not a string or a
    container comes back as it was.
    """
    compiled = _current()
    if compiled is None:
        return value
    return _masked(value, compiled)


def mask_also(value: Any, secrets: list[str]) -> Any:
    """*value* masked, and *secrets* with it — values the registry was not given."""
    value = mask(value)
    pattern = pattern_for(
        form for secret in secrets for form in forms_of(secret, MIN_SECRET_LENGTH)
    )
    if pattern is None:
        return value
    return _masked(value, _Compiled(pattern, frozenset(), {}, 0))


def _masked(value: Any, compiled: _Compiled) -> Any:
    if isinstance(value, str):
        text = compiled.pattern.sub(REDACTED_VALUE, value)
        return mask_cut_prefix(text, compiled.cut_prefixes, compiled.longest)
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return REDACTED_VALUE if str(value) in compiled.numbers else value
    if isinstance(value, dict):
        return {_masked(key, compiled): _masked(item, compiled) for key, item in value.items()}
    if isinstance(value, list):
        return [_masked(item, compiled) for item in value]
    if isinstance(value, tuple):
        return tuple(_masked(item, compiled) for item in value)
    return value
