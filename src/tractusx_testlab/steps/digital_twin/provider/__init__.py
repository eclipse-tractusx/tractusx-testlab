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


"""Provider-side Digital Twin Registry steps — ``digital-twin/provider/*``.

Registering twins at a registry the engine operates, through the SDK's AAS
service. Split by what is being registered: a shell descriptor has its own
lifecycle, and submodel descriptors hang off one.

The consumer-side steps live in
:mod:`tractusx_testlab.steps.digital_twin_registry.consumer`: they read a
registry over a data plane and share none of this package's SDK surface.
"""

from tractusx_testlab.steps.digital_twin.provider import (
    shell,
    submodel_descriptor,
)
