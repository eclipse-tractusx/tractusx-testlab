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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""Restart an EDC runtime that booted but never reports ready.

The Umbrella release converges in under three minutes, every time, except
when one of its EDC-based runtimes (an IdentityHub, the IssuerService) comes
up wedged: the JVM logs ``57 service extensions started`` and ``Runtime <id>
ready``, Jetty has bound every context, Jersey has registered the health
controller — and the kubelet's readiness probe on ``/api/check/readiness``
answers 404 from then on, while the liveness probe on the same port passes.
Nothing restarts it: the container never crashes, and the liveness probe is
the one that is green. ``helm install --wait`` then sits out its whole
25-minute budget and fails.

Seen twice in forty runs, on two different images and versions (run
34432469270, 2026-09-10, ``issuerservice-memory:0.3.2``; run 34685108558,
2026-09-12, ``identityhub-memory:0.4.0-SNAPSHOT``). The same image and
configuration booted cleanly 18 times in a row outside the cluster, and a
fresh boot in the cluster has so far always come up clean too. So the
deploy watcher calls this once a tick: a pod that has been running for
``--grace-seconds`` with its runtime logged ready and its container still
not ready is deleted, and its Deployment brings a new one up in about forty
seconds. Before deleting, the probe's own path is fetched from inside the
cluster and printed with its status and body, which is the evidence the
upstream issue needs and which no log so far has captured (the images
ship Jetty without a logging backend, so whatever it says about the 404 is
lost).

The rule is deliberately narrow. A runtime that has not logged ready is
still booting or has crashed, and the kubelet already handles a crash. A
Job's pod is a Helm hook and is never touched. Each owner (a ReplicaSet or
StatefulSet) is restarted at most ``--max-restarts`` times, so a runtime
that is broken rather than wedged is left for the helm timeout and the
diagnostics to report.

Runs on the runner's own ``python3`` with nothing but ``kubectl`` on the
path; the decision itself is a pure function so it can be tested offline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

#: What every EDC-based runtime prints as the last line of a successful boot.
READY_LINE = re.compile(r"Runtime [0-9a-f-]{36} ready")

#: The one curl image the workflow already uses for its preflight probes.
CURL_IMAGE = "curlimages/curl:8.10.1"


@dataclass(frozen=True)
class Wedge:
    """A pod that should be restarted, and why."""

    pod: str
    owner: str
    container: str
    readiness_url: str | None
    liveness_url: str | None
    reason: str


def assess(pod: dict, log_tail: str, now: datetime, grace: timedelta) -> Wedge | None:
    """Decide whether *pod* is a wedged runtime.

    ``pod`` is one item of ``kubectl get pods -o json``; ``log_tail`` the
    tail of its container log. Returns ``None`` for every pod the watcher
    should leave alone.
    """
    metadata = pod.get("metadata", {})
    status = pod.get("status", {})
    if status.get("phase") != "Running":
        return None
    owners = metadata.get("ownerReferences") or []
    if any(owner.get("kind") == "Job" for owner in owners):
        return None
    statuses = status.get("containerStatuses") or []
    if not statuses or all(container.get("ready") for container in statuses):
        return None
    container = next(c for c in statuses if not c.get("ready"))
    running = (container.get("state") or {}).get("running")
    if not running:
        # Waiting or terminated: crashing, pulling, or being killed. The
        # kubelet owns those.
        return None
    started = _parse_time(running.get("startedAt"))
    if started is None or now - started < grace:
        return None
    if not READY_LINE.search(log_tail):
        return None

    spec_container = next(
        (
            c
            for c in pod.get("spec", {}).get("containers", [])
            if c.get("name") == container["name"]
        ),
        {},
    )
    pod_ip = status.get("podIP")
    owner = owners[0]["name"] if owners else metadata.get("name", "")
    return Wedge(
        pod=metadata.get("name", ""),
        owner=owner,
        container=container["name"],
        readiness_url=_probe_url(spec_container.get("readinessProbe"), pod_ip),
        liveness_url=_probe_url(spec_container.get("livenessProbe"), pod_ip),
        reason=(
            f"runtime logged ready, container not ready for {int((now - started).total_seconds())}s"
        ),
    )


