"""Execute a notebook's Python code cells without modifying the notebook file.

This lightweight validation command is useful in CI and new environments before
the full Jupyter toolchain is installed. Notebook outputs are not persisted, but
all code cells share one namespace and generated files are still produced.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import warnings
from pathlib import Path


def validate_notebook(path: Path) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__"}
    executed = 0

    with tempfile.TemporaryDirectory(prefix="aircraft-mpl-") as config_dir:
        os.environ.setdefault("MPLCONFIGDIR", config_dir)
        warnings.filterwarnings(
            "ignore", message="FigureCanvasAgg is non-interactive.*", category=UserWarning
        )
        for index, cell in enumerate(notebook.get("cells", []), start=1):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            if not source.strip():
                continue
            compiled = compile(source, f"{path}#cell-{index}", "exec")
            exec(compiled, namespace)
            executed += 1

    print(f"Validated {executed} code cells in {path}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    args = parser.parse_args()
    validate_notebook(args.notebook.resolve())


if __name__ == "__main__":
    main()
