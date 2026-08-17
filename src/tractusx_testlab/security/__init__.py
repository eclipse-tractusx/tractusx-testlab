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

"""Security module — key generation, encryption, signing, identity, and trust store.

Sub-modules:
    crypto — key generation, encryption, and digital signing
    trust  — player identity, trust store, and vault client
"""

from tractusx_testlab.security.crypto.encryption import decrypt_package, encrypt_package
from tractusx_testlab.security.crypto.keygen import (
    KeyPair,
    generate_ed25519_keypair,
    generate_rsa_keypair,
)
from tractusx_testlab.security.crypto.signing import sign_bytes, verify_signature
from tractusx_testlab.security.trust.identity import PlayerIdentity
from tractusx_testlab.security.trust.trust_store import TrustStore
from tractusx_testlab.security.trust.vault import VaultClient

__all__ = [
    # Crypto
    "KeyPair",
    # Trust
    "PlayerIdentity",
    "TrustStore",
    "VaultClient",
    "decrypt_package",
    "encrypt_package",
    "generate_ed25519_keypair",
    "generate_rsa_keypair",
    "sign_bytes",
    "verify_signature",
]
