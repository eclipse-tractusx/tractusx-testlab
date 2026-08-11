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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Field-level contract diff between the IDE block catalog and the step registry.

A ``uses:`` value is only half the contract between the IDE and the engine: the
IDE also writes a ``with:`` mapping and a ``returns:`` block, and both sides
must agree on those key names or the script fails silently.  Comparing step
*names* alone — which is what a registry listing gives you — reports parity for
a step whose every parameter the engine throws away.

This tool compares the two contracts key by key and classifies each divergence
by how it fails at runtime:

``A`` — ``uses:`` does not resolve; the compiler rejects the script.
``B`` — an IDE parameter no engine field accepts.  ``StepParams`` is
        ``extra="allow"``, so the value is *dropped without an error*.
``C`` — an IDE ``returns:`` name nothing in the output resolves; the variable
        is set to ``None`` and the failure surfaces in a later step.
``D`` — required in the IDE, optional in the engine.  Benign: the engine falls
        back to a context variable or a default.
``E`` — an engine parameter the IDE never offers (capability not exposed).
``F`` — a registered step with no IDE block.
``G`` — an IDE parameter that binds only through a ``validation_alias``.  It
        runs today; it is still two spellings of one field.

Aliases are resolved on both sides, so a field the engine accepts under
``validation_alias`` counts as present, and a return name the runtime resolves
through a ``StepOutput`` slot or an ``HttpResponse`` attribute counts as
readable.  Comparing the generated JSON Schema instead would over-report both.

Resolving an alias is not approving it.  The contract this repository holds
itself to is one name and one shape per field (see
``docs/developer/ide-engine-contract-parity.md``), so a key that binds only
because a second spelling exists is reported as ``G`` and counts towards the
non-zero exit alongside ``A``, ``B`` and ``C``.

Usage::

    poetry run python tools/compare_ide_parity.py --ide ~/path/to/cx-test-suite
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Optional

warnings.filterwarnings("ignore")

from pydantic import BaseModel  # noqa: E402
from pydantic.aliases import AliasChoices, AliasPath  # noqa: E402

import tractusx_testlab.steps  # noqa: E402,F401  importing registers every step
from tractusx_testlab.scripting.registry import StepRegistry  # noqa: E402

# -- Known name drift ---------------------------------------------------------
# The IDE spelling on the left is what the exporter writes; the engine name on
# the right is what actually resolves.  An entry here is a class-A finding that
# the tool follows through so the fields underneath it can still be compared.
NAME_MAP = {
    "connector/consumer/negotiate": "connector/consumer/negotiate_contract",
    "connector/consumer/initiate_transfer": "connector/consumer/transfer_data",
    "digital-twin-registry/register_shell": "digital-twin/provider/create_shell_descriptor",
    "digital-twin-registry/add_submodel": "digital-twin/provider/create_submodel_descriptor",
    "digital-twin-registry/lookup_shell": "digital-twin/provider/get_shell_descriptor",
}

# Return names the runtime resolves no matter what the step declares:
# ``StepOutput`` slots, ``HttpResponse`` attributes, and the two aliases
# hard-coded in ``steps/_checks/extraction.py``.
UNIVERSAL_RETURNS = {
    "value", "request", "response", "exports",
    "status_code", "headers", "body", "duration_ms",
    "response_body", "response_headers",
}


# -- Engine side --------------------------------------------------------------


def _accepted_names(field_name: str, field: Any, populate_by_name: bool) -> set[str]:
    """Every ``with:`` key that binds to *field_name*."""
    names: set[str] = set()
    validation_alias = getattr(field, "validation_alias", None)
    if isinstance(validation_alias, AliasChoices):
        for choice in validation_alias.choices:
            if isinstance(choice, str):
                names.add(choice)
            elif isinstance(choice, AliasPath):
                names.add(str(choice.path[0]))
    elif isinstance(validation_alias, str):
        names.add(validation_alias)
    else:
        names.add(field_name)
    if getattr(field, "alias", None):
        names.add(field.alias)
    if populate_by_name:
        names.add(field_name)
    return names


