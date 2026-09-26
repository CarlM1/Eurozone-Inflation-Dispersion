"""
Eurozone HICP Inflation Dispersion around ECB Rate Decisions
--------------------------------------------------------------
Pulls Harmonised Index of Consumer Prices (HICP) annual inflation rates
for a set of euro-area countries from the ECB Data Portal, computes the
cross-country dispersion (standard deviation) of inflation each month,
and plots it against known ECB deposit facility rate decision dates.

BEFORE RUNNING:
1. Go to https://data.ecb.europa.eu and search "HICP - Overall index,
   Annual rate of change". Select the countries you want (see COUNTRIES
   below for a suggested starting set) and the frequency (Monthly).
2. Use the page's Export panel -> "Developers" tab -> it will show you
   the exact API query URL for your selection. Copy that URL and paste
   it into API_URL below. Doing it this way (rather than hand-typing the
   SDMX series key) guarantees the codes are correct for your selection.
3. pip install pandas requests matplotlib
"""

import io
import requests
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------
# 1) CONFIG — fill this in
# ---------------------------------------------------------------------

# Built directly from the ECB Data Portal's documented API syntax (dataflow ICP,
# dimensions FREQ.REF_AREA.ADJUSTMENT.ICP_ITEM.STS_INSTITUTION.SUFFIX), verified
# against the ECB's own reference examples. Countries: Germany, France, Italy,
# Spain, Netherlands, Ireland, Portugal, Greece — a deliberate core/periphery mix.
API_URL = "https://data-api.ecb.europa.eu/service/data/ICP/M.DE+FR+IT+ES+NL+IE+PT+GR.N.000000.4.ANR?format=csvdata&startPeriod=2021-01"

# Known ECB deposit facility rate decision dates (verified 2022 - mid 2025;
# double-check anything after that on ecb.europa.eu before you rely on it,
# since more recent decisions may not be reflected here).
RATE_DECISIONS = {
    "2022-07-27": 0.00,
    "2022-09-14": 0.75,
    "2022-11-02": 1.50,
    "2022-12-21": 2.00,
    "2023-02-08": 2.50,
    "2023-03-22": 3.00,
    "2023-05-10": 3.25,
    "2023-06-21": 3.50,
    "2023-08-02": 3.75,
    "2023-09-20": 4.00,  # peak of the hiking cycle
    "2024-06-12": 3.75,  # first cut — during Carl's ECB internship window
    "2024-09-18": 3.50,
    "2024-10-23": 3.25,
    "2024-12-18": 3.00,
    "2025-02-05": 2.75,
    "2025-03-12": 2.50,
    "2025-04-23": 2.25,
    "2025-06-11": 2.00,
}

# The one decision you want to draw a vertical "before / after" line at
# for the split-comparison chart.
FOCUS_DECISION = "2024-06-12"

OUTPUT_DIR = "output"


# ---------------------------------------------------------------------
# 2) FETCH
# ---------------------------------------------------------------------

def fetch_hicp(api_url: str) -> pd.DataFrame:
    """Download the SDMX csvdata response and return a raw DataFrame."""
    resp = requests.get(api_url, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    return df


# ---------------------------------------------------------------------
# 3) CLEAN / RESHAPE
# ---------------------------------------------------------------------

def reshape_hicp(raw: pd.DataFrame) -> pd.DataFrame:
    """
    ECB csvdata responses vary slightly in column naming by dataset, so this
    looks for the columns it needs case-insensitively rather than assuming
    exact names.
    """
    cols = {c.lower(): c for c in raw.columns}
    ref_area_col = cols.get("ref_area") or cols.get("cust_breakdown") or "REF_AREA"
    time_col = cols.get("time_period") or "TIME_PERIOD"
    value_col = cols.get("obs_value") or "OBS_VALUE"

    df = raw[[ref_area_col, time_col, value_col]].copy()
    df.columns = ["country", "period", "value"]
    df["date"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    wide = df.pivot_table(index="date", columns="country", values="value")
    wide = wide.sort_index()
    return wide


# ---------------------------------------------------------------------
# 4) ANALYSE
# ---------------------------------------------------------------------

def compute_dispersion(wide: pd.DataFrame) -> pd.Series:
    """Cross-country standard deviation of YoY inflation, per month."""
    return wide.std(axis=1)


# ---------------------------------------------------------------------
# 5) PLOT
# ---------------------------------------------------------------------

def plot_trajectories(wide: pd.DataFrame, out_path: str):
    fig, ax = plt.subplots(figsize=(9, 5))
    for country in wide.columns:
        ax.plot(wide.index, wide[country], label=country, linewidth=1.4)
    ax.set_title("Eurozone HICP Inflation by Country (YoY %)")
    ax.set_ylabel("Annual inflation rate (%)")
    ax.legend(ncol=4, fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_dispersion(dispersion: pd.Series, out_path: str):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(dispersion.index, dispersion.values, color="black", linewidth=1.6)

    for date_str, rate in RATE_DECISIONS.items():
        date = pd.to_datetime(date_str)
        if date < dispersion.index.min() or date > dispersion.index.max():
            continue
        ax.axvline(date, color="tab:red", alpha=0.25, linewidth=1)

    ax.set_title("Cross-Country Dispersion of Eurozone Inflation\n(std. dev. across member states, red lines = ECB rate decisions)")
    ax.set_ylabel("Std. dev. of YoY HICP (pp)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_before_after(dispersion: pd.Series, focus_date: str, out_path: str):
    focus = pd.to_datetime(focus_date)
    before_start = focus - pd.DateOffset(months=6)
    after_end = focus + pd.DateOffset(months=6)
    before = dispersion[(dispersion.index >= before_start) & (dispersion.index < focus)].mean()
    after = dispersion[(dispersion.index >= focus) & (dispersion.index < after_end)].mean()

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.bar(["6m before", "6m after"], [before, after], color=["tab:blue", "tab:orange"])
    ax.set_title(f"Avg. Inflation Dispersion Around {focus_date}\n(first ECB rate cut)")
    ax.set_ylabel("Std. dev. of YoY HICP (pp)")
    for i, v in enumerate([before, after]):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    raw = fetch_hicp(API_URL)
    wide = reshape_hicp(raw)
    wide.to_csv(f"{OUTPUT_DIR}/hicp_by_country.csv")

    dispersion = compute_dispersion(wide)
    dispersion.to_csv(f"{OUTPUT_DIR}/dispersion.csv")

    plot_trajectories(wide, f"{OUTPUT_DIR}/1_trajectories.png")
    plot_dispersion(dispersion, f"{OUTPUT_DIR}/2_dispersion.png")
    plot_before_after(dispersion, FOCUS_DECISION, f"{OUTPUT_DIR}/3_before_after.png")

    print("Done. Charts and CSVs written to ./output/")
    print(dispersion.tail(12))


if __name__ == "__main__":
    main()
