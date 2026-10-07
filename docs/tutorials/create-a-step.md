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
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and tested by a human committer. -->

# Create a Step

A step is what a test names in `uses:` — `connector/consumer/negotiate`, `security/oauth2/client_credentials`, `util/generate_uuid`. This tutorial adds one end to end: pick its id, put the module where that id says it lives, declare its contract, implement it, test it, and publish it in the step reference.

The example is `security/jwt/decode`, a step that decodes a JWT a test already holds — say the `access_token` from `security/oauth2/client_credentials` — so the test can assert on its claims. For the full rules behind each choice, see [Creating a Step](../developer/creating-a-step.md).

## 1. Choose the id

Every step id is `<category>/<module>/<function>`:

| Segment | Names | Examples |
|---|---|---|
| category | the domain under test, or an engine facility | `connector`, `digital-twin-registry`, `notification`, `security`, `util`, `flow`, `mock`, `http` |
| module | the component or access path inside the category | `consumer`, `provider`, `dataplane`, `oauth2` |
| function | the operation | `negotiate`, `create_shell_descriptor`, `client_credentials` |

The module segment is left out only when a category has no sub-division at all (`util/log`, `flow/delay`). Once a category has one module, every id in it carries one.

`security` already has the `oauth2` module. Decoding a token is not an OAuth2 grant, so it gets a module of its own: **`security/jwt/decode`**.

Before settling, check the id is new and the name reads like its neighbours:

```bash
poetry run testlab docs --step security/jwt/decode --json   # exits with an error: unknown step
```

Ids are public contract. Once a TCK uses one, renaming it means migrating every TCK — there are no aliases.

## 2. Put the module where the id points

The directory mirrors the id, so anyone reading `uses:` finds the code without a search:

```text
src/tractusx_testlab/steps/
├── security/                 ← category  "security"
│   ├── __init__.py           ← barrel: imports every module below
│   ├── oauth2.py             ← module    "security/oauth2/*"
│   └── jwt.py                ← module    "security/jwt/*"      (new)
├── digital_twin_registry/    ← category  "digital-twin-registry"  ('-' becomes '_')
│   ├── consumer.py
│   ├── submodel.py
│   └── provider/             ← a module that outgrew one file becomes a package,
│       ├── shell.py          ←   split by what it handles
│       └── submodel_descriptor.py
├── step_contract.py          ← BaseStep, StepParams, StepPayload, StepValue, StepOutput
├── shared_models.py          ← contract models used by more than one step
├── http_client.py            ← the one way a step makes an HTTP call
└── sdk_call.py               ← the one way a step calls the Tractus-X SDK
```

These layout rules are enforced by tests, not left to review:

| Rule | Checked by |
|---|---|
| A step's file is under the package its id's category names | `tests/unit/steps/test_step_registration.py` |
| Every `@step` class is imported, so it is registered | `tests/unit/steps/test_step_registration.py` |
| No source file over 300 lines; files already over it may not grow | `tests/unit/structure/test_module_layout.py` |
| No module named for a layer — `utils`, `helpers`, `base`, `common`, `core`, `manager`, `factory`, `contracts`, `checks`, `rules` | `tests/unit/structure/test_module_layout.py` |
| No new basename shared by two modules (a module named for its step id is the accepted exception) | `tests/unit/structure/test_module_layout.py` |

Where the rules leave you a choice:

- **One module, one responsibility.** A file holds the steps of one id module. When it grows toward 300 lines, turn the module into a package and split it by what the steps handle, the way `digital_twin_registry/provider/` splits shells from submodel descriptors. Don't cut it at an arbitrary line.
- **Helpers stay close to their users.** A helper used inside one category goes in a private module there (`connector/_polling.py`). A helper used across categories goes at the `steps/` level and is named for what it does (`http_client.py`, `dsp_keys.py`), never `utils.py`.
- **Don't copy the older layout.** `connector/` still groups some modules by topic (`catalog_query.py` holds `connector/consumer/query_catalog*`). Lay out new code by id.

## 3. Declare the contract

A step declares what it accepts under `with:` and what it returns. The runner validates inputs against the declaration, `returns:` and `validate:` read the declared output, and the step reference is generated from it. A `BaseStep` subclass without both models fails at import.

| Model | Base | Declares |
|---|---|---|
| `params_model` | `StepParams` | one field per `with:` key: type, default, constraints, description |
| `output_model` | `StepPayload` | an object: one field per output key. Every field is published as a context variable of the same name. |
| | `StepValue[T]` | a bare value (a string, a list). There are no fields, so the docstring describes it. |
| | `NoOutput` (in `shared_models`) | the step acts and returns nothing |

