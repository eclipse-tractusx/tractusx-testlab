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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""YAML field-key constants used when reading/writing test documents."""

# -- Document header ----------------------------------------------------------
NAME = "name"
VERSION = "version"
DESCRIPTION = "description"
DATASPACE_VERSION = "dataspace_version"
KIND = "kind"
TYPE = "type"

# -- Script structure ---------------------------------------------------------
IMPORT = "import"
IMPORTS = "imports"
VARIABLES = "variables"
SETUP = "setup"
STEPS = "steps"
TEARDOWN = "teardown"
SERVICES = "services"

# -- ADR-0019 topology blocks -------------------------------------------------
DATASPACE = "dataspace"
INFRASTRUCTURE = "infrastructure"
ECOSYSTEM = "ecosystem"
ENGINE = "engine"
SUT = "sut"
REQUIRED = "required"
STANDARD = "standard"
ID = "id"

# -- TCK ----------------------------------------------------------------------
TEST = "test"
TESTS = "tests"
OUTPUTS = "outputs"

# -- Step fields --------------------------------------------------------------
ALLOW_SDK_CALLS = "allow_sdk_calls"
PARAMS = "params"
EXPECT = "validate"
TIMEOUT_S = "timeout_s"
STORE_IN_MEMORY = "store_in_memory"
IF = "if"

# -- Service fields -----------------------------------------------------------
BASE_URL = "base_url"
AUTH = "auth"

# -- Assertion fields ---------------------------------------------------------
VALUE = "value"
PATH = "path"
SOURCE = "source"
SEVERITY = "severity"
OUTPUT = "output"

# -- Assertion type keys (compact format) ------------------------------------
NOT_NULL = "not_null"
NOT_EMPTY = "not_empty"
EQUALS = "equals"
NOT_EQUALS = "not_equals"
CONTAINS_KEY = "contains"
NOT_CONTAINS_KEY = "not_contains"
MATCHES = "matches"
SCHEMA_KEY = "schema"
VALIDATES_AGAINST_SCHEMA = "validates_against_schema"
GREATER_THAN = "greater_than"
LESS_THAN = "less_than"
GREATER_OR_EQUAL = "greater_or_equal"
LESS_OR_EQUAL = "less_or_equal"
BETWEEN = "between"

# -- Typed assertion extra fields --------------------------------------------
ASSERTION_SCHEMA = "schema"
ASSERTION_MIN = "min"
ASSERTION_MAX = "max"

# -- Service config -----------------------------------------------------------
CONFIG = "config"
MANAGEMENT_URL = "management_url"

# -- Step output definitions --------------------------------------------------
OUTPUT_DEFINITIONS = "output_definitions"

# -- Variable fields ----------------------------------------------------------
RUNTIME = "runtime"

# -- Variable verb form (LOCKED GRAMMAR v1) -----------------------------------
USES = "uses"
WITH = "with"
RETURNS = "returns"
PLACEHOLDER = "placeholder"
FORMAT = "format"
# Verb namespaces: simple variables use `variable/type/<type>`; generated
# variables use `generate/<gen>`.
VARIABLE = "variable"
GENERATE = "generate"
SCOPE = "scope"

# -- Test case entry ----------------------------------------------------------
TEST = "test"

# -- Dependency ref -----------------------------------------------------------
FILE = "file"