def _type_name(field: Any) -> str:
    annotation = field.annotation
    return getattr(annotation, "__name__", str(annotation)).replace("typing.", "")


def _describe_model(model: Optional[type[BaseModel]]) -> dict:
    if model is None:
        return {"extra": None, "fields": {}}
    populate = bool(model.model_config.get("populate_by_name", False))
    return {
        "extra": model.model_config.get("extra", "ignore"),
        "fields": {
            name: {
                "accepts": sorted(_accepted_names(name, field, populate)),
                "type": _type_name(field),
                "required": field.is_required(),
                "description": (field.description or "").split("\n")[0],
            }
            for name, field in model.model_fields.items()
        },
    }


def read_engine() -> dict:
    """The registry's real input and output surface, aliases resolved."""
    engine: dict[str, dict] = {}
    for step_type in StepRegistry.list_step_types():
        cls = StepRegistry.get(step_type, "v1")
        if cls is None:
            continue
        engine[step_type] = {
            "params": _describe_model(getattr(cls, "params_model", None)),
            "output": _describe_model(getattr(cls, "output_model", None)),
            "exports": _describe_model(getattr(cls, "exports_model", None)),
        }
    return engine


# -- IDE side -----------------------------------------------------------------


def read_ide(blocks_dir: Path) -> list[dict]:
    """Every block definition in the catalog, indexed or not."""
    blocks = []
    for path in sorted(blocks_dir.rglob("*.json")):
        if path.name in ("index.json", "classes.json"):
            continue
        block = json.loads(path.read_text())
        block["_path"] = str(path.relative_to(blocks_dir))
        blocks.append(block)
    return blocks


# -- Comparison ---------------------------------------------------------------


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _input_lookup(params: dict) -> dict[str, str]:
    """Every accepted ``with:`` key mapped to the field it binds to."""
    return {
        accepted: field_name
        for field_name, field in params["fields"].items()
        for accepted in field["accepts"]
    }


def _readable_names(step: dict) -> dict[str, dict]:
    """Names a ``returns:`` block can read — outputs are dumped ``by_alias``."""
    readable: dict[str, dict] = {}
    for kind in ("output", "exports"):
        for name, field in step[kind]["fields"].items():
            # Exports publish under the field name; outputs under the alias.
            wire = name if kind == "exports" else (field["accepts"][0] if field["accepts"] else name)
            readable.setdefault(wire, {"type": field["type"], "where": []})
            readable[wire]["where"].append(kind)
    return readable


def compare(engine: dict, blocks: list[dict]) -> dict:
    rows = []
    matched = set()
    for block in blocks:
        uses = block.get("uses")
        resolved = NAME_MAP.get(uses, uses)
        step = engine.get(resolved)
        if step is None:
            rows.append({"kind": "unresolvable", "uses": uses, "path": block["_path"],
                         "label": block.get("label")})
            continue
        matched.add(resolved)
        lookup = _input_lookup(step["params"])
        readable = _readable_names(step)

        dropped, bound, required_drift = [], [], []
        consumed = set()
        for param in block.get("params") or []:
            name = param["name"]
            if name not in lookup:
                dropped.append({"name": name, "type": param.get("type"),
                                "required": bool(param.get("required")),
                                "description": param.get("description", "")})
                continue
            field_name = lookup[name]
            consumed.add(field_name)
            field = step["params"]["fields"][field_name]
            bound.append({"ide": name, "engine": field_name, "via_alias": name != field_name})
            if bool(param.get("required")) != field["required"]:
                required_drift.append(name)

        engine_only_params = [
            {"name": name, "type": field["type"], "accepts": field["accepts"],
             "description": field["description"]}
            for name, field in step["params"]["fields"].items()
            if name not in consumed
        ]

        declared = {o["name"] for o in block.get("outputs") or []}
        unreadable = [
            name for name in declared
            if name not in readable and _camel(name) not in readable
            and name not in UNIVERSAL_RETURNS
        ]
        engine_only_outputs = [name for name in readable if name not in declared]

        rows.append({
            "kind": "matched", "uses": uses, "engine": resolved,
            "renamed": uses != resolved, "path": block["_path"], "label": block.get("label"),
            "params_extra": step["params"]["extra"],
            "dropped_params": dropped, "bound_params": bound,
            "required_drift": required_drift, "engine_only_params": engine_only_params,
            "unreadable_returns": sorted(unreadable),
            "engine_only_outputs": sorted(engine_only_outputs),
        })
    return {"rows": rows, "engine_only_steps": sorted(n for n in engine if n not in matched)}


