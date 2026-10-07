# 2. Common Header

**[SPEC]** Every declaration file begins with the same two fields. A parser reads them first and only then
decides how to interpret the rest of the document.

```yaml
kind: tck          # or: test
syntax: v1-alpha
```

| Field | R/O | Values | Notes |
|---|---|---|---|
| `kind` | R | `tck` \| `test` | Fixed. Used in every declaration file so the parser knows how to read it. |
| `syntax` | R | `v1-alpha` | Engine/Test Lab library syntax version, i.e. which technical capabilities are available. Should not change often. |

> ⚠️ **Known inconsistency [PROP-P6].** The `index.yaml` screenshot on slide 17 shows `testlab: v1-alpha` and a
> top-level `namespace: ccm-v0.0.1`; the field specification on slide 18 shows `syntax: v1-alpha` and no
> manifest-level `namespace`. **This document treats slide 18 as normative**: the key is `syntax:` everywhere,
> and `namespace:` appears **only in test files**. Confirm before freezing `v1-alpha`.
