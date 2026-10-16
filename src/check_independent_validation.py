"""Check a user-supplied independent-validation intake manifest."""

from __future__ import annotations

import argparse
import json

from src.independent_validation import validate_manifest_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="CSV manifest with one row per independent group")
    args = parser.parse_args()
    result = validate_manifest_file(args.manifest)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
