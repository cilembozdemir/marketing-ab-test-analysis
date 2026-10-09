"""Evaluate conversion uplift in a marketing A/B test."""

from pathlib import Path
import json
import math

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import chi2_contingency, norm


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "marketing_AB.csv.gz"
OUTPUT_DIR = ROOT / "outputs"
ALPHA = 0.05


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    data = pd.read_csv(DATA_PATH)

    if data["user_id"].duplicated().any():
        raise ValueError("Each user should appear once in this experiment.")
    if not set(data["test_group"].unique()).issubset({"ad", "psa"}):
        raise ValueError("Unexpected experiment group found.")

    summary = (
        data.groupby("test_group")["converted"]
        .agg(users="size", conversions="sum", conversion_rate="mean")
        .reset_index()
    )
    summary.to_csv(OUTPUT_DIR / "group_summary.csv", index=False)

    rates = summary.set_index("test_group")
    ad_rate = rates.loc["ad", "conversion_rate"]
    psa_rate = rates.loc["psa", "conversion_rate"]
    ad_n = rates.loc["ad", "users"]
    psa_n = rates.loc["psa", "users"]

    absolute_uplift = ad_rate - psa_rate
    relative_uplift = absolute_uplift / psa_rate
    standard_error = math.sqrt(ad_rate * (1 - ad_rate) / ad_n + psa_rate * (1 - psa_rate) / psa_n)
    critical_value = norm.ppf(1 - ALPHA / 2)
    ci_low = absolute_uplift - critical_value * standard_error
    ci_high = absolute_uplift + critical_value * standard_error

    contingency_table = pd.crosstab(data["test_group"], data["converted"])
    chi_square, p_value, _, _ = chi2_contingency(contingency_table)
    recommendation = (
        "The advertisement increased conversion and the result is statistically significant."
        if p_value < ALPHA and absolute_uplift > 0
        else "The evidence is not strong enough to recommend the advertisement based on conversion alone."
    )

    results = {
        "rows": int(len(data)),
        "ad_conversion_rate": round(float(ad_rate), 5),
        "psa_conversion_rate": round(float(psa_rate), 5),
        "absolute_uplift_percentage_points": round(float(absolute_uplift * 100), 3),
        "relative_uplift_percent": round(float(relative_uplift * 100), 2),
        "ci_95_percentage_points": [round(float(ci_low * 100), 3), round(float(ci_high * 100), 3)],
        "chi_square": round(float(chi_square), 3),
        "p_value": float(p_value),
        "incremental_conversions_per_10000": round(float(absolute_uplift * 10_000), 1),
        "recommendation": recommendation,
    }
    (OUTPUT_DIR / "results.json").write_text(json.dumps(results, indent=2))

    plot_data = summary.copy()
    plot_data["conversion_percent"] = plot_data["conversion_rate"] * 100
    sns.barplot(data=plot_data, x="test_group", y="conversion_percent", color="#4C78A8")
    plt.title("Conversion rate by experiment group")
    plt.xlabel("Experiment group")
    plt.ylabel("Conversion rate (%)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "conversion_rate.png", dpi=160)
    plt.close()

    print(summary.to_string(index=False))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
