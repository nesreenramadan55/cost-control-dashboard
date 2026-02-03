import pandas as pd
import numpy as np
import re
from pathlib import Path

# =========================
# CONFIG
# =========================
INPUT_FILE = "MCL FINAL1.xlsx"        
SHEET_NAME = "MonthlyTABLE_31"
MONTH_YEAR = "2026-1"
OUTPUT_FILE = "LBACC_JAN2026.xlsx"

ITEM_COL = "Text105"
PRICE_COL = "LISTPRICE"  
COSTPRICE_COL="COSTPRICE" 
     
ITEM_TYPE_COL="item_type"         

ROUTINE_MIN_DAYS = 20
ROUTINE_MAX_CV = 0.15
SPIKE_Z = 2.0
HIGH_COST_SHARE = 0.08


def find_day_cols(cols):
    day_cols = []
    for c in cols:
        s = str(c).strip()
        if re.fullmatch(r"(?:[1-9]|[12]\d|3[01])", s):
            day_cols.append(c)
    return sorted(day_cols, key=lambda x: int(str(x).strip()))


def to_num(s):
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", ".", regex=False)
         .str.replace(" ", "", regex=False),
        errors="coerce"
    )


def main():
    # --- load ---
    in_path = Path(INPUT_FILE)
    if not in_path.exists():
        raise FileNotFoundError(f"File not found: {INPUT_FILE}")

    df = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME)
    df.columns = [str(c).strip() for c in df.columns]
    import numpy as np
    # -----------------------------
# CATEGORY + TRANSACTIONS_LONG
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

# 1) excel row -> category
    df["excel_row"] = df.index + 2  # row 1 headers, row 2 first data
    df["category"] = "OTHER"
    df.loc[df["excel_row"].between(3, 25),   "category"] = "LBACC"
    df.loc[df["excel_row"].between(26, 170), "category"] = "LOUNGE"
    df.loc[df["excel_row"].between(171, 260),"category"] = "STORE"

# 2) day columns 1..31
    day_cols = [c for c in df.columns if str(c).strip().isdigit()]

# 3) melt -> long_df WITH category
    long_df = df.melt(
    id_vars=[ITEM_COL, PRICE_COL, COSTPRICE_COL, ITEM_TYPE_COL, "category"],
    value_vars=day_cols,
    var_name="day",
    value_name="qty")


    long_df = long_df.dropna(subset=["qty"])
    long_df["qty"] = pd.to_numeric(long_df["qty"], errors="coerce")
    long_df = long_df[long_df["qty"].fillna(0) != 0]


# Clean numeric columns
    # Clean numeric columns
    long_df["qty"] = pd.to_numeric(long_df["qty"], errors="coerce").fillna(0)

# CREATE unit_price from LISTPRICE
    long_df["unit_price"] = pd.to_numeric(long_df[PRICE_COL], errors="coerce").fillna(0)

# Safe multiplication (no index alignment issues)

    # long_df["cost"] = long_df["cost_value"]

    if "date" in long_df.columns:
        long_df = long_df.drop(columns=["date"])
    

    long_df["item"] = long_df[ITEM_COL].astype(str).str.strip()
    # Rename for clarity
    long_df.rename(columns={
    PRICE_COL: "selling_price",
    COSTPRICE_COL: "cost_price",
    ITEM_TYPE_COL: "item_type"
}, inplace=True)

# Make sure numeric
    long_df["selling_price"] = pd.to_numeric(long_df["selling_price"], errors="coerce").fillna(0)
    long_df["cost_price"] = pd.to_numeric(long_df["cost_price"], errors="coerce").fillna(0)

# Compute values
    long_df["sales_value"] = long_df["qty"].to_numpy() * long_df["selling_price"].to_numpy()
    # ==============================
    # Daily Total Sales (per day)
    # ==============================
    daily_sales = long_df.groupby("day")["sales_value"].transform("sum")
    long_df["daily_total_sales"] = daily_sales

    long_df["cost_value"]  = long_df["qty"].to_numpy() * long_df["cost_price"].to_numpy()
    long_df["profit"]      = long_df["sales_value"] - long_df["cost_value"]
