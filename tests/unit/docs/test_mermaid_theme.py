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

"""The docs build keeps hand-coloured Mermaid diagrams readable in the dark scheme."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[3] / "tools" / "mkdocs_mermaid_theme.py"
_spec = importlib.util.spec_from_file_location("mkdocs_mermaid_theme", _HOOK)
assert _spec and _spec.loader
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _page(body: str) -> str:
    return f"Text\n\n```mermaid\nflowchart TD\n{body}\n```\n"


def test_light_fill_becomes_a_tint_of_its_stroke() -> None:
    out = hook.on_page_markdown(_page("    style A fill:#e1f5fe,stroke:#0288d1"))
    assert "    style A fill:#0288d133,stroke:#0288d1\n" in out


def test_light_fill_without_a_coloured_stroke_tints_itself() -> None:
    out = hook.on_page_markdown(_page("    classDef ok fill:#e8f5e9,stroke:#333"))
    assert "classDef ok fill:#e8f5e933,stroke:#333" in out


def test_dark_fill_gets_white_text() -> None:
    out = hook.on_page_markdown(_page("    style B fill:#1565c0,stroke:#333"))
    assert "style B fill:#1565c0,stroke:#333,color:#fff" in out


def test_declared_text_colour_is_kept() -> None:
    line = "    classDef step fill:#f8961e,stroke:#333,color:#000"
    assert line in hook.on_page_markdown(_page(line))


def test_light_sequence_band_becomes_translucent() -> None:
    out = hook.on_page_markdown(_page("    rect rgb(255, 243, 224)"))
    assert "rect rgba(255, 243, 224, 0.2)" in out


def test_style_lines_outside_mermaid_fences_are_untouched() -> None:
    page = "```yaml\nstyle A fill:#e1f5fe,stroke:#0288d1\n```\n"
    assert hook.on_page_markdown(page) == page
