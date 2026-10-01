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

"""Which run an inbound call is for: one address per run on a shared mock server.

A process may run several TCKs at once — an engine runs a handful, for
different tenants — and one server answers the mocks of all of them. Two runs
of one TCK register the same path, and two different TCKs may as well. Kept by
path and method alone, the second registration took the first one's place: its
key replaced the first run's, the first run's wait was handed the second run's
listener, and the system under test of one run could end the wait of the other.

So everything a run registers is kept under an address of its own: the path the
test wrote, behind ``/runs/<run id>``. That *key path* is what the registry, the
guards and the callback listeners are kept under, and it is a URL path the
server answers too — a call to ``<server>/runs/<run>/<path>`` reaches that run's
mock and no other. ``mock/api`` hands the system under test that address
(:func:`run_root`).

A call on the bare path — an address a test wired in by hand, or one a host
forwards without the run in it — is still answered when it can be told whose it
is (:func:`pick`): the one run that serves the path, or the one run whose key
the call carries. When neither tells, nothing is guessed: the call is refused
rather than handed to a run it may not be meant for.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlsplit

#: The segment a run's address starts with: ``/runs/<run id>/<path>``.
RUN_SEGMENT = "runs"
_PREFIX = f"/{RUN_SEGMENT}/"

#: The run whose step is executing in this context (:func:`acting_for`).
_current_run: ContextVar[str | None] = ContextVar("testlab_mock_run", default=None)


def scoped(run: str | None, path: str) -> str:
    """The key path *path* is kept under for run *run*; *path* itself for no run.

    Idempotent: a path already under the run's address is returned as it is,
    so a caller holding either form arrives at the same key.
    """
    if not run:
        return path
    root = f"{_PREFIX}{run}"
    if path.startswith(f"{root}/"):
        return path
    return f"{root}{path}"


def split(path: str) -> tuple[str | None, str]:
    """``(run, path as the test wrote it)`` of a key path; ``(None, path)`` outside any run."""
    if not path.startswith(_PREFIX):
        return None, path
    run, slash, rest = path[len(_PREFIX) :].partition("/")
    if not run or not slash:
        return None, path
    return run, f"/{rest}"


def declared(path: str) -> str:
    """*path* as the test wrote it, without a run's address in front of it."""
    return split(path)[1]


def run_root(base_url: str, run: str) -> str:
    """Where run *run*'s mocks are published, given the server's public root *base_url*.

    A root that names the run already is the run's address as it stands: an
    engine hands every run ``<origin>/mock/<job id>`` and serves that prefix
    itself. Any other root — ``http://localhost:<port>``, an operator's public
    origin — gains the run's segment, so two runs never publish one address.
    """
    if run in urlsplit(base_url).path.split("/"):
        return base_url
    return f"{base_url.rstrip('/')}{_PREFIX}{run}"


def current_run() -> str | None:
    """The run whose step is executing right now, or ``None`` outside a step."""
    return _current_run.get()


@contextmanager
def acting_for(run: str) -> Iterator[None]:
    """Register and look up mocks for run *run* while inside this block.

    The step runner wraps every step in it, so a step that registers or reads a
    mock without naming its run — one written before runs had addresses of their
    own — still keeps to its own run's.
    """
    token = _current_run.set(run)
    try:
        yield
    finally:
        _current_run.reset(token)


def pick(
    path: str,
    registered: Collection[str],
    carries: Callable[[str], bool],
) -> str | None:
    """The key path a call on *path* is answered under, or ``None`` when no one run can be told.

    *registered* is every key path something is kept under — a mock, a guard, a
    listener; *carries* says of a key path whether the call carries the key its
    guard requires. In order:

    - a path something is registered under exactly is its own answer — a run's
      address, or a mock registered outside any run;
    - a path under the address of a run that has registered anything is that
      run's, whether or not it serves the path;
    - a bare path is the one run's that serves it, or — when several do — the
      one run's whose key the call carries. Anything else is ``None``: the call
      names no run, and guessing would hand one run's call to another.
    """
    if path in registered:
        return path
    run, _ = split(path)
    if run is not None and any(split(key)[0] == run for key in registered):
        return path
    runs = {owner for owner, rest in map(split, registered) if owner is not None and rest == path}
    if len(runs) <= 1:
        return scoped(next(iter(runs), None), path)
    named = {owner for owner in runs if carries(scoped(owner, path))}
    return scoped(named.pop(), path) if len(named) == 1 else None
