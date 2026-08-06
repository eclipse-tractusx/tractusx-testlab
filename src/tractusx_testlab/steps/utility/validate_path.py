#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################

"""validate_path step — extract-then-assert variant of util/json_path_extract.

Same traversal engine as ``util/json_path_extract``, exposed under a name that
signals its typical use: pulling a single field out of a prior step's output so
a ``validate:`` block can assert on it.
"""

from __future__ import annotations

from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.utility.json_extract import JsonPathExtractStep


@step("util/validate_path")
class ValidatePathStep(JsonPathExtractStep):
    """Extract a value from a step output by dot-path, for a ``validate:`` block to assert on.

    Identical to ``util/json_path_extract`` — same inputs, same output — under
    a name that says what it is usually there for.
    """