A JWT's claim set is defined by its issuer, not by TestLab. So the output names the registered claims tests usually read and lets every other claim through with `extra="allow"`.

## 4. Implement the step

Create `src/tractusx_testlab/steps/security/jwt.py`, starting with the Apache-2.0 header and the AI notice that every source file carries (copy them from `oauth2.py` next door):

```python
"""security/jwt/* — read the claims a JSON Web Token carries.

A token a test obtained — from ``security/oauth2/client_credentials``, or from an
EDR — says who it was issued to and for what. These steps decode it so a test
can assert on those claims. Decoding is not verifying: no signature is checked,
which is why no step here is named ``verify``.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class DecodeJwtParams(StepParams):
    """Input contract of ``security/jwt/decode``."""

    token: str = Field(
        min_length=1,
        description="The compact JWT to decode, e.g. '${{ execution.get_token.access_token }}'.",
    )


class JwtClaimsPayload(StepPayload):
    """The claims of a JWT, as the issuer wrote them.

    The claim set is defined by the issuer rather than by testlab, so the
    registered claims tests read are named here and every other claim — a BPN,
    a Keycloak ``azp`` — rounds through untouched.
    """

    model_config = ConfigDict(extra="allow")

    iss: str | None = Field(default=None, description="Issuer of the token.")
    sub: str | None = Field(default=None, description="Subject the token was issued to.")
    aud: Any = Field(default=None, description="Audience: one string or a list of them.")
    exp: int | None = Field(default=None, description="Expiry, in seconds since the epoch.")


def decode_claims(token: str) -> dict[str, Any]:
    """Return the claim set of compact JWT *token*, without verifying it.

    Raises ``ValueError`` naming what is wrong with the token, so the step fails
    with a sentence a test author can act on.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"A JWT has three dot-separated parts; this one has {len(parts)}")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("The JWT payload is not base64url-encoded JSON") from error
    if not isinstance(claims, dict):
        raise ValueError("The JWT payload is JSON but not a claim set (an object)")
    return claims


@step("security/jwt/decode")
class DecodeJwtStep(BaseStep[DecodeJwtParams, JwtClaimsPayload]):
    """Decode a JWT and publish its claims, without verifying the signature.

    Every claim becomes an output, so a later step reads ``sub`` or ``exp``
    directly and an assertion checks a claim by name.
    """

    params_model = DecodeJwtParams
    output_model = JwtClaimsPayload

    async def execute(
        self,
        params: DecodeJwtParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[JwtClaimsPayload]:
        return StepOutput(value=JwtClaimsPayload.of(decode_claims(params.token)))
```

What this code relies on:

- **`execute` gets a validated model, not a dict.** A missing `token` fails before `execute` runs, and the error names the field.
- **Return the declared model.** `JwtClaimsPayload.of(document)` binds a document someone else defined. It serialises only the keys that were present, so a token without `aud` doesn't come back with `"aud": null`.
- **Publish through the output, never `context.set_variable`.** Every top-level output field becomes a context variable after the step runs. The `store_in_variable` parameter is the only exception.
- **Keep logic in plain functions.** `decode_claims` can be tested without a step, and the docstrings become the step's entry in the reference.

### When the step talks to a service

A step never names its service or builds a client itself. The run seeds the connector and registry services from its infrastructure bindings, and a step reaches them through `context.dataspace`. The step calls the SDK only through `sdk_call.run`, which runs the blocking call off the event loop and reports a failure as the bound service's error:

```python
from tractusx_testlab.steps import sdk_call

aas = context.dataspace.registry()          # also: .consumer(), .provider(), .notifications()
result = await sdk_call.run(
    aas.create_asset_administration_shell_descriptor,
    ShellDescriptor(**shell_descriptor),
    bpn=bpn,
)
```

A plain HTTP call goes through `steps.http_client.request`, never `requests` or a private `httpx` client. That keeps the event loop free for mock callbacks and records the call in the execution trace. Pass the exchange back as `StepOutput(request=HttpRequest(...), response=HttpResponse(...))` so the run report shows it. `security/oauth2.py` is a complete example.

### Reuse before you declare

If another step already declares the shape you need, inherit its model from `steps/shared_models.py` rather than declaring your own. Examples are `HttpTransportParams` (`headers`, `timeout`), `FilterExpressionParams`, `CatalogOutput`, `DataAddressPayload`, `DeletionOutput` and `NoOutput`. Each parameter has one canonical name. Don't add aliases or legacy spellings.

## 5. Register the module

