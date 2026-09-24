"""Reproducible exploratory analysis for processed hydraulic cycles."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

_matplotlib_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_matplotlib_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_matplotlib_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data.hydraulic import PROFILE_COLUMNS

HYDRAULIC_TARGETS = PROFILE_COLUMNS[:-1]
HYDRAULIC_NON_FEATURE_COLUMNS = frozenset({"cycle_id", *PROFILE_COLUMNS})


def analyze_hydraulic_features(
    project_root: Path, table: pd.DataFrame | None = None
) -> dict[str, object]:
    """Audit processed cycles and save distributions and correlation figures."""

    data = (
        table.copy()
        if table is not None
        else pd.read_csv(
            project_root / "data" / "processed" / "hydraulic" / "cycle_features.csv"
        )
    )
    feature_columns = [
        column for column in data.columns if column not in HYDRAULIC_NON_FEATURE_COLUMNS
    ]
    if not np.isfinite(data[feature_columns].to_numpy()).all():
        raise ValueError("Hydraulic feature table contains non-finite values.")
    stable = data.loc[data["stable_flag"] == 0]
    zero_variance = [
        column for column in feature_columns if data[column].nunique(dropna=False) <= 1
    ]
    duplicate_feature_rows = int(data.duplicated(subset=feature_columns).sum())

    top_correlations: dict[str, list[dict[str, object]]] = {}
    correlation_features = [
        column for column in feature_columns if stable[column].nunique(dropna=False) > 1
    ]
    for target in HYDRAULIC_TARGETS:
        correlations = (
            stable[correlation_features]
            .corrwith(stable[target], method="spearman")
            .dropna()
        )
        top = correlations.abs().nlargest(10).index
        top_correlations[target] = [
            {"feature": feature, "spearman": float(correlations[feature])}
            for feature in top
        ]

    figure_dir = project_root / "reports" / "figures" / "hydraulic"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, target in zip(axes.flat, HYDRAULIC_TARGETS):
        counts = data[target].value_counts().sort_index()
        ax.bar(counts.index.astype(str), counts.values, color="#0f766e")
        ax.set(title=target.replace("_", " ").title(), xlabel="Class", ylabel="Cycles")
    fig.suptitle("Hydraulic Condition Target Distributions")
    fig.tight_layout()
    fig.savefig(figure_dir / "hydraulic_target_distributions.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, target in zip(axes.flat, HYDRAULIC_TARGETS):
        rows = top_correlations[target][::-1]
        ax.barh(
            [str(item["feature"]) for item in rows],
            [float(item["spearman"]) for item in rows],
            color=["#2563eb" if float(item["spearman"]) >= 0 else "#dc2626" for item in rows],
        )
        ax.axvline(0, color="#111827", linewidth=0.8)
        ax.set(title=target.replace("_", " ").title(), xlabel="Spearman correlation")
    fig.suptitle("Top Stable-Cycle Feature Associations")
    fig.tight_layout()
    fig.savefig(figure_dir / "hydraulic_top_feature_correlations.png", dpi=160)
    plt.close(fig)

    result = {
        "rows": len(data),
        "features": len(feature_columns),
        "stable_rows": len(stable),
        "potentially_unstable_rows": int((data["stable_flag"] == 1).sum()),
        "missing_values": int(data.isna().sum().sum()),
        "duplicate_feature_rows": duplicate_feature_rows,
        "zero_variance_features": zero_variance,
        "target_counts": {
            target: {
                str(key): int(value)
                for key, value in data[target].value_counts().sort_index().items()
            }
            for target in HYDRAULIC_TARGETS
        },
        "top_stable_cycle_spearman_correlations": top_correlations,
    }
    (metrics_dir / "hydraulic_eda.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(analyze_hydraulic_features(root), indent=2))


if __name__ == "__main__":
    main()
