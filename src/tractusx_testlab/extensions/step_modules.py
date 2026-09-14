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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Every extension module that registers something with the step machinery.

``labs/`` steps (``@step``) and step parameter extensions (``@extends``) register
when their module is imported. ``tractusx_testlab.steps`` imports this module,
so they register together with the core steps. Add the import of a new module
here — a module not imported here is never registered.

Kept apart from ``tractusx_testlab.extensions`` because these modules import the
step contract, and the step contract's models import that package.
"""

import tractusx_testlab.extensions.labs.dataplane_retry
import tractusx_testlab.extensions.labs.steps  # noqa: F401
