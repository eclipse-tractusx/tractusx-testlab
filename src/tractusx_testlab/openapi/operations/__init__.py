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

"""The operations of an API document: found by name, and turned into requests."""

from tractusx_testlab.openapi.operations.operation_index import (
    SAFE_METHODS,
    Operation,
    OperationIndex,
    Parameter,
    document_key,
    forget_operation_indexes,
    operation_index,
)
from tractusx_testlab.openapi.operations.pointers import PointerError, follow, resolve
from tractusx_testlab.openapi.operations.request_building import (
    ApiRequestError,
    PreparedRequest,
    expand_path,
    is_json_media,
    prepare,
)
from tractusx_testlab.openapi.operations.servers import (
    check_base_url,
    default_server_url,
    server_base_path,
)

__all__ = [
    "SAFE_METHODS",
    "ApiRequestError",
    "Operation",
    "OperationIndex",
    "Parameter",
    "PointerError",
    "PreparedRequest",
    "check_base_url",
    "default_server_url",
    "document_key",
    "expand_path",
    "follow",
    "forget_operation_indexes",
    "is_json_media",
    "operation_index",
    "prepare",
    "resolve",
    "server_base_path",
]
