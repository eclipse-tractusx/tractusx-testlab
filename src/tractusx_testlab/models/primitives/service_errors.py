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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""What the service registry raises when a step asks for a service it cannot give.

Every error here is an :class:`~tractusx_testlab.models.primitives.exceptions.EngineError`
about the registry that seeds and hands out the services a run stands on: a
name nobody registered, a service that failed to come up or was stopped, two
definitions claiming one name, a step wired to the wrong kind of service. None
is a verdict about the system under test — the step never got to ask its
question — and none is the deployment's fault the way a
:mod:`~tractusx_testlab.models.primitives.binding_errors` is, because the
registry is TestLab's own.

They are grouped here rather than among the outcome hierarchy because they
share one vocabulary — a service *name*, its *state*, its *type* — and a reader
of the hierarchy wants to know which of the four outcomes a run reported, not
how the registry spells its refusals.
"""

from __future__ import annotations

from tractusx_testlab.models.primitives.enums import ServiceState, ServiceType
from tractusx_testlab.models.primitives.exceptions import EngineError


class ServiceNotFoundError(EngineError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Service not found: {name}")


class ServiceNotReadyError(EngineError):
    def __init__(self, name: str, state: ServiceState):
        self.name = name
        self.state = state
        super().__init__(f"Service '{name}' is in state {state.value}, not READY")


class ServiceTypeMismatchError(EngineError):
    def __init__(self, step_type: str, expected: ServiceType, actual: ServiceType):
        self.step_type = step_type
        self.expected = expected
        self.actual = actual
        super().__init__(f"Step '{step_type}' expects {expected.value} but got {actual.value}")


class DuplicateServiceError(EngineError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Duplicate service name: {name}")


class ServiceInitError(EngineError):
    def __init__(self, name: str, cause: Exception):
        self.name = name
        self.cause = cause
        super().__init__(f"Failed to initialize service '{name}': {cause}")
