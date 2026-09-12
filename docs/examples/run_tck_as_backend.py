################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Backend integration example: load a .tck, discover required variables, and run it.

This script simulates what a backend service would do when asked to execute a TCK:

  1. Load the .tck package (once, on startup or per request).
  2. Inspect which variables are required vs optional.
  3. Receive variables from an external caller (simulated here as a dict).
  4. Validate that all required variables are present.
  5. Execute the TCK with those variables.
  6. Print a structured result summary.

Usage:
    # Dry-run: load + inspect variables only (no stub needed)
    python docs/examples/run_tck_as_backend.py --dry-run

    # Full run (requires the CCM stub running on port 8090):
    #   cd stubs/ccm-sut && python app.py
    python docs/examples/run_tck_as_backend.py

To point at a different .tck or override variables, edit the constants below.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Register all step executors before loading the player.
import tractusx_testlab.steps  # noqa: F401

from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.models.runtime.results import TckResult

# ---------------------------------------------------------------------------
# Configuration — edit these to match your environment
# ---------------------------------------------------------------------------

TCK_PATH = Path("/tmp/test-out/certificate-management-tck.tck")

# Simulated incoming request variables (what a backend would receive from the caller).
# Keys match the variable ids declared in the TCK env block.
REQUEST_VARS: dict[str, str] = {
    "provider_url": "http://localhost:8090/api/v1/dsp",
    "provider_bpn": "BPNL000000000001",
    "consumer_bpn": "BPNL000000000002",
    "location_bpns": "BPNS000000000001",
    "testlab_management_url": "http://localhost:8090/api/v1/dsp",
    "testlab_dsp_url": "http://localhost:8090/api/v1/dsp",
    "testlab_mock_base_url": "http://localhost:8100",
    # Optional overrides (have defaults in the TCK — safe to omit):
    # "certificate_type": "iso9001",
    # "sut_response_timeout": "60",
}


# ---------------------------------------------------------------------------
# Step 1 — Load (done once; in a real backend this is cached at startup)
# ---------------------------------------------------------------------------

def load_tck(path: Path) -> object:
    """Load a compiled .tck archive and return the runtime Tck object."""
    print(f"[loader] Loading TCK from: {path}")
    tck = Loader().load(path)
    print(f"[loader] Loaded '{tck.name}' — {tck.test_count()} tests, {tck.total_steps()} steps")
    return tck


# ---------------------------------------------------------------------------
# Step 2 — Discover variables (what the backend exposes to the caller)
# ---------------------------------------------------------------------------

def describe_variables(tck) -> None:
    """Print all variables the TCK declares, split by required vs optional."""
    required = tck.required_variables()
    all_vars = tck.all_variables()
    optional = {n: v for n, v in all_vars.items() if n not in required}

    print("\n[variables] Required (must be provided by caller):")
    for name, var in required.items():
        print(f"  - {name}  (type: {var.type})"
              + (f"  # {var.description}" if var.description else ""))

    print("\n[variables] Optional (have defaults):")
    for name, var in optional.items():
        print(f"  - {name}  (type: {var.type}, default: {var.default!r})"
              + (f"  # {var.description}" if var.description else ""))


# ---------------------------------------------------------------------------
# Step 3 — Validate incoming request variables
# ---------------------------------------------------------------------------

def validate_request(tck, request_vars: dict[str, str]) -> None:
    """Raise ValueError listing every missing required variable."""
    required = tck.required_variables()
    missing = [name for name in required if name not in request_vars]
    if missing:
        raise ValueError(
            f"Missing required variables: {missing}. "
            f"Provide all of: {list(required.keys())}"
        )
    print(f"\n[validate] All {len(required)} required variables present — OK")


# ---------------------------------------------------------------------------
# Step 4 — Execute
# ---------------------------------------------------------------------------

async def execute(tck, runtime_vars: dict[str, str]) -> TckResult:
    """Run the TCK with the provided variables and return the full result."""
    player = TestlabPlayer()
    print(f"\n[player] Starting execution of '{tck.name}'...")
    return await player.run_tck(tck, runtime_vars=runtime_vars)


# ---------------------------------------------------------------------------
# Step 5 — Print result summary
# ---------------------------------------------------------------------------

def print_result(result: TckResult) -> None:
    """Print a human-readable summary of the TCK execution result."""
    duration = f"{result.duration_ms:.0f}ms" if result.duration_ms else "n/a"
    print(f"\n[result] Status  : {result.status}")
    print(f"[result] Duration: {duration}")
    print(f"[result] Tests : {len(result.tests)}")

    for test in result.tests:
        passed = sum(1 for s in test.execution if s.status.value == "PASSED")
        total = len(test.execution)
        print(f"  [{test.status}] {test.test_name}  ({passed}/{total} steps passed)")
        for step in test.execution:
            icon = "✓" if step.status.value == "PASSED" else "✗"
            print(f"    {icon} {step.step_id}  [{step.status}]")
            if step.error:
                print(f"      error: {step.error}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dry_run = "--dry-run" in sys.argv

    tck = load_tck(TCK_PATH)

    describe_variables(tck)

    try:
        validate_request(tck, REQUEST_VARS)
    except ValueError as exc:
        print(f"\n[error] Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("\n[dry-run] Skipping execution — pass no --dry-run flag to run against a live stub.")
        sys.exit(0)

    result = asyncio.run(execute(tck, REQUEST_VARS))

    print_result(result)

    sys.exit(0 if result.status.value in ("COMPLETED",) else 1)


if __name__ == "__main__":
    main()
