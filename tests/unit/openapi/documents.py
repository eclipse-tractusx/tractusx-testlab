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

"""API documents the openapi and labs API step tests share, bound as a test names them."""

from __future__ import annotations

import copy
from typing import Any

import yaml

from tests.paths import FIXTURES_DIR
from tractusx_testlab.openapi import BoundApiDocument, freeze, load_api_document

SHOP = FIXTURES_DIR / "openapi" / "shop-3.0.yaml"
ICH = FIXTURES_DIR / "openapi" / "industry-core-hub.yaml"
YAML = "application/vnd.oai.openapi"


def shop() -> BoundApiDocument:
    """The OpenAPI 3.0 shop document, as ``${{ env.apis.shop }}`` resolves it."""
    loaded = load_api_document(SHOP, YAML)
    return BoundApiDocument(loaded.content, "shop", loaded.sha256)


def ich() -> BoundApiDocument:
    """The Industry Core Hub document (OpenAPI 3.1, 54 operations), as ``ich``."""
    loaded = load_api_document(ICH, YAML)
    return BoundApiDocument(loaded.content, "ich", loaded.sha256)


def shop_raw() -> dict[str, Any]:
    return copy.deepcopy(yaml.safe_load(SHOP.read_text(encoding="utf-8")))


def bound(document: dict[str, Any], api_id: str = "inline") -> BoundApiDocument:
    """*document* bound under *api_id*, with a digest of its own identity."""
    return BoundApiDocument(freeze(document), api_id, f"test-{api_id}-{id(document)}")
