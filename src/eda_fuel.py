"""Exploratory analysis for processed fuel-system scenarios."""

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

from src.data.fuel_system import FUEL_SENSOR_COLUMNS

FUEL_NON_FEATURE_COLUMNS = frozenset(
    {"scenario_id", "scenario_code", "sample_index", "is_abnormal"}
)


def analyze_fuel_system(
    project_root: Path, table: pd.DataFrame | None = None
) -> dict[str, object]:
    """Audit scenario trajectories and save comparison figures."""

    data = table.copy() if table is not None else pd.read_csv(
        project_root / "data" / "processed" / "fuel_system" / "scenario_features.csv"
    )
    feature_columns = [
        column for column in data.columns if column not in FUEL_NON_FEATURE_COLUMNS
    ]
    if not np.isfinite(data[feature_columns].to_numpy(dtype=float)).all():
        raise ValueError("Fuel feature table contains non-finite values.")

    normal = data.loc[data["scenario_id"] == "normal"]
    normal_mean = normal.loc[:, FUEL_SENSOR_COLUMNS].mean()
    normal_std = normal.loc[:, FUEL_SENSOR_COLUMNS].std(ddof=0).replace(0, 1.0)
    scenario_order = ["normal", "one", "two", "three", "four"]
    mean_shift = pd.DataFrame(
        {
            scenario: (
                data.loc[data["scenario_id"] == scenario, FUEL_SENSOR_COLUMNS].mean()
                - normal_mean
            )
            / normal_std
            for scenario in scenario_order
        }
    ).T
    top_shifts: dict[str, list[dict[str, object]]] = {}
    for scenario in scenario_order[1:]:
        row = mean_shift.loc[scenario]
        top = row.abs().nlargest(3).index
        top_shifts[scenario] = [
            {"sensor": sensor, "normal_standard_deviations": float(row[sensor])}
            for sensor in top
        ]

    figure_dir = project_root / "reports" / "figures" / "fuel_system"
    metrics_dir = project_root / "reports" / "metrics"
    figure_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    colors = {
        "normal": "#16a34a",
        "one": "#2563eb",
        "two": "#f59e0b",
        "three": "#dc2626",
        "four": "#7c3aed",
    }
    fig, axes = plt.subplots(4, 2, figsize=(14, 15), sharex=True)
    for ax, sensor in zip(axes.flat, FUEL_SENSOR_COLUMNS):
        for scenario in scenario_order:
            rows = data.loc[data["scenario_id"] == scenario]
            ax.plot(
                rows["sample_index"], rows[sensor], label=scenario.title(),
                color=colors[scenario], linewidth=1.25, alpha=0.9,
            )
        ax.set(title=sensor, ylabel="Sensor value")
        ax.grid(alpha=0.2)
    axes[-1, 0].set_xlabel("Ordered sample index")
    axes[-1, 1].set_xlabel("Ordered sample index")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5)
    fig.suptitle("Fuel-System Sensor Trajectories by Neutral Scenario", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(figure_dir / "fuel_sensor_trajectories.png", dpi=160)
    plt.close(fig)

    abnormal_shift = mean_shift.loc[scenario_order[1:]]
    limit = max(1.0, float(np.abs(abnormal_shift.to_numpy()).max()))
    fig, ax = plt.subplots(figsize=(11, 5.5))
    image = ax.imshow(
        abnormal_shift.to_numpy(), cmap="coolwarm", aspect="auto",
        vmin=-limit, vmax=limit,
    )
    ax.set(
        title="Scenario Mean Shift Relative to Normal",
        xticks=np.arange(len(FUEL_SENSOR_COLUMNS)),
        xticklabels=FUEL_SENSOR_COLUMNS,
        yticks=np.arange(4),
        yticklabels=[f"Scenario {name.title()}" for name in scenario_order[1:]],
    )
    fig.colorbar(image, ax=ax, label="Normal standard deviations")
    fig.tight_layout()
    fig.savefig(figure_dir / "fuel_scenario_mean_shift.png", dpi=160)
    plt.close(fig)

    result = {
        "rows": len(data),
        "scenarios": int(data["scenario_id"].nunique()),
        "raw_sensors": len(FUEL_SENSOR_COLUMNS),
        "model_features": len(feature_columns),
        "missing_values": int(data.isna().sum().sum()),
        "duplicate_feature_rows": int(data.duplicated(subset=feature_columns).sum()),
        "top_standardized_mean_shifts_from_normal": top_shifts,
        "warning": (
            "Mean shifts are descriptive. Neutral abnormal scenario IDs do not "
            "establish named physical fault causes."
        ),
    }
    (metrics_dir / "fuel_system_eda.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(analyze_fuel_system(root), indent=2))


if __name__ == "__main__":
    main()
