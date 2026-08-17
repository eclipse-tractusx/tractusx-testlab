<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# How to Create a New Step Executor (Python)

A step executor is the Python code that runs when a block is executed at runtime. Every block type needs a corresponding step executor.

A step declares its interface: what it accepts under `with:` and what it returns. Every step publishes all of its return outputs — each top-level output field becomes a context variable of the same name. This is not optional — defining a `BaseStep` subclass without `params_model` and `output_model` raises a `TypeError` at import time. The declaration is also what generates the [step reference](../specification/reference/steps.md), so a parameter you rename in code cannot go stale in the docs.

This page walks through one example end to end. For the rules behind it — every base class, the shared contract models, what fails and what it says — see [Creating a Step](../developer/creating-a-step.md).

## Step 1 — Decide the location

Step executors live under `src/tractusx_testlab/steps/`:

```
steps/
├── connector/     # EDC connector steps (DSP, dataplane, provision, consume)
├── industry/      # Industry layer steps (DTR, notifications, submodels)
├── server/        # Mock-server steps
├── utility/       # General-purpose helpers
├── base.py        # BaseStep, StepParams, StepPayload, StepValue
├── _contracts.py  # Contract models shared by more than one step
├── assertions.py  # Assertion evaluation engine
└── conditions.py  # Conditional execution ("if" expressions)
```

For our "Check Health" example, we'll put it in a new file since it's a general HTTP step.

## Step 2 — Declare the interface

Three models describe a step, and each answers a different question:

| Model | Base class | Answers |
|---|---|---|
| `params_model` | `StepParams` | What keys does the script write under `with:`? |
| `output_model` | `StepPayload` or `StepValue` | What does `returns:` and `validate:` read — and therefore which context variables do later steps get? |

Both are required. There is no separate export channel: every top-level output field is published as a context variable after the step runs, so later steps read your output under exactly the field names you declare.

Pick the output base class by shape:

- **`StepPayload`** — the output is an object with named fields. Every field is public surface: renaming one breaks the scripts that read it.
- **`StepValue[T]`** — the output *is* a bare value (a string, a list, whatever a JSON path pointed at). It has no fields, so its docstring is the description.
- **`NoOutput`** — the step acts and returns nothing. Declaring it is the point: "produces nothing" and "not declared" must not look the same.

## Step 3 — Create the step file

Create `src/tractusx_testlab/steps/utility/health.py`:

```python
################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
"""Step executor for health check HTTP requests."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

import httpx
from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import StepParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


class CheckHealthParams(StepParams):
    """Input contract of ``check_health``."""

    url: str = Field(description="Health endpoint URL.")
    timeout_s: float = Field(
        default=10, gt=0, description="Request timeout in seconds."
    )


class CheckHealthOutput(StepPayload):
    """Output contract of ``check_health``."""

    status_code: int = Field(description="Status code the endpoint answered with.")
    response_body: Any = Field(
        default=None, description="Response body, parsed as JSON when it is JSON."
    )


@step("check_health")
class CheckHealthStep(BaseStep[CheckHealthParams, CheckHealthOutput]):
    """Send a GET request to a health endpoint and report status and body."""

    params_model = CheckHealthParams
    output_model = CheckHealthOutput

    async def execute(
        self,
        params: CheckHealthParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[CheckHealthOutput]:
        async with httpx.AsyncClient(timeout=params.timeout_s) as client:
            resp = await client.get(params.url)

        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        logger.info("Health check %s → %d", params.url, resp.status_code)

        status = body.get("status") if isinstance(body, dict) else None
        return StepOutput(
            value=CheckHealthOutput(status_code=resp.status_code, response_body=body),
            request=HttpRequest(method="GET", url=params.url),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )
```

**Key rules:**

1. **Class extends `BaseStep[ParamsModel, OutputModel]`** — implement the `async execute()` method
2. **Set `params_model` and `output_model`** — both are mandatory; the class will not import without them
3. **Decorate with `@step("type_name")`** — the string must match the block JSON's `type` field exactly
4. **`execute` receives a validated model**, not a dict — read `params.url`, never `params["url"]`
5. **Return the declared model** — `StepOutput(value=CheckHealthOutput(...))`. Raw data is refused even when it would validate, because the point is that the step commits to a shape
6. **Publish variables through the output**, not `context.set_variable` — every top-level output field becomes a context variable automatically, and a `None` value leaves the variable unset rather than written as null
7. **Use `logging`** — never `print()`
8. **Access services via `context`** — e.g., `context.get_consumer_service(name)` for EDC connectors

### Returning a bare value

When the output is not an object, declare its type instead of inventing a wrapper:

