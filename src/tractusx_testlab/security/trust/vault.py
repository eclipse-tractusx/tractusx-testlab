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

"""Optional HashiCorp Vault backend for key storage."""

from __future__ import annotations

import requests

from tractusx_testlab.models import VaultConfig


class VaultClient:
    """Thin wrapper around the HashiCorp Vault KV v2 API."""

    __slots__ = ("_secret_path", "_session", "_token", "_url")

    def __init__(self, config: VaultConfig) -> None:
        self._url = config.vault_url.rstrip("/")
        self._token = config.vault_token
        self._secret_path = config.vault_secret_path
        self._session = requests.Session()
        self._session.headers["X-Vault-Token"] = self._token

    def _kv_url(self, key: str) -> str:
        return f"{self._url}/v1/{self._secret_path}/data/{key}"

    def read_secret(self, key: str) -> dict | None:
        """Read a secret from Vault. Returns the data dict or None."""
        resp = self._session.get(self._kv_url(key), timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("data")
        return None

    def write_secret(self, key: str, data: dict) -> None:
        """Write (create/update) a secret in Vault."""
        resp = self._session.post(self._kv_url(key), json={"data": data}, timeout=10)
        resp.raise_for_status()

    def delete_secret(self, key: str) -> None:
        """Soft-delete the latest version of a secret."""
        resp = self._session.delete(self._kv_url(key), timeout=10)
        resp.raise_for_status()

    def store_key(self, name: str, private_pem: bytes, public_pem: bytes) -> None:
        """Convenience: store a key pair in Vault."""
        self.write_secret(name, {
            "private_key": private_pem.decode(),
            "public_key": public_pem.decode(),
        })

    def load_key(self, name: str) -> tuple[bytes, bytes] | None:
        """Convenience: load a key pair from Vault. Returns (private, public) or None."""
        data = self.read_secret(name)
        if data and "private_key" in data and "public_key" in data:
            return data["private_key"].encode(), data["public_key"].encode()
        return None