# -- Reporting ----------------------------------------------------------------


def report(result: dict) -> int:
    rows = result["rows"]
    matched = [r for r in rows if r["kind"] == "matched"]
    unresolvable = [r for r in rows if r["kind"] == "unresolvable"]
    renamed = [r for r in matched if r["renamed"]]

    def section(title: str, lines: list[str]) -> None:
        print(f"\n== {title} ==")
        for line in lines or ["  (none)"]:
            print(line)

    section(
        f"A. uses does not resolve ({len(renamed) + len(unresolvable)})",
        [f"   {r['uses']} -> {r['engine']}" for r in renamed]
        + [f"   {r['uses']} -> NOTHING ({r['label']})" for r in unresolvable],
    )
    section(
        "B. IDE params the engine silently drops",
        [f"   {r['uses']} [extra={r['params_extra']}]: "
         + ", ".join(f"{p['name']}{'*' if p['required'] else ''}" for p in r["dropped_params"])
         for r in matched if r["dropped_params"]],
    )
    section(
        "C. IDE returns nothing in the output resolves",
        [f"   {r['uses']}: " + ", ".join(r["unreadable_returns"])
         for r in matched if r["unreadable_returns"]],
    )
    section(
        "D. required in IDE, optional in engine (benign)",
        [f"   {r['uses']}: " + ", ".join(r["required_drift"])
         for r in matched if r["required_drift"]],
    )
    section(
        "E. engine params the IDE does not offer",
        [f"   {r['uses']}: " + ", ".join(p["name"] for p in r["engine_only_params"])
         for r in matched if r["engine_only_params"]],
    )
    section(
        "F. registered steps with no IDE block",
        [f"   {name}" for name in result["engine_only_steps"]],
    )
    section(
        "G. IDE params that bind only through an alias",
        [f"   {r['uses']}: "
         + ", ".join(f"{p['ide']} -> {p['engine']}" for p in r["bound_params"] if p["via_alias"])
         for r in matched if any(p["via_alias"] for p in r["bound_params"])],
    )

    breaking = (
        len(renamed) + len(unresolvable)
        + sum(len(r["dropped_params"]) for r in matched)
        + sum(len(r["unreadable_returns"]) for r in matched)
        + sum(1 for r in matched for p in r["bound_params"] if p["via_alias"])
    )
    print(f"\n{breaking} breaking divergence(s) across {len(rows)} IDE blocks.")
    return 1 if breaking else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ide", type=Path, default=Path.home() / "catenax-eV" / "cx-test-suite",
        help="Checkout of the cx-test-suite repository.",
    )
    parser.add_argument("--json", type=Path, help="Write the full diff to this file.")
    parser.add_argument(
        "--check", action="store_true",
        help="Exit 1 when any breaking divergence remains.",
    )
    args = parser.parse_args()

    blocks_dir = args.ide / "public" / "blocks"
    if not blocks_dir.is_dir():
        parser.error(f"No block catalog at {blocks_dir}")

    result = compare(read_engine(), read_ide(blocks_dir))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2))
    exit_code = report(result)
    return exit_code if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