```python
from tractusx_testlab.steps.base import StepValue


class HealthTextOutput(StepValue[str]):
    """The raw health text the endpoint returned."""


@step("check_health_text")
class CheckHealthTextStep(BaseStep[CheckHealthParams, HealthTextOutput]):
    """Fetch a health endpoint and return its body as text."""

    params_model = CheckHealthParams
    output_model = HealthTextOutput

    async def execute(self, params, context, definition) -> StepOutput[HealthTextOutput]:
        async with httpx.AsyncClient(timeout=params.timeout_s) as client:
            resp = await client.get(params.url)
        return StepOutput(value=HealthTextOutput(resp.text))
```

### Returning a document the counterpart defined

A catalog, an AAS descriptor, or an EDR data address is shaped by its own specification, not by testlab. Declare the well-known keys, allow the rest through, and bind the document with `.of()`:

```python
from pydantic import ConfigDict


class HealthReportPayload(StepPayload):
    """A health report as the service returned it."""

    model_config = ConfigDict(extra="allow")

    status: Optional[str] = Field(default=None, description="Reported status.")


# ... inside execute():
return StepOutput(value=HealthReportPayload.of(document))
```

`of()` returns `None` for an absent document, so "the service answered with nothing" stays distinct from "the service answered with `{}`". Only the keys actually present are serialised, so a step never invents `"status": null` on a document that omitted it.

### Reusing a contract another step already declares

When two steps talk about the same thing, they share one model rather than each re-declaring it — that is what makes the wiring between steps visible in the types. The shared models live in `steps/_contracts.py`:

| Model | Use it for |
|---|---|
| `CounterPartyParams` | `counter_party_address` / `counter_party_id`, with their legacy spellings |
| `FilterExpressionParams` | catalog filter criteria, plus `sdk_filter_expression()` |
| `ServiceParams` | selecting which configured connector service to talk to |
| `HttpTransportParams` / `HttpCallParams` | headers and timeout, plus method and body |
| `CatalogPayload`, `DataAddressPayload` | DSP documents |
| `NoOutput` | a step that produces nothing |

Inherit the mixins into your own params model:

```python
class MyStepParams(CounterPartyParams, FilterExpressionParams):
    """Input contract of ``my/step``."""
```

## Step 4 — Register the module for auto-import

The step registry uses the `@step` decorator, but the module must be imported for the decorator to run. Add your module to its subpackage's `__init__.py` — here `src/tractusx_testlab/steps/utility/__init__.py`:

```python
import tractusx_testlab.steps.utility.health  # noqa: F401
```

The subpackages themselves are already imported by `src/tractusx_testlab/steps/__init__.py`, so nothing else needs touching.

## Step 5 — Dataspace-version-specific steps

If your step behaves differently on Jupiter vs Saturn, register with a version constraint:

```python
@step("check_health", dataspace_version="saturn")
class CheckHealthSaturnStep(BaseStep[CheckHealthParams, CheckHealthOutput]):
    """Saturn-specific implementation."""

    params_model = CheckHealthParams
    output_model = CheckHealthOutput
    ...
```

Version-specific registrations take priority over global ones at runtime.

## Step 6 — Write a test

Tests call `invoke()`, not `execute()`. `invoke()` is the entry point the runner uses: it validates the raw `with:` mapping into `params_model`, runs `execute`, serialises the output back to plain data, and publishes the output fields — so a test that calls it exercises the same path a script does.

Create `tests/test_check_health.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tractusx_testlab.steps.utility.health import CheckHealthStep


@pytest.mark.asyncio
async def test_check_health_returns_status_and_body():
    """CheckHealthStep returns status_code and response_body from GET."""
    context = MagicMock()
    definition = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "UP"}
    mock_response.headers = {"content-type": "application/json"}

    with patch("tractusx_testlab.steps.utility.health.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value.get = AsyncMock(return_value=mock_response)

        result = await CheckHealthStep().invoke(
            {"url": "https://example.com/health", "timeout_s": 5}, context, definition
        )

    assert result.value == {"status_code": 200, "response_body": {"status": "UP"}}
    assert result.request.method == "GET"


@pytest.mark.asyncio
async def test_check_health_rejects_a_missing_url():
    """A required parameter that is absent fails with the step's contract error."""
    with pytest.raises(ValueError, match="url: Field required"):
        await CheckHealthStep().invoke({}, MagicMock(), MagicMock())
```

Note the shape of the assertion on `result.value`: because the step declared its output, `invoke()` hands back plain JSON data carrying exactly the fields the step set — the same thing a script's `returns:` and `validate:` blocks navigate.

## Step 7 — Run the test and regenerate the reference

```bash
cd /path/to/tractusx-testlab
pytest tests/test_check_health.py -v
testlab docs           # regenerate docs/specification/reference/steps.md
testlab docs --check   # CI runs this; it fails if the page is out of date
```

Your new step appears on the reference page automatically, with its parameters, defaults, accepted aliases, output fields, and published variables — all read from the models you declared.
