#!/usr/bin/env bash
###############################################################################
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
# SPDX-License-Identifier: Apache-2.0
###############################################################################

## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

# Fetch a URL from inside the cluster and print the HTTP status curl saw.
#
#   probe_from_pod.sh <pod-name> <namespace> <url>
#
# The preflights used to do this with `kubectl run --rm -i`, which hands back
# the container's stdout over an attach. curl is done in milliseconds, so the
# container regularly exited before the attach connected, and kubectl then
# printed nothing — `--quiet` hid the warning — and the preflight failed with
# an empty status against a server that was fine (runs 34647498951 and
# 34647881766, 2026-09-11, one on each probe). Here the pod runs detached,
# the script waits for it to finish, and reads the status out of its log,
# which the kubelet keeps until the pod is deleted. A connection failure
# prints curl's `000`; a pod that never finishes prints nothing. The caller
# compares against 200 either way.
set -euo pipefail

name="$1"
namespace="$2"
url="$3"

kubectl delete pod "${name}" --namespace "${namespace}" --ignore-not-found --wait=true >/dev/null
kubectl run "${name}" --namespace "${namespace}" --restart=Never --quiet \
  --image=curlimages/curl:8.10.1 -- \
  curl --silent --output /dev/null --write-out '%{http_code}' --max-time 10 "${url}" >/dev/null

phase=""
for _ in $(seq 1 90); do
  phase="$(kubectl get pod "${name}" --namespace "${namespace}" \
    -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  case "${phase}" in
    Succeeded|Failed) break ;;
  esac
  sleep 2
done

if [ "${phase}" = "Succeeded" ] || [ "${phase}" = "Failed" ]; then
  kubectl logs "${name}" --namespace "${namespace}" 2>/dev/null || true
else
  kubectl describe pod "${name}" --namespace "${namespace}" >&2 || true
fi
kubectl delete pod "${name}" --namespace "${namespace}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
