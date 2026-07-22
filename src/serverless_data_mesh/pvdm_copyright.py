"""Copyright notice for the Vaquar Pattern (PVDM) proprietary method.

The open-source ``serverless-data-mesh`` package is Apache-2.0. The **method**
name, acronym, and four-phase invariant remain proprietary to Vaquar Khan.
"""

from __future__ import annotations

INVENTOR = "Vaquar Khan"
METHOD_NAME = "Vaquar Pattern"
ACRONYM = "PVDM"
PHASES = "Physical · Verify · Durable · Metadata"
YEARS = "2024–2026"

# Short line for UI eyebrows, dashboards, and CLI banners.
NOTICE_SHORT = (
    f"© {YEARS} {INVENTOR}. {ACRONYM} ({METHOD_NAME}) — proprietary method. "
    "All rights reserved in the method name and invariants."
)

# One-line attribution for method fields / footers.
ATTRIBUTION = (
    f"{METHOD_NAME} ({ACRONYM}) — proprietary method by {INVENTOR} "
    f"© {YEARS}. Reference implementation Apache-2.0."
)

# Full notice for docs, NOTICE file, and generated READMEs.
NOTICE_FULL = f"""\
{METHOD_NAME} ({ACRONYM}: {PHASES})
Copyright © {YEARS} {INVENTOR}. All rights reserved.

{ACRONYM} and the {METHOD_NAME} are proprietary architectural methods of
{INVENTOR}. The method name, operational acronym, and publication invariant
(commit_metadata ⟹ VRP = PASS) may not be rebranded or claimed as an
independent invention without attribution to the inventor.

This repository's reference implementation (serverless-data-mesh) is licensed
under the Apache License 2.0. Use of the open-source code does not transfer
ownership of the proprietary method.
"""
