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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""What the operator still owes, said in one message instead of one per run.

Every error here is the same shape of problem: TestLab was pointed at a
deployment, or handed a set of values, that does not add up — a capability with
no address behind it, an input the TCK cannot invent, a key that names no field,
a binding that contradicts what the TCK certifies against. None of them is a
verdict about the system under test and none of them is a TestLab defect, which
is why they are all :class:`AuthoringError`: nothing was proved either way.

They are grouped here rather than among the runtime errors because what makes
them useful is not the type but the message. An operator reading one is trying
to answer a single question — *what do I have to write in my config?* — and the
answer is only worth reading if it is the whole list, scoped to the run they
attempted.
"""

from __future__ import annotations

import difflib

from tractusx_testlab.models.primitives.exceptions import AuthoringError


def _env_hint(context_key: str) -> str:
    """Return the environment-variable form of a context key, as a trailing hint."""
    _, _, rest = context_key.partition(".")
    if not rest:
        return ""
    return f"   (or TESTLAB_{rest.replace('.', '_').upper()})"


def _did_you_mean(key: str, known: list[str]) -> str:
    """Return a suggestion block for the legal keys closest to *key*, if any."""
    close = difflib.get_close_matches(key, known, n=3, cutoff=0.7)
    if not close:
        return ""
    return "\n  Did you mean:\n" + "\n".join(f"      {match}" for match in close)


def _owed_block(keys: list[str], heading: str) -> str:
    """Return a block listing the keys an operator still owes, if any."""
    if not keys:
        return ""
    return f"\n  {heading}:\n" + "\n".join(f"      {key}{_env_hint(key)}" for key in keys)


class InfrastructureError(AuthoringError):
    """Base for problems with the infrastructure bindings an engine was given."""


class UnknownBindingKeyError(InfrastructureError):
    """Raised when a binding key names no field of the infrastructure model.

    A misspelled key used to be dropped in silence and surface as an empty URL
    several steps later, so the key is rejected where it is written.

    What is printed beside it is what the operator can act on: the closest
    legal key when the mistake is a typo, and the keys *this TCK* actually
    needs. The full model has twenty-odd fields and no TCK requires all of
    them, so listing every accepted key answers a question nobody asked and
    buries the one line that would have fixed the config.
    """

    def __init__(self, key: str, known: list[str], needed: list[str] | None = None) -> None:
        self.key = key
        self.known = known
        self.needed = needed or []
        super().__init__(
            f"Unknown infrastructure binding key: '{key}'."
            + _did_you_mean(key, known)
            + _owed_block(self.needed, "This TCK needs")
        )


class MissingBindingError(InfrastructureError):
    """Raised before the first step when a required capability is not fully bound.

    Reports every capability at once and, within each, every field the
    operator still owes — not only the address that identifies it. A run that
    named just the identity field sent the operator back for one key at a
    time, each round costing a full run to discover the next.

    Only fields the operator has to supply are asked for. A release, a
    standard and a version travel from the TCK onto the binding, and a header
    name has a working default, so none of them belong in a list of what is
    still missing.
    """

    def __init__(self, missing: list[tuple[str, str, list[str]]]) -> None:
        self.missing = missing
        blocks = []
        for side, capability, keys in missing:
            owed = "\n".join(f"      {key}{_env_hint(key)}" for key in keys)
            blocks.append(f"  {side}.{capability} — set:\n{owed}")
        capabilities = ", ".join(f"{side}.{capability}" for side, capability, _ in missing)
        super().__init__(
            "This TCK requires infrastructure that is not fully bound: "
            f"{capabilities}\n" + "\n".join(blocks)
        )


class MissingInputVariableError(InfrastructureError):
    """Raised before the first step when a TCK input variable was not supplied.

    A TCK declares the values it cannot know — the twin it looks up, the BPN it
    presents — as ``env`` variables with ``source: input`` and no default. Those
    are a contract with the operator exactly as a binding is, and until one is
    supplied there is nothing to run: an unsupplied input used to resolve to an
    empty ``${{ env.… }}`` and fail as a puzzling 404 several steps in.
    """

    def __init__(self, missing: dict[str, str]) -> None:
        self.missing = missing
        lines = "\n".join(
            f"      {name}" + (f" — {description}" if description else "")
            for name, description in missing.items()
        )
        super().__init__(
            f"This TCK needs {len(missing)} input variable(s) that were not supplied:\n"
            f"{lines}\n"
            "  Set them under 'variables:' in the run config, or pass --var name=value."
        )


class StandardConflictError(InfrastructureError):
    """Raised when a binding claims a different standard or release than the TCK certifies.

    A TCK that certifies against Saturn cannot prove anything by running
    against a connector the operator declared as Jupiter — one of the two is
    wrong, and which one is the operator's call, so both are printed.
    """

    def __init__(self, conflicts: list[tuple[str, str, str, str, str]]) -> None:
        self.conflicts = conflicts
        lines = "\n".join(
            f"  {side}.{capability}.{field}: bound as '{bound}', "
            f"but this TCK certifies against '{required}'"
            for side, capability, field, bound, required in conflicts
        )
        super().__init__(
            f"The infrastructure bound does not match what this TCK certifies against:\n{lines}"
        )
