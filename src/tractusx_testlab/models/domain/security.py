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

"""Security models — encryption key blocks, package manifests, and Base64 type helpers."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer


def _b64_decode(v: Any) -> bytes:
    """Accept base64-encoded str or raw bytes."""
    if isinstance(v, str):
        return base64.b64decode(v)
    return v


def _b64_encode(v: bytes) -> str:
    """Serialize bytes as base64 string for JSON."""
    return base64.b64encode(v).decode()


Base64Bytes = Annotated[
    bytes,
    BeforeValidator(_b64_decode),
    PlainSerializer(_b64_encode, return_type=str),
]


class EncryptedKeyBlock(BaseModel):
    player_id: str
    encrypted_key: Base64Bytes


class SecurityBlock(BaseModel):
    format: str = "tck"
    algorithm: str = "AES-256-GCM"
    key_derivation: str = "RSA-OAEP-SHA256"
    compiler_id: str = ""
    authorized_players: list[EncryptedKeyBlock] = Field(default_factory=list)


class PackageManifest(BaseModel):
    name: str
    version: str
    sdk_version: str = ""
    compiled_at: datetime | None = None
    dataspace_versions: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    checksum: str = ""
    security: SecurityBlock | None = None
