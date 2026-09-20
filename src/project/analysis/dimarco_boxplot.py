"""Compare Dimarco's match-level FV across 2023–24, 2024–25 and 2025–26.

Run: .venv/bin/python -m project.analysis.dimarco_boxplot
Reuse an extraction with --csv output/dimarco-player-fv.csv.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sqlalchemy import text

from project.analysis.queries import connect_database


SEASONS = [2023, 2024, 2025]
QUERY_PATH = Path(__file__).with_name("dimarco_player_fv.sql")


def plot_dimarco_fv(data):
    """Return a three-season box plot and descriptive match-level statistics."""
    if data.empty or set(data["performance_season"]) != set(SEASONS):
        raise ValueError("Expected FV observations for all three seasons: 2023, 2024, 2025.")
    if set(data["player_name"]) != {"Dimarco"} or len(data[["player_id", "source_id"]].drop_duplicates()) != 1:
        raise ValueError("Expected a single Dimarco player/source identity.")
    if data["fv"].isna().any():
        raise ValueError("Expected non-null match-level FV observations.")
    if data.duplicated(["player_id", "source_id", "fixture_id"]).any():
        raise ValueError("Duplicate player/source/fixture observations.")
    summary = data.groupby("performance_season")["fv"].describe().reindex(SEASONS)
    with sns.axes_style("whitegrid"), plt.rc_context({"svg.fonttype": "none"}):
        fig, ax = plt.subplots(figsize=(10, 7))
        sns.boxplot(data=data, x="performance_season", y="fv", order=SEASONS,
                    color="#2878B5", saturation=0.85, width=0.48,
                    whis=1.5, linewidth=1.4, fliersize=5, ax=ax)
        # ax.axhline(6, color="#64748b", linestyle="--", linewidth=1)
        # ax.set_xticks(range(len(SEASONS)), [
        #     f"{season}–{str(season + 1)[-2:]}\nn = {int(summary.loc[season, 'count'])}"
        #     for season in SEASONS
        # ])
        ax.set_xlabel("")
        ax.set_ylabel("Fanta Voto (FV)", fontsize=12)
        ax.tick_params(axis="both", labelsize=11)
        ax.grid(axis="x", visible=False)
        sns.despine(ax=ax)
        fig.suptitle("Dimarco, FV across three seasons", fontsize=20, y=0.96)
        # fig.text(0.5, 0.895, "Match-level distributions · 2023–24 to 2025–26",
                #  ha="center", fontsize=11, color="#475569")
        # fig.text(0.10, 0.04,
        #          "Box: middle 50% · Line: median · Whiskers: up to 1.5 × IQR · Points: outliers\n"
        #          "Dashed line: FV = 6 · n: non-null FV observations · Redazione Fantacalcio",
        #          fontsize=9, color="#475569", linespacing=1.7)
        fig.subplots_adjust(left=0.10, right=0.97, top=0.83, bottom=0.20)
    return fig, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="Reuse a saved match-level extraction.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    if args.csv:
        data = pd.read_csv(args.csv)
    else:
        engine = connect_database()
        try:
            with engine.connect() as connection:
                data = pd.read_sql_query(text(QUERY_PATH.read_text()), connection)
        finally:
            engine.dispose()
    fig, summary = plot_dimarco_fv(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output_dir / "dimarco-player-fv.csv", index=False)
    summary.to_csv(args.output_dir / "dimarco-player-fv-summary.csv")
    with plt.rc_context({"svg.fonttype": "none"}):
        for extension in ("png", "svg"):
            fig.savefig(args.output_dir / f"dimarco-fv-boxplots.{extension}",
                        dpi=180, facecolor="white")
    plt.close(fig)
    print(summary.to_string())
    print(f"Saved {len(data)} observations and PNG/SVG charts in {args.output_dir}")


if __name__ == "__main__":
    main()