# Daily total profit
    long_df["daily_total_profit"] = (
        long_df.groupby("day")["profit"]
        .transform("sum")
    )
    # cost = spending metric used by dashboard
    long_df["cost"] = long_df["cost_value"]
# optional: drop duplicate to avoid confusion in Excel
    long_df.drop(columns=["cost_value"], inplace=True)
    # If unit_price exists, it's duplicate of selling_price -> drop it
    if "unit_price" in long_df.columns:
     long_df.drop(columns=["unit_price"], inplace=True)

    print("Transactions_Long columns:", list(long_df.columns))
    print(long_df["category"].value_counts(dropna=False))

    # --- detect day cols ---

    day_cols = find_day_cols(df.columns)
    if not day_cols:
        raise ValueError("No day columns found (1..31).")

    # --- validate needed cols ---
    for col in [ITEM_COL, PRICE_COL, COSTPRICE_COL, ITEM_TYPE_COL]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}. Columns found: {list(df.columns)}")

    # --- clean ---
    df = df[[ITEM_COL, PRICE_COL, COSTPRICE_COL, ITEM_TYPE_COL] + day_cols].copy()
    df[ITEM_COL] = df[ITEM_COL].astype(str).str.strip()
    df = df[df[ITEM_COL].ne("")]

    df[PRICE_COL] = to_num(df[PRICE_COL]).fillna(0)
    df[COSTPRICE_COL] = to_num(df[COSTPRICE_COL]).fillna(0)
    df[ITEM_TYPE_COL] = df[ITEM_TYPE_COL].astype(str).str.strip().str.upper()
    for c in day_cols:
        df[c] = to_num(df[c]).fillna(0)

    
    y, m = MONTH_YEAR.split("-")
    long_df["date"] = pd.to_datetime(
        long_df["day"].astype(str).str.zfill(2).radd(f"{y}-{m}-"),
        errors="coerce"
    )

    long_df.rename(columns={ITEM_COL: "item", PRICE_COL: "unit_price"}, inplace=True)
    long_df["qty"] = long_df["qty"].fillna(0)
    # avoid pandas alignment issues when duplicates exist
    # --- FIX: remove duplicate columns (keeps the first occurrence) ---
    long_df = long_df.loc[:, ~long_df.columns.duplicated()].copy()
    long_df = long_df.reset_index(drop=True)
    
    qty_s = pd.to_numeric(long_df["qty"], errors="coerce").fillna(0)

# unit_price must be a single Series
     #unit_price_s = pd.to_numeric(long_df["unit_price"], errors="coerce").fillna(0)
    # Ensure numeric
    long_df["selling_price"] = pd.to_numeric(long_df["selling_price"], errors="coerce").fillna(0)
    long_df["cost_price"] = pd.to_numeric(long_df["cost_price"], errors="coerce").fillna(0)

# unit_price = selling_price
    long_df["unit_price"] = long_df["selling_price"]
#long_df["cost"] = long_df["cost_value"]
     # Remove duplicate column in final Excel output (same as selling_price)
    if "unit_price" in long_df.columns:
     long_df.drop(columns=["unit_price"], inplace=True)