`@step` registers the class when its module is imported. Add the module to the category's barrel, `src/tractusx_testlab/steps/security/__init__.py`:

```python
import tractusx_testlab.steps.security.jwt
import tractusx_testlab.steps.security.oauth2
```

`steps/__init__.py` already imports every category package. A brand-new category needs one more line there, plus a directory whose name matches the id's first segment.

A step that behaves differently per dataspace generation registers once per version, for example `@step("connector/consumer/discover_connector", dataspace_version="saturn")`. The version-specific registration wins.

## 6. Test it

Unit tests mirror the source tree, so the test for `steps/security/jwt.py` goes in `tests/unit/steps/security/`. Call `invoke()`, not `execute()`. `invoke()` is the runner's path: it validates the raw `with:` mapping, runs the step, serialises the output and publishes it. Assert on the plain data it returns, which is what `returns:` and `validate:` see.

`tests/unit/steps/security/test_security_jwt.py`:

```python
"""Tests for the security/jwt/* steps."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.security.jwt import DecodeJwtStep


def _token(claims: dict) -> str:
    """A compact JWT carrying *claims*, with a header and signature nothing reads."""
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJSUzI1NiJ9.{payload}.c2lnbmF0dXJl"


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinition:
    return StepDefinition(id="claims", uses="security/jwt/decode")


def test_the_step_is_registered() -> None:
    assert StepRegistry.get("security/jwt/decode", "") is DecodeJwtStep


@pytest.mark.asyncio
async def test_publishes_every_claim(context: StepContext) -> None:
    token = _token({"sub": "BPNL000000000001", "exp": 1767225600, "azp": "edc"})

    output = await DecodeJwtStep().invoke({"token": token}, context, _definition())

    assert output.value == {"sub": "BPNL000000000001", "exp": 1767225600, "azp": "edc"}
    assert context.get_variable("sub") == "BPNL000000000001"


@pytest.mark.asyncio
async def test_claims_the_token_omits_are_not_invented(context: StepContext) -> None:
    output = await DecodeJwtStep().invoke({"token": _token({"sub": "a"})}, context, _definition())

    assert output.value == {"sub": "a"}


@pytest.mark.asyncio
async def test_rejects_a_missing_token(context: StepContext) -> None:
    with pytest.raises(ValueError, match="token"):
        await DecodeJwtStep().invoke({}, context, _definition())


@pytest.mark.asyncio
async def test_names_what_is_wrong_with_a_malformed_token(context: StepContext) -> None:
    with pytest.raises(ValueError, match="three dot-separated parts"):
        await DecodeJwtStep().invoke({"token": "not-a-jwt"}, context, _definition())
```

Some tests you don't write, because they already run over every registered step:

- `tests/unit/steps/test_step_contracts.py` checks the declared models and requires a non-empty docstring.
- `tests/unit/steps/test_step_registration.py` checks the decorator, the barrel import and the directory.

## 7. Publish it and use it

Regenerate the step reference. CI fails when the committed pages are stale:

```bash
poetry run testlab docs          # writes docs/api-reference/steps/security/jwt.md and the nav entry
poetry run testlab docs --check
```

Then run the checks CI runs, listed in [Development Workflow](development-workflow.md). If the step should also appear as a block in the cx-test-suite IDE, add the block there. `poetry run python tools/compare_ide_parity.py --ide <path-to-cx-test-suite>` then shows whether the block's `with:` and `returns:` keys match your models.

The step is now usable in a TCK:

```yaml
execution:
  - id: get_token
    uses: security/oauth2/client_credentials
    with:
      token_url: ${{ env.token_url }}
      client_id: ${{ env.client_id }}
      client_secret: ${{ env.client_secret }}
    returns:
      access_token:
        type: string

  - id: claims
    uses: security/jwt/decode
    with:
      token: ${{ execution.get_token.access_token }}
    validate:
      - uses: validate/assert/equals
        with: { input: sub, value: "${{ env.expected_bpn }}" }
```

## Checklist

- [ ] Id follows `<category>/<module>/<function>` and is written in full everywhere
- [ ] Module sits at the path its id names, under 300 lines, named for what it holds
- [ ] Params model declares every `with:` key with a description, constraints and one canonical name
- [ ] Output is a `StepPayload`, `StepValue` or `NoOutput`; counterpart documents are bound with `.of()`
- [ ] Services come from `context.dataspace`, SDK calls go through `sdk_call.run`, HTTP through `http_client`
- [ ] Module imported from its category's `__init__.py`
- [ ] Unit tests under `tests/unit/steps/<category>/` call `invoke()` and assert on plain data
- [ ] `testlab docs` run and the regenerated pages committed
