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

"""The one reference grammar.

Kept as a module so the compiler and the runtime cannot compile ``${{ }}``
differently — they did, and an expression containing ``}`` validated at
compile time and matched nothing at run time.
"""

from __future__ import annotations

import re

EXPR_REF = re.compile(r"\$\{\{\s*((?:[^}]|\}(?!\}))+?)\s*\}\}")
"""Matches ``${{ expr }}``, capturing the expression without its padding.

Two things this has to get right, and the two halves used to live in
different modules getting one each. ``}`` may appear *inside* an expression
— ``${{ env.obj['a}b'] }}`` — so the terminator is two braces, not one; and
the capture excludes the surrounding spaces, so ``${{ env.x }}`` and
``${{env.x}}`` name the same variable rather than one of them naming
``" env.x "``.
"""

EXPR_REF_FULL = re.compile(r"^\$\{\{\s*((?:[^}]|\}(?!\}))+?)\s*\}\}$")
"""Matches a string that is nothing but a single ``${{ expr }}``."""