# total cost per day
    daily_totals = long_df.groupby("date")["cost"].transform("sum")
    long_df["daily_total_cost"] = daily_totals

    # keep only ordered rows
    long_df = long_df[long_df["qty"] > 0].copy()

    # --- item stats ---
    stats = long_df.groupby("item", as_index=False).agg(
        total_qty=("qty", "sum"),
        total_cost=("cost", "sum"),
        avg_qty=("qty", "mean"),
        std_qty=("qty", "std"),
        days_ordered=("date", "nunique"),
          #unit_price=("unit_price", "max")
    )
    stats["std_qty"] = stats["std_qty"].fillna(0)
    total_cost = stats["total_cost"].sum()
    stats["cost_share"] = np.where(total_cost > 0, stats["total_cost"] / total_cost, 0.0)
    stats["cv"] = np.where(stats["avg_qty"] > 0, stats["std_qty"] / stats["avg_qty"], 0.0)
    stats = stats.sort_values("total_cost", ascending=False)

    # --- routine items ---
    routine = stats[(stats["days_ordered"] >= ROUTINE_MIN_DAYS) & (stats["cv"] <= ROUTINE_MAX_CV)].copy()
    routine["reason"] = (
    "Ordered " + routine["days_ordered"].astype(int).astype(str) +
    " days; stable qty (CV=" + routine["cv"].round(2).astype(str) + ")"
)

    # --- spike days ---
    base = long_df.groupby("item", as_index=False).agg(mu=("qty", "mean"), sigma=("qty", "std"))
    base["sigma"] = base["sigma"].fillna(0)
    mdf = long_df.merge(base, on="item", how="left")
    mdf["threshold"] = mdf["mu"] + SPIKE_Z * mdf["sigma"]
    spikes = mdf[(mdf["sigma"] > 0) & (mdf["qty"] > mdf["threshold"])].copy()
    spikes["reason"] = (
    "Spike order: " +
    spikes["qty"].round(0).astype(int).astype(str) +
    " vs normal max ~" +
    spikes["threshold"].round(1).astype(str) +
    " (+" +
    ((spikes["qty"] - spikes["threshold"]) / spikes["threshold"] * 100)
      .replace([float("inf"), -float("inf")], 0)
      .fillna(0)
      .round(0).astype(int).astype(str) +
    "%)"
)
    spikes = spikes.sort_values(["cost"], ascending=False)[["date", "item", "qty", "selling_price", "cost", "reason"]]
    spikes = spikes.sort_values(["date", "cost"], ascending=[True, False]).reset_index(drop=True)

    # --- alerts ---
    alerts = []
    for _, r in routine.iterrows():
        alerts.append({"severity": "HIGH", "type": "Routine ordering", "item": r["item"], "reason": r["reason"], "impact_cost": float(r["total_cost"])})
    hi = stats[stats["cost_share"] >= HIGH_COST_SHARE]
    for _, h in hi.iterrows():
        alerts.append({"severity": "HIGH", "type": "High cost driver", "item": h["item"], "reason": f"{h['cost_share']*100:.1f}% of monthly cost", "impact_cost": float(h["total_cost"])})
    for _, s in spikes.head(50).iterrows():
        alerts.append({"severity": "MEDIUM", "type": "Spike day", "item": s["item"], "reason": f"{s['date'].date()} {s['reason']}", "impact_cost": float(s["cost"])})

    alerts_df = pd.DataFrame(alerts)
    if alerts_df.empty:
        alerts_df = pd.DataFrame(columns=["severity", "type", "item", "reason", "impact_cost"])
    else:
        sev_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        alerts_df["rank"] = alerts_df["severity"].map(sev_rank).fillna(99).astype(int)
        alerts_df = alerts_df.sort_values(["rank", "impact_cost"], ascending=[True, False]).drop(columns=["rank"])

    # --- management summary ---
    daily = long_df.groupby("date", as_index=False).agg(total_cost=("cost", "sum"), total_qty=("qty", "sum"), n_items=("item", "nunique"))
    peak_day = ""
    peak_cost = 0.0
    if not daily.empty:
        i = daily["total_cost"].idxmax()
        peak_day = str(daily.loc[i, "date"].date())
        peak_cost = float(daily.loc[i, "total_cost"])

    summary = pd.DataFrame([{
        "monthly_total_cost": float(total_cost),
        "unique_items_ordered": int(stats.shape[0]),
        "top5_cost_share": float(stats.head(5)["total_cost"].sum() / total_cost) if total_cost > 0 else 0.0,
        "peak_day": peak_day,
        "peak_day_cost": peak_cost
    }])
   
      
    top_cost_items = stats.head(30).copy()
      
    # --- export ---
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as w:
        summary.to_excel(w, sheet_name="Management_Summary", index=False)
        alerts_df.to_excel(w, sheet_name="Alerts", index=False)
        top_cost_items.to_excel(w, sheet_name="Top_Cost_Items", index=False)
        routine.to_excel(w, sheet_name="Routine_Items", index=False)
        spikes.to_excel(w, sheet_name="Spike_Days", index=False)
        long_df.to_excel(w, sheet_name="Transactions_Long", index=False)

    

    print("✅ Done. Output:", OUTPUT_FILE)
    print("Detected day columns:", len(day_cols))
    print("Using item col:", ITEM_COL, "| price col:", PRICE_COL)


if __name__ == "__main__":
    main()