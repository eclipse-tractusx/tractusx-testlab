# Notices for Eclipse Tractus-X

This content is produced and maintained by the Eclipse Tractus-X project.

* Project home: https://projects.eclipse.org/projects/automotive.tractusx

## Trademarks

Eclipse Tractus-X is a trademark of the Eclipse Foundation.

## Copyright

All content is the property of the respective authors or their employers. For
more information regarding authorship of content, please consult the listed
source code repository logs.

## Declared Project Licenses

The Tractus-X project uses the following licenses:

- Apache-2.0 for code
- CC-BY-4.0 for non-code

Apache-2.0:
This program and the accompanying materials are made available under the terms of the Apache License, Version 2.0 which is available at https://www.apache.org/licenses/LICENSE-2.0.
SPDX-License-Identifier: Apache-2.0

CC-BY-4.0:
The materials in this repository are made available under the terms of the Creative Commons Attribution 4.0 International License, which is available at https://spdx.org/licenses/CC-BY-4.0.html.
SPDX-License-Identifier: CC-BY-4.0

## Source Code

The project maintains the following source code repositories:

* https://github.com/eclipse-tractusx/tractusx-testlab


## Third-party Content

This project leverages the following third party content.

Test fixtures only — OpenAPI documents vendored unchanged except where noted,
each keeping its own license header:

* `tests/e2e/connector-dtr-smoke/apis/aas-registry-openapi.yaml` — the Asset
  Administration Shell Registry API of Eclipse Tractus-X
  sldt-digital-twin-registry v0.11.0
  (https://github.com/eclipse-tractusx/sldt-digital-twin-registry,
  `backend/src/main/resources/static/aas-registry-openapi.yaml`), Apache-2.0.
  It is derived from the IDTA "Specification of the Asset Administration
  Shell: Part 2" (CC-BY-4.0, Industrial Digital Twin Association). Two
  external `$ref`s were pointed at the document's own components so the file
  is self-contained; the file header records the change.
* `tests/fixtures/openapi/industry-core-hub.yaml` — the backend API of Eclipse
  Tractus-X Industry Core Hub
  (https://github.com/eclipse-tractusx/industry-core-hub,
  `docs/api/openAPI.yaml`), Apache-2.0, unchanged.

## Cryptography

Content may contain encryption software. The country in which you are currently
may have restrictions on the import, possession, and use, and/or re-export to
another country, of encryption software. BEFORE using any encryption software,
please check the country's laws, regulations and policies concerning the import,
possession, or use, and re-export of encryption software, to see if this is
permitted.
