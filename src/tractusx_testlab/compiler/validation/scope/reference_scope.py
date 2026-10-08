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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-6).
## It was reviewed and tested by a human committer.

"""Compile-time names supplied by the manifest, its steps and the player."""

from tractusx_testlab.compiler.validation._variable_references import nested_step_ids
from tractusx_testlab.infrastructure.mapping import known_keys
from tractusx_testlab.models import TckDefinition, TestDefinition
from tractusx_testlab.syntax import context_vars


def _scope_of(tck: TckDefinition, test: TestDefinition) -> frozenset[str]:
    """Every name a reference in *test* may legally resolve to.

    Assembled from the manifest's ``env`` block, the test's own step ids (those
    nested in a flow step included), the infrastructure binding keys and
    immutable run metadata. This is the namespace the runtime will
    actually have, so a name missing from here is a name that will be missing
    from the run.
    """
    names: set[str] = set()

    env = tck.env
    if env is not None:
        for variable_id in _env_variable_ids(env.variables):
            names.add(f"env.{variable_id}")
        for testdata in env.testdata or []:
            names.add(f"env.testdata.{testdata.id}")
        for schema in env.schemas or []:
            names.add(f"env.schemas.{schema.id}")

    for phase, steps in (
        ("setup", test.setup),
        ("execution", test.execution),
        ("teardown", test.teardown),
    ):
        for step in steps:
            if step.id:
                names.add(f"{phase}.{step.id}")
            for nested_id in nested_step_ids(step.uses, step.with_):
                names.add(f"{phase}.{nested_id}")

    names.update(known_keys())
    names.update(context_vars.RUN_VARIABLES)
    return frozenset(names)


def _env_variable_ids(variables: object) -> list[str]:
    """Ids of the manifest's declared variables, whichever shape they arrive in."""
    if isinstance(variables, list):
        return [str(v["id"]) for v in variables if isinstance(v, dict) and "id" in v]
    if isinstance(variables, dict):
        return [str(key) for key in variables]
    return []
