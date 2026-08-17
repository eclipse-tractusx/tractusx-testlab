###############################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Repository paths for tests.

Test modules live at varying depths under ``tests/``, so counting ``.parent``
hops from ``__file__`` is fragile — moving a file between subpackages silently
repoints it. Import these constants instead; they are anchored once, here.
"""

from __future__ import annotations

from pathlib import Path

#: Repository root — the directory holding ``src/``, ``docs/`` and ``tests/``.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Importable source tree (``src`` layout).
SRC_DIR = REPO_ROOT / "src"

#: MkDocs documentation tree.
DOCS_DIR = REPO_ROOT / "docs"

#: Published example TCKs, exercised by ``tests/examples/``.
EXAMPLES_DIR = DOCS_DIR / "examples"

#: Uncompiled source of the certificate-management-v2 example TCK.
CCM_RAW_DIR = EXAMPLES_DIR / "certificate-management-v2" / "raw"

#: Test suite root.
TESTS_DIR = REPO_ROOT / "tests"

#: Static YAML/JSON inputs shared across the suite.
FIXTURES_DIR = TESTS_DIR / "fixtures"

__all__ = [
    "CCM_RAW_DIR",
    "DOCS_DIR",
    "EXAMPLES_DIR",
    "FIXTURES_DIR",
    "REPO_ROOT",
    "SRC_DIR",
    "TESTS_DIR",
]
