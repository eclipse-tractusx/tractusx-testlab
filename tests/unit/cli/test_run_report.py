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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The live progress bar: animated on a terminal, silent in a log.

``FORCE_COLOR`` keeps the result tables coloured in a CI log. ``rich`` reads
the same variable as "stdout is a terminal", and a live display on a
terminal redraws itself between every line of output, hides the cursor and
wraps everything routed through it at 80 columns — which turned the e2e
job's log into a spinner interleaved with broken lines. The bar's console
has to take its terminal-ness from the real terminal, not from the colour
convention.
"""

from __future__ import annotations

import sys

from rich.live import Live

from tractusx_testlab.cli._run_report import progress_console


class TestProgressConsole:
    def test_force_color_does_not_make_a_log_a_terminal(self, monkeypatch, capsys) -> None:
        monkeypatch.setenv("FORCE_COLOR", "1")
        console = progress_console()
        assert not console.is_terminal
        assert not console.is_interactive

    def test_a_live_display_leaves_stdout_alone_off_a_terminal(self, monkeypatch, capsys) -> None:
        monkeypatch.setenv("FORCE_COLOR", "1")
        long_line = "x" * 200
        with Live("bar", console=progress_console()):
            print(long_line)
        out = capsys.readouterr().out
        # Not wrapped at the console's 80 columns, and no cursor control.
        assert long_line in out.splitlines()
        assert "\x1b[?25l" not in out

    def test_a_real_terminal_still_gets_the_live_bar(self, monkeypatch) -> None:
        monkeypatch.setenv("FORCE_COLOR", "1")
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        assert progress_console().is_terminal
