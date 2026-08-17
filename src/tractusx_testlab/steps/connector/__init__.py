#################################################################################
# Eclipse Tractus-X - Software Development KIT
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

# Every module that declares a connector step, imported so its ``@step``
# decorators run.  Each module is named here directly rather than reached
# through another module's imports: a step that only registers as a side effect
# of someone else's import is a step that silently disappears when that import
# is tidied away.
import tractusx_testlab.steps.connector.catalog_filter  # noqa: F401
import tractusx_testlab.steps.connector.catalog_query  # noqa: F401
import tractusx_testlab.steps.connector.cleanup  # noqa: F401
import tractusx_testlab.steps.connector.dataplane  # noqa: F401
import tractusx_testlab.steps.connector.do_dsp  # noqa: F401
import tractusx_testlab.steps.connector.extract  # noqa: F401
import tractusx_testlab.steps.connector.negotiate  # noqa: F401
import tractusx_testlab.steps.connector.provision  # noqa: F401
import tractusx_testlab.steps.connector.pull_data  # noqa: F401
import tractusx_testlab.steps.connector.transfer  # noqa: F401
import tractusx_testlab.steps.connector.utils  # noqa: F401
