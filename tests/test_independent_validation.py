from src.independent_validation import COMPONENTS, REQUIRED_COLUMNS, validate_manifest_rows


def complete_rows():
    rows = []
    for component in COMPONENTS:
        for partition, group, tuned in (
            ("external_calibration", f"{component}-cal", "false"),
            ("frozen_test", f"{component}-test", "false"),
        ):
            rows.append({
                "component": component, "group_id": group, "partition": partition,
                "source_url": "https://example.org/documented-dataset",
                "source_version": "1.0", "license_or_access_terms": "research use",
                "raw_sha256": "a" * 64, "acquired_utc": "2026-09-30T00:00:00Z",
                "label_method": "source-provided event labels",
                "independent_from_development": "true", "used_for_tuning": tuned,
            })
    return rows


def test_all_component_groups_pass_manifest_structure_only():
    result = validate_manifest_rows(complete_rows())
    assert result["valid"] is True
    assert result["status"] == "manifest_structure_pass_not_model_validation"
    assert result["groups_checked"] == len(COMPONENTS) * 2


def test_empty_manifest_remains_blocked():
    result = validate_manifest_rows([])
    assert result["valid"] is False
    assert result["status"] == "blocked_no_external_groups"


def test_frozen_test_cannot_be_tuned_or_reused():
    rows = complete_rows()
    rows[1]["used_for_tuning"] = "true"
    rows[3]["independent_from_development"] = "false"
    result = validate_manifest_rows(rows)
    assert result["valid"] is False
    assert any("used for tuning" in issue for issue in result["issues"])
    assert any("not declared independent" in issue for issue in result["issues"])


def test_duplicate_groups_and_bad_hashes_fail():
    rows = complete_rows()
    rows[1]["group_id"] = rows[0]["group_id"]
    rows[0]["raw_sha256"] = "not-a-hash"
    result = validate_manifest_rows(rows)
    assert result["valid"] is False
    assert any("appears more than once" in issue for issue in result["issues"])
    assert any("64 hexadecimal" in issue for issue in result["issues"])
