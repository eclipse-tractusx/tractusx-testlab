################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Combination tests — steps running together, the way a TCK runs them.

Every other test file in this suite asks whether one step, on its own, does
what its contract says. These ask the question a TCK author actually has: does
what step A produces arrive at step B?

That question has its own failure modes, and none of them are visible from a
single step. A step can publish exactly the fields it declares and still be
unreadable, because the name a later step reads it under is assembled somewhere
else entirely. Both halves can be right and the join between them wrong.
"""
