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

"""Server package — lazy imports to avoid circular dependencies with steps."""

from __future__ import annotations


def create_app(*args, **kwargs):
    """Lazy proxy to app.create_app — avoids circular import at module load."""
    from tractusx_testlab.server.app import create_app as _create_app

    return _create_app(*args, **kwargs)


def __getattr__(name):
    if name == "PackageStorage":
        from tractusx_testlab.server.storage import PackageStorage

        return PackageStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["PackageStorage", "create_app"]