def _probe_url(probe: dict | None, pod_ip: str | None) -> str | None:
    http = (probe or {}).get("httpGet")
    if not http or not pod_ip:
        return None
    scheme = (http.get("scheme") or "HTTP").lower()
    return f"{scheme}://{pod_ip}:{http.get('port')}{http.get('path', '/')}"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --------------------------------------------------------------------------
# kubectl
# --------------------------------------------------------------------------


def _kubectl(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["kubectl", *args], capture_output=True, text=True, check=False, timeout=120
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _pods(namespace: str) -> list[dict]:
    return json.loads(_kubectl("get", "pods", "-n", namespace, "-o", "json")).get("items", [])


def _log_tail(namespace: str, pod: str, container: str) -> str:
    return _kubectl("logs", "-n", namespace, pod, "-c", container, "--tail=300", check=False)


def fetch_evidence(namespace: str, wedge: Wedge) -> str:
    """Fetch the readiness and liveness paths from inside the cluster.

    The same detached-pod pattern as ``probe_from_pod.sh``: ``kubectl run``
    without ``--rm -i``, because curl finishes before an attach can connect,
    and the answer is read from the pod's log once it has exited.
    """
    urls = [u for u in (wedge.readiness_url, wedge.liveness_url) if u]
    if not urls:
        return "(no httpGet probes on the container; nothing to fetch)"
    name = f"tck-wedge-{int(time.time())}"
    script = "; ".join(
        f"echo '### {url}'; curl --silent --include --max-time 5 '{url}' | head -c 2000; echo"
        for url in urls
    )
    _kubectl("delete", "pod", name, "-n", namespace, "--ignore-not-found", check=False)
    _kubectl(
        "run",
        name,
        "-n",
        namespace,
        "--restart=Never",
        "--quiet",
        f"--image={CURL_IMAGE}",
        "--",
        "sh",
        "-c",
        script,
        check=False,
    )
    phase = ""
    for _ in range(45):
        phase = _kubectl(
            "get", "pod", name, "-n", namespace, "-o", "jsonpath={.status.phase}", check=False
        ).strip()
        if phase in ("Succeeded", "Failed"):
            break
        time.sleep(2)
    output = _kubectl("logs", name, "-n", namespace, check=False) if phase else ""
    _kubectl(
        "delete", "pod", name, "-n", namespace, "--ignore-not-found", "--wait=false", check=False
    )
    return output.strip() or f"(probe pod ended in phase {phase or 'unknown'} with no output)"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def _restart_count(state_dir: Path, owner: str) -> int:
    path = state_dir / owner
    return int(path.read_text()) if path.exists() else 0


def _record_restart(state_dir: Path, owner: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / owner).write_text(str(_restart_count(state_dir, owner) + 1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--namespace", required=True)
    parser.add_argument(
        "--state-dir", required=True, type=Path, help="where restarts per owner are counted"
    )
    parser.add_argument("--grace-seconds", type=int, default=120)
    parser.add_argument("--max-restarts", type=int, default=2)
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    grace = timedelta(seconds=args.grace_seconds)
    for pod in _pods(args.namespace):
        name = pod["metadata"]["name"]
        statuses = pod.get("status", {}).get("containerStatuses") or []
        if not statuses or all(c.get("ready") for c in statuses):
            continue
        container = next(c for c in statuses if not c.get("ready"))["name"]
        wedge = assess(pod, _log_tail(args.namespace, name, container), now, grace)
        if wedge is None:
            continue
        restarts = _restart_count(args.state_dir, wedge.owner)
        if restarts >= args.max_restarts:
            print(
                f"wedged: {wedge.pod} ({wedge.reason}); already restarted {restarts}x, leaving it"
            )
            continue
        print(f"wedged: {wedge.pod} ({wedge.reason})")
        print(fetch_evidence(args.namespace, wedge))
        _kubectl("delete", "pod", wedge.pod, "-n", args.namespace, "--wait=false", check=False)
        _record_restart(args.state_dir, wedge.owner)
        print(
            f"::warning title=Wedged runtime restarted::{wedge.pod} logged ready but its "
            f"readiness probe never passed; deleted so {wedge.owner} brings up a fresh one "
            f"(restart {restarts + 1} of {args.max_restarts})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
