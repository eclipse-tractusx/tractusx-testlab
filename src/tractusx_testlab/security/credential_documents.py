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

"""Keeping a credential handle a handle when a step's output becomes plain data.

A step declares its output as a model and the run reads it as JSON data: the
model is dumped once, in JSON mode, and every later reader — a check, a
``returns:`` name, the next step's ``${{ }}`` — sees that data. A handle dumps
as ``***``, which is right for every record and wrong for the run itself: the
EDR token a transfer step returned would reach the data-plane step as the
three characters ``***``. So the dump is taken as usual and every handle the
model held is put back where its ``***`` landed — the run keeps the handle,
and only a record turns it into text.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from tractusx_testlab.security.credentials import Credential

__all__ = ["holds_credential", "restore_credentials"]


def holds_credential(value: object) -> bool:
    """Whether *value* — a model, a document, a list — holds a handle at any depth."""
    if isinstance(value, Credential):
        return True
    if isinstance(value, BaseModel):
        return any(holds_credential(getattr(value, name)) for name in type(value).model_fields) or (
            holds_credential(value.model_extra or {})
        )
    if isinstance(value, dict):
        return any(holds_credential(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(holds_credential(item) for item in value)
    return False


def restore_credentials(original: object, dumped: Any) -> Any:
    """*dumped* — *original* dumped by alias — with each handle of *original* put back."""
    if isinstance(original, Credential):
        return original
    if isinstance(original, BaseModel) and isinstance(dumped, dict):
        fields = {
            (field.alias or name): getattr(original, name)
            for name, field in type(original).model_fields.items()
        }
        fields.update(original.model_extra or {})
        return {
            key: restore_credentials(fields[key], item) if key in fields else item
            for key, item in dumped.items()
        }
    if isinstance(original, dict) and isinstance(dumped, dict):
        return {
            key: restore_credentials(original[key], item) if key in original else item
            for key, item in dumped.items()
        }
    if isinstance(original, list | tuple) and isinstance(dumped, list):
        return [restore_credentials(a, b) for a, b in zip(original, dumped, strict=False)]
    return dumped
