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

"""Experimental extensions — syntax and steps that are not part of ``v1-alpha`` yet.

**Everything in this package is experimental.** An extension may change shape or
be removed without a syntax version bump, and it is only in effect for a TCK
that asks for it by name::

    # index.yaml
    extensions: [cac]

A key or a step an extension contributes is refused by the compiler in any TCK
that did not enable that extension, and every TCK that does enable one is told
it is experimental. That is the whole contract: nothing here can reach a
certification run by accident.

Three kinds of contribution exist:

* **Syntax keys** on steps and on ``validate:`` entries — ``cac`` is one.
* **Steps** under a reserved prefix — ``labs/`` holds steps still being tested.
* **Step parameters** — extra ``with:`` keys on an existing step, declared and
  implemented in the extension's package (:mod:`tractusx_testlab.steps.step_extension`).

An extension graduates by moving out of this package into the core syntax or
the core step catalogue under its final name. No alias is left behind.
See ``docs/developer/extensions.md`` for how to add one.
"""

from __future__ import annotations

from tractusx_testlab.extensions.cac import EXTENSION as CAC
from tractusx_testlab.extensions.extension import Extension, ExtensionFinding
from tractusx_testlab.extensions.labs import EXTENSION as LABS

#: Every extension a manifest may name, by the name it names it with. Listed
#: explicitly rather than discovered: an extension nobody registered here is not
#: one, and a reader looking for what ``extensions:`` accepts reads this line.
EXTENSIONS: dict[str, Extension] = {extension.name: extension for extension in (CAC, LABS)}

__all__ = ["EXTENSIONS", "Extension", "ExtensionFinding"]
