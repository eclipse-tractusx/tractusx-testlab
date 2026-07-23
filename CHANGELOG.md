# Changelog

All notable changes to this repository will be documented in this file.
Further information can be found on the [README.md](README.md) file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- Initial repository setup following TRG 2.03 release guidelines
- `validate/schema` step performing full JSON Schema validation of a payload
  against a schema declared in `env.schemas`
- `env.schemas` files are now seeded into the runtime context, resolvable via
  `${{ env.schemas.<id> }}` (both raw and compiled package layouts)
- `json_path_extract` predicate filters (`items[key=value]`), array traversal
  without an index, and nested/dotted predicate keys
- `util/parse_kv` step for parsing delimited `key=value` strings such as an EDC
  `subprotocolBody`
- `util/base64` step for encoding/decoding strings with base64 / base64url, e.g.
  building a base64url `aas_identifier` for the AAS DTR
- `util/log` step for echoing a resolved value while authoring a test

### Fixed

- Path extraction no longer drops predicate values containing `.`/`;`/`#` and
  can traverse into lists after the first segment
- `json_path_extract` accepts a resolved object (a `${{ }}` expression) as its
  `source`, not only a variable name
