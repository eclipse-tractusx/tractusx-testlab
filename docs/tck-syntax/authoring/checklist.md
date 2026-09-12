# 10. Authoring Checklist

Before submitting a TCK for compilation:

- [ ] Every file declares `kind` and `syntax`.
- [ ] `metadata.standards[]` lists every standard the TCK certifies, with versions.
- [ ] `dataspace.version` is set.
- [ ] `infrastructure.engine` and `infrastructure.sut` reflect what the tests actually need.
- [ ] Every `tests[].id` resolves to a file in `/tests`.
- [ ] Every test's `namespace` equals the manifest `id`.
- [ ] Every test file's `execution` has at least one step, and every step at least one `validate`.
- [ ] Every `uses:` key exists in the capability catalogue for this `syntax` version.
- [ ] Every `${{ }}` reference resolves backwards to `env`, `testdata`, or a prior step's declared `returns`.
- [ ] **No test reads another test's outputs** — tests are independent.
- [ ] `teardown` removes everything `setup` and `execution` created in the live dataspace.
- [ ] Versions and numeric-looking strings are quoted (`version: "1.0"`, not `version: 1.0`).
- [ ] No secrets are hard-coded; credentials come from `source: input` variables.
- [ ] *(On ratification of P1)* Every validation carries a `cac:` reference, and coverage of the standard's CAC
      set is complete.
