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

"""Ctrl-C at a prompt of ``testlab run`` stops the process at once (ADR-0028).

``testlab run`` in a real process, its stdin and stdout a pseudo-terminal, and
a SIGINT sent when it asks: at ``Continue? [y/N]``, and at ``Choose [1-2]``
with a minute left. Neither waits for Enter, nor for the step's timeout.
"""

from __future__ import annotations

import contextlib
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from tests.combinations.mock_server_double import free_port

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs a pseudo-terminal")

_SELECT = {"id": "pick", "uses": "flow/select", "with": {"options": ["a", "b"], "timeout_s": 60}}


def _manifest(root: Path) -> Path:
    (root / "tests").mkdir(parents=True)
    manifest = {
        "kind": "tck",
        "syntax": "v1-alpha",
        "id": "interrupt-tck",
        "metadata": {
            "name": "Interrupt",
            "version": "v1.0.0",
            "description": "d",
            "authors": [{"name": "T", "email": "t@example.org", "company": "E"}],
            "copyright_holders": ["2026 Contributors to the Eclipse Foundation"],
            "license": "Apache-2.0",
            "standards": [{"id": "TESTLAB-INTERNAL", "version": "v1.0.0"}],
        },
        "tests": [{"id": "one.yaml", "name": "one"}],
    }
    test = {
        "kind": "test",
        "syntax": "v1-alpha",
        "namespace": "interrupt-tck",
        "id": "one",
        "metadata": {"name": "one", "version": "v1.0.0", "description": "d"},
        "execution": [_SELECT],
    }
    (root / "index.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (root / "tests" / "one.yaml").write_text(yaml.safe_dump(test), encoding="utf-8")
    return root / "index.yaml"


class _Terminal:
    """``testlab run`` on a pseudo-terminal: what it printed, and a way to type."""

    def __init__(self, tmp_path: Path) -> None:
        manifest = _manifest(tmp_path / "src")
        self.master, slave = os.openpty()
        environment = {**os.environ, "TESTLAB_SERVER_PORT": str(free_port()), "NO_COLOR": "1"}
        environment.pop("TESTLAB_YES", None)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from tractusx_testlab.cli import app; app()",
                "run",
                str(manifest),
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=tmp_path,
            env=environment,
        )
        os.close(slave)
        self.output = ""

    def wait_for(self, text: str, within: float = 90) -> None:
        deadline = time.monotonic() + within
        while text not in self.output:
            if time.monotonic() > deadline or self.process.poll() is not None:
                raise AssertionError(f"never saw {text!r}:\n{self.output}")
            self._read(0.2)

    def type(self, text: str) -> None:
        os.write(self.master, text.encode())

    def interrupt_and_wait(self, within: float) -> float:
        """Send SIGINT; how long the process took to end (fails after *within* seconds)."""
        started = time.monotonic()
        self.process.send_signal(signal.SIGINT)
        while self.process.poll() is None:
            if time.monotonic() - started > within:
                self.process.kill()
                raise AssertionError(f"still running {within}s after Ctrl-C:\n{self.output}")
            self._read(0.1)
        self._read(0.2)
        return time.monotonic() - started

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(5)
        os.close(self.master)

    def _read(self, wait: float) -> None:
        ready, _, _ = select.select([self.master], [], [], wait)
        if ready:
            with contextlib.suppress(OSError):  # the process closed its end
                self.output += os.read(self.master, 65536).decode(errors="replace")


@pytest.fixture
def terminal(tmp_path: Path):
    running = _Terminal(tmp_path)
    yield running
    running.close()


def test_ctrl_c_at_the_approval_ends_the_process_at_once(terminal: _Terminal) -> None:
    terminal.wait_for("Continue? [y/N]")
    assert terminal.interrupt_and_wait(within=10) < 10
    assert terminal.process.returncode != 0
    assert "TCK RUN SUMMARY" not in terminal.output


def test_ctrl_c_at_a_choice_ends_the_run_without_waiting_for_its_timeout(
    terminal: _Terminal,
) -> None:
    terminal.wait_for("Continue? [y/N]")
    terminal.type("y\n")
    terminal.wait_for("Choose [1-2]")
    assert terminal.interrupt_and_wait(within=15) < 15
    assert terminal.process.returncode != 0
    assert "No choice in time" not in terminal.output
