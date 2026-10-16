"""Metadata-only gate for genuinely independent model evaluation groups.

This checks a validation manifest's structure, not the scientific validity of a
dataset, its labels, or any resulting model score.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

COMPONENTS = ("engine", "battery", "hydraulic", "fuel-system", "landing-gear")
PARTITIONS = ("external_calibration", "frozen_test")
REQUIRED_COLUMNS = (
    "component", "group_id", "partition", "source_url", "source_version",
    "license_or_access_terms", "raw_sha256", "acquired_utc", "label_method",
    "independent_from_development", "used_for_tuning",
)
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def validate_manifest_rows(rows: list[dict[str, str]]) -> dict[str, object]:
    issues: list[str] = []
    if not rows:
        return {"valid": False, "status": "blocked_no_external_groups", "issues": ["Manifest has no dataset-group rows."], "components": {}}

    seen: set[tuple[str, str]] = set()
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    clean_rows: list[dict[str, str]] = []
    for row_number, row in enumerate(rows, start=2):
        values = {str(key).strip(): str(value or "").strip() for key, value in row.items()}
        missing = [column for column in REQUIRED_COLUMNS if not values.get(column)]
        if missing:
            issues.append(f"Row {row_number}: missing {', '.join(missing)}.")
            continue
        component = values["component"].lower()
        partition = values["partition"].lower()
        if component not in COMPONENTS:
            issues.append(f"Row {row_number}: unknown component {component!r}.")
            continue
        if partition not in PARTITIONS:
            issues.append(f"Row {row_number}: partition must be one of {', '.join(PARTITIONS)}.")
            continue
        key = (component, values["group_id"])
        if key in seen:
            issues.append(f"Row {row_number}: group {values['group_id']!r} appears more than once for {component}.")
        seen.add(key)
        if not values["source_url"].lower().startswith(("https://", "http://")):
            issues.append(f"Row {row_number}: source_url must identify a documented source.")
        if not _SHA256.fullmatch(values["raw_sha256"]):
            issues.append(f"Row {row_number}: raw_sha256 must be 64 hexadecimal characters.")
        independent = values["independent_from_development"].lower()
        tuned = values["used_for_tuning"].lower()
        if independent not in {"true", "false"} or tuned not in {"true", "false"}:
            issues.append(f"Row {row_number}: independence/tuning fields must be true or false.")
        if partition == "frozen_test" and independent != "true":
            issues.append(f"Row {row_number}: frozen_test group {values['group_id']!r} is not declared independent.")
        if partition == "frozen_test" and tuned != "false":
            issues.append(f"Row {row_number}: frozen_test group {values['group_id']!r} was used for tuning.")
        counts[component][partition] += 1
        clean_rows.append(values)

    component_summary = {}
    for component in COMPONENTS:
        per_partition = {partition: counts[component][partition] for partition in PARTITIONS}
        component_summary[component] = per_partition
        if not any(per_partition.values()):
            issues.append(f"No independent-validation groups recorded for {component}.")
        for partition in PARTITIONS:
            if per_partition[partition] == 0:
                issues.append(f"{component} has no {partition} group.")

    return {
        "valid": not issues,
        "status": "manifest_structure_pass_not_model_validation" if not issues else "blocked_manifest_incomplete_or_inconsistent",
        "issues": issues,
        "components": component_summary,
        "groups_checked": len(clean_rows),
        "meaning": "A pass checks metadata structure only; domain review and model evaluation are still required.",
    }


def validate_manifest_file(path: str | Path) -> dict[str, object]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            return {"valid": False, "status": "blocked_manifest_schema", "issues": [f"Missing columns: {', '.join(missing)}."], "components": {}}
        return validate_manifest_rows(list(reader))
