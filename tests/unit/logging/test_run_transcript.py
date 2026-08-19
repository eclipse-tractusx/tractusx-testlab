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

"""The transcript holds what the console showed — all of it.

Each of these is something a per-logger file handler used to lose: the CLI's own
narration, which never touches ``logging``; the tracebacks, which go to the root
logger rather than the engine's; and anything a library prints on its way past.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from tractusx_testlab.logging import transcript


class TestPath:
    def test_it_sits_beside_the_trace_of_the_same_run(self) -> None:
        """Same date dir, same ``<time>_<id>`` stem — the two are found together."""
        path = transcript.transcript_path(Path("/logs"), "abc123")
        assert path.parent.parent == Path("/logs")
        assert path.name.endswith("_abc123.log")

    def test_each_run_gets_its_own_id(self) -> None:
        assert transcript.new_run_id() != transcript.new_run_id()


class TestRecording:
    def test_plain_prints_are_kept(self, tmp_path) -> None:
        """``typer.echo`` and ``print`` never reach a logger — this is why."""
        path = tmp_path / "run.log"
        with transcript.recording(path):
            print("Compiled -> package.tck")
        assert "Compiled -> package.tck" in path.read_text()

    def test_a_traceback_is_kept(self, tmp_path, monkeypatch) -> None:
        """The one thing the file is opened for, and it never touched the engine's logger.

        ``logger.exception`` in a step goes to the *root* logger, which is why a
        handler on ``testlab.player`` never saw it. Root handlers are cleared
        here to reproduce a real CLI process — pytest attaches its own capture
        handler, which is not what an operator runs.
        """
        monkeypatch.setattr(logging.root, "handlers", [])
        path = tmp_path / "run.log"
        with transcript.recording(path):
            try:
                raise ValueError("the SUT said 403")
            except ValueError:
                logging.getLogger("some.module").exception("Engine fault")

        written = path.read_text()
        assert "Engine fault" in written
        assert "Traceback (most recent call last)" in written
        assert "ValueError: the SUT said 403" in written

    def test_anything_a_library_prints_on_its_way_past_is_kept(self, tmp_path) -> None:
        path = tmp_path / "run.log"
        with transcript.recording(path):
            sys.stderr.write("some dependency complaining\n")
        assert "some dependency complaining" in path.read_text()

    def test_colour_is_stripped_but_the_words_are_not(self, tmp_path) -> None:
        path = tmp_path / "run.log"
        with transcript.recording(path):
            print("\x1b[31mRESULT: FAIL\x1b[0m")
        assert path.read_text() == "RESULT: FAIL\n"

    def test_a_redrawn_progress_line_lands_once(self, tmp_path) -> None:
        """A bar that overwrites itself is one line to a reader, not a hundred."""
        path = tmp_path / "run.log"
        with transcript.recording(path):
            sys.stdout.write("running 10%\rrunning 60%\rrunning 100%\n")
        assert path.read_text() == "running 100%\n"

    def test_the_console_still_gets_everything(self, tmp_path, capsys) -> None:
        with transcript.recording(tmp_path / "run.log"):
            print("on screen")
        assert "on screen" in capsys.readouterr().out

    def test_streams_are_restored_afterwards(self, tmp_path) -> None:
        before_out, before_err = sys.stdout, sys.stderr
        with transcript.recording(tmp_path / "run.log"):
            assert sys.stdout is not before_out
        assert sys.stdout is before_out
        assert sys.stderr is before_err

    def test_a_run_inside_a_run_keeps_one_file(self, tmp_path) -> None:
        """The player must not open a second transcript inside a CLI run."""
        outer, inner = tmp_path / "outer.log", tmp_path / "inner.log"
        with transcript.recording(outer):
            with transcript.recording(inner) as active:
                print("from the inner run")
                assert active == outer
        assert not inner.exists()
        assert "from the inner run" in outer.read_text()

    def test_no_path_means_no_transcript(self, tmp_path) -> None:
        before = sys.stdout
        with transcript.recording(None) as active:
            assert active is None
            assert sys.stdout is before

    def test_nothing_is_being_recorded_by_default(self) -> None:
        assert transcript.active() is None
