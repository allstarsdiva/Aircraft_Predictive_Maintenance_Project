"""Exploratory analysis for the landing-gear digital-twin events."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

_cache = Path(tempfile.gettempdir()) / "aircraft-matplotlib-cache"
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data.landing_gear import LANDING_GEAR_FAULT_NAMES
from src.preprocess_landing_gear import LANDING_GEAR_MODEL_FEATURES

LANDING_GEAR_NON_FEATURE_COLUMNS = frozenset(
    {"run_id", "fault_code", "rul_percent", "is_fault", "fault_name"}
)
LANDING_GEAR_OBSERVABLE_FEATURES = (
    "max_deflection",
    "max_velocity",
    "settling_time",
    "mass",
)
LANDING_GEAR_PHYSICS_FEATURES = LANDING_GEAR_MODEL_FEATURES


def analyze_landing_gear(
    project_root: Path, table: pd.DataFrame | None = None
) -> dict[str, object]:
    """Audit feature/target structure and save descriptive figures."""

    data = table.copy() if table is not None else pd.read_csv(
        project_root / "data" / "processed" / "landing_gear" / "validated_runs.csv"
    )
    if not np.isfinite(data[list(LANDING_GEAR_PHYSICS_FEATURES)].to_numpy(float)).all():
        raise ValueError("Landing-gear feature table contains non-finite values")

    transitions = data.loc[
        data["fault_code"].diff().fillna(0).ne(0), ["run_id", "fault_code"]
    ]
    correlations = data[[*LANDING_GEAR_PHYSICS_FEATURES, "rul_percent"]].corr()
    by_fault = data.groupby("fault_code", sort=True).agg(
        rows=("run_id", "size"),
        rul_min=("rul_percent", "min"),
        rul_mean=("rul_percent", "mean"),
        rul_median=("rul_percent", "median"),
        rul_max=("rul_percent", "max"),
    )

    figure_dir = project_root / "reports" / "figures" / "landing_gear"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    colors = ["#16a34a", "#2563eb", "#f59e0b", "#dc2626"]
    fig, axes = plt.subplots(3, 2, figsize=(13, 13))
    for ax, feature in zip(axes.flat, LANDING_GEAR_PHYSICS_FEATURES):
        for code, color in zip(sorted(LANDING_GEAR_FAULT_NAMES), colors):
            rows = data.loc[data["fault_code"] == code, feature]
            ax.hist(rows, bins=24, alpha=0.45, color=color,
                    label=LANDING_GEAR_FAULT_NAMES[code].replace("_", " ").title())
        ax.set(title=feature.replace("_", " ").title(), ylabel="Events")
        ax.grid(alpha=0.15)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2)
    fig.suptitle("Landing-Gear Feature Distributions by Fault Class", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(figure_dir / "landing_gear_feature_distributions.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, feature in zip(axes, ("max_velocity", "settling_time", "k_stiffness")):
        scatter = ax.scatter(
            data[feature], data["rul_percent"], c=data["fault_code"],
            cmap="viridis", s=12, alpha=0.55,
        )
        ax.set(xlabel=feature.replace("_", " ").title(), ylabel="RUL (%)")
        ax.grid(alpha=0.15)
    fig.colorbar(scatter, ax=axes, label="Fault code", shrink=0.8)
    fig.suptitle("Landing-Gear RUL Relationships")
    fig.subplots_adjust(left=0.06, right=0.94, bottom=0.12, top=0.86, wspace=0.27)
    fig.savefig(figure_dir / "landing_gear_rul_relationships.png", dpi=160)
    plt.close(fig)

    result = {
        "rows": len(data),
        "model_features": len(LANDING_GEAR_PHYSICS_FEATURES),
        "missing_values": int(data.isna().sum().sum()),
        "duplicate_feature_rows": int(
            data.duplicated(subset=list(LANDING_GEAR_PHYSICS_FEATURES)).sum()
        ),
        "fault_counts": {
            str(code): int(count)
            for code, count in data["fault_code"].value_counts().sort_index().items()
        },
        "fault_rul_summary": {
            str(code): {key: float(value) for key, value in row.items()}
            for code, row in by_fault.to_dict(orient="index").items()
        },
        "rul_correlations": {
            feature: float(correlations.loc[feature, "rul_percent"])
            for feature in LANDING_GEAR_PHYSICS_FEATURES
        },
        "fault_order_transitions": transitions.to_dict(orient="records"),
        "run_id_excluded": True,
        "warning": (
            "This is synthetic within-dataset EDA. Stiffness and damping are latent "
            "physics parameters, not confirmed directly measured aircraft sensors."
        ),
    }
    (metrics_dir / "landing_gear_eda.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(analyze_landing_gear(root), indent=2))


if __name__ == "__main__":
    main()
