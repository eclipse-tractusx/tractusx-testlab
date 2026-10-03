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

"""The part of ``StepContext`` that keeps a namespace read-only once it is fixed.

The run's infrastructure bindings are published under ``infrastructure.*``
before the first step and say what the run is bound to — the addresses its
steps trust and the credential handles they send. Once sealed, a write there —
a step's ``returns:``, a ``store_in_variable`` — fails with
:class:`~tractusx_testlab.models.primitives.exceptions.SealedVariableError`
rather than re-pointing an address or swapping a handle for text. Split from
the context only for its length; ``StepContext`` is the one class that uses it.
"""

from __future__ import annotations

from tractusx_testlab.models.primitives.exceptions import SealedVariableError


class SealedNamespaces:
    """Read-only name prefixes; the ``_sealed`` slot lives on ``StepContext``."""

    __slots__ = ()

    _sealed: tuple[str, ...]

    def seal(self, prefix: str) -> None:
        """Make every name under *prefix* read-only for the rest of the run."""
        if prefix not in self._sealed:
            self._sealed = (*self._sealed, prefix)

    @property
    def sealed(self) -> tuple[str, ...]:
        """The prefixes sealed here, for a copy of this context to keep."""
        return self._sealed

    def _writable(self, name: str) -> None:
        """Refuse a write to *name* when it falls under a sealed prefix."""
        if self._sealed and isinstance(name, str) and name.startswith(self._sealed):
            raise SealedVariableError(name)
