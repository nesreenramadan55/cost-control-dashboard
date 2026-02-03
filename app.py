
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
# st.cache_data.clear()
st.set_page_config(page_title="LBACC Cost Dashboard", layout="wide")
st.markdown(
    """
    <div style="text-align:left; margin-top:10px;">
        <div style="font-size:64px; font-weight:900; letter-spacing:6px; line-height:1;">
            LBACC
        </div>
        <div style="font-size:26px; font-weight:600; margin-top:6px;">
            Cost Control Dashboard
        </div>
        <div style="font-size:20px; opacity:0.8; margin-top:6px;">
            By Nesreen
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

REQUIRED_SHEETS = ["Transactions_Long"]  # minimum required
st.caption("update test")
@st.cache_data
def load_excel(uploaded_file):
    # Read only what we need (fast)
    xls = pd.ExcelFile(uploaded_file)
    sheets = xls.sheet_names

    # Ensure minimum sheet exists
    for s in REQUIRED_SHEETS:
        if s not in sheets:
            raise ValueError(f"Missing required sheet: {s}")

    tx = pd.read_excel(uploaded_file, sheet_name="Transactions_Long")

    # Optional sheets (if they exist)
    top_items = pd.read_excel(uploaded_file, sheet_name="Top_Cost_Items") if "Top_Cost_Items" in sheets else None
    alerts = pd.read_excel(uploaded_file, sheet_name="Alerts") if "Alerts" in sheets else None
    summary = pd.read_excel(uploaded_file, sheet_name="Management_Summary") if "Management_Summary" in sheets else None

    return tx, top_items, alerts, summary, sheets


def safe_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


#st.title("LBACC — Cost Control Dashboard")

uploaded = st.file_uploader("Upload the monthly output Excel (..xlsx)", type=["xlsx"])

if not uploaded:
    st.info("Upload the Excel output file to start.")
    st.stop()

try:
    tx, top_items, alerts, summary, sheet_names = load_excel(uploaded)
except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()

# --- Normalize columns ---
tx.columns = [str(c).strip() for c in tx.columns]

# --- Validate required columns in Transactions_Long ---
required_cols = ["day", "qty", "selling_price", "sales_value","cost"]
missing_cols = [c for c in required_cols if c not in tx.columns]
if missing_cols:
    st.error(f"Transactions_Long is missing columns: {missing_cols}")
    st.stop()

# Optional but recommended
if "item" not in tx.columns and "Text105" in tx.columns:
    tx["item"] = tx["Text105"].astype(str).str.strip()

if "category" not in tx.columns:
    tx["category"] = "UNKNOWN"

# --- Type cleaning ---
tx["day"] = pd.to_numeric(tx["day"], errors="coerce").astype("Int64")
tx["qty"] = safe_num(tx["qty"])
tx["selling_price"] = safe_num(tx["selling_price"])
tx["cost"] = safe_num(tx["cost"])

tx = tx.dropna(subset=["day"])
tx["day"] = tx["day"].astype(int)


# ----- Sidebar: Item Type Filter -----
st.sidebar.subheader("Item Type")

# optional: labels for nicer UI
type_labels = {
    "F": "Food (F)",
    "BEV": "Beverage (BEV)",
    "GI": "General Item (GI)"
}
TOTAL_PASSENGERS = 35488
total_passengers = "TOTAL_PASSENGERS"


# get available types in the current dataset
available_types = (
    tx["item_type"].dropna().astype(str).str.strip().unique().tolist()
)
available_types = [t for t in available_types if t != ""]
available_types = sorted(available_types)

# default = all
default_types = available_types

selected_types = st.sidebar.multiselect(
    "Filter by Item Type",
    options=available_types,
    default=default_types,
    format_func=lambda x: type_labels.get(x, x)
)
# Apply item_type filter
tx = tx[tx["item_type"].astype(str).str.strip().isin(selected_types)].copy()
# ==============
# Sidebar filters
# ==============
st.sidebar.header("Filters")

cats = sorted([c for c in tx["category"].dropna().unique()])
cat_choice = st.sidebar.selectbox("Category", ["ALL"] + cats, index=0)

day_min, day_max = int(tx["day"].min()), int(tx["day"].max())
day_range = st.sidebar.slider("Day range", day_min, day_max, (day_min, day_max))

top_n = st.sidebar.slider("Top N items", 3, 30, 15)

filtered = tx.copy()

filtered = filtered[(filtered["day"] >= day_range[0]) & (filtered["day"] <= day_range[1])]
if cat_choice != "ALL":
    filtered = filtered[filtered["category"] == cat_choice]
# NEW: item_type filter
if selected_types:
    filtered = filtered[filtered["item_type"].astype(str).str.strip().isin(selected_types)]
else:
    # if user deselects all, show nothing (or keep all if you prefer)
    filtered = filtered.iloc[0:0]

# =================
# KPI Cards (metrics)
# =================
st.subheader("Key Metrics")

# daily totals are already in the sheet (repeated per row) -> take first value per day
daily_totals = (
    filtered.groupby("day", as_index=False)
    .agg(
        daily_total_sales=("daily_total_sales", "first"),
        daily_total_cost=("daily_total_cost", "first"),
        daily_total_profit=("daily_total_profit", "first"),
    )
    .sort_values("day")
)

monthly_total = float(filtered["sales_value"].sum())
unique_items = int(filtered["item"].nunique()) if "item" in filtered.columns else 0

if len(daily_totals) > 0:
    peak_row = daily_totals.loc[daily_totals["daily_total_sales"].idxmax()]
    peak_day = int(peak_row["day"])
    peak_cost = float(peak_row["daily_total_sales"])
else:
    peak_day, peak_cost = None, 0.0

cat_cost = (
    filtered.groupby("category", as_index=False)["cost"]
    .sum()
    .sort_values("cost", ascending=False)
)
total_sales = filtered["sales_value"].sum()
sales_per_passenger = total_sales / TOTAL_PASSENGERS if TOTAL_PASSENGERS > 0 else 0
k1, k2, k3, k4, k5, k6= st.columns(6)
k1.metric("Monthly Total Value(Sales)", f"{monthly_total:,.2f}")
k2.metric("Unique items ordered", f"{unique_items:,}")
k3.metric("Peak day", "-" if peak_day is None else f"Day {peak_day}")
k4.metric("Peak day sales", f"{peak_cost:,.2f}")
k5.metric("Total Passengers" , f"{TOTAL_PASSENGERS:,}")
k6.metric ("Sales per Pass" , f"{sales_per_passenger:,.2f}")


st.divider()

COLOR_MAP = {
    "LBACC": "#142349",   
    "LOUNGE": "#23AFF0",
    "STORE": "#0B0ED4"
}
top_items_df = (
    filtered.groupby(["item", "category"], as_index=False)
    .agg(sales_value=("sales_value", "sum"))
)
#tab_overview, tab_sales_cost = st.tabs(["Overview", "Sales & Cost"])
#tab_overview, tab_sales_cost = st.tabs([
    #"Overview",
    #"Sales & Cost"
#])
#with tab_overview:
       #st.header("overview")
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select View",
    ["Overview", "Sales & Cost"],
    index=0
)


# ======================
# Chart 1: Daily Total Cost
# ======================
def render_overview(filtered, fig_alerts=None):
    st.header("Overview")
    st.subheader("Daily Total Sales Trend")
    fig1 = px.line(daily_totals, x="day", y="daily_total_sales", markers=True)
    fig1.update_layout(xaxis_title="Day", yaxis_title="Total Sales")
    st.plotly_chart(fig1, use_container_width=True, key="daily_sales_trend")
    # ================
    # second chart
    # =================
    st.subheader("Daily Sales by Category (Stacked)")

    daily_cat = (
        tx.groupby(["day", "category"], as_index=False)["sales_value"]
        .sum()
        .sort_values(["day", "category"])
    )

    # Apply same day-range filter to this view
    daily_cat = daily_cat[(daily_cat["day"] >= day_range[0]) & (daily_cat["day"] <= day_range[1])]

    if cat_choice != "ALL":
        daily_cat = daily_cat[daily_cat["category"] == cat_choice]

    fig2 = px.bar(daily_cat, x="day", y="sales_value", color="category", barmode="stack")
    fig2 = px.bar(
        daily_cat,
        x="day",
        y="sales_value",
        color="category",
        barmode="stack",
        color_discrete_map=COLOR_MAP
    )
    fig2.update_layout(xaxis_title="Day", yaxis_title="Sales Value")
    st.plotly_chart(fig2, use_container_width=True, key="daily_sales_by_cat")

    # ==========================
    # Chart 3: Monthly cost by category
    # ==========================
    cat_sales = (
        filtered.groupby("category", as_index=False)["sales_value"]
        .sum()
        .sort_values("sales_value", ascending=False)
    )
    st.subheader("Monthly Sales by Category")
    fig3 = px.bar(cat_sales, x="category", y="sales_value")
    fig3.update_layout(xaxis_title="Category", yaxis_title="Total Sales")
    st.plotly_chart(fig3, use_container_width=True, key="monthly_sales_by_cat")

    # ==========================
    # ==============================
    # Chart 4: Pareto Top Items (Sales)
    # ==============================

    st.subheader("Pareto – Top Items Contribution (80/20)")

    top_items_df = (
        filtered
        .groupby("item", as_index=False)["sales_value"]
        .sum()
        .sort_values("sales_value", ascending=False)
        .head(top_n)
    )

    if len(top_items_df) > 0:
        top_items_df["cum_pct"] = (
            top_items_df["sales_value"].cumsum()
            / top_items_df["sales_value"].sum()
            * 100
        )

        fig4 = go.Figure()

        # Bar: Sales
        fig4.add_trace(
            go.Bar(
                x=top_items_df["item"],
                y=top_items_df["sales_value"],
                name="Sales Value"
            )
        )

        # Line: Cumulative %
        fig4.add_trace(
            go.Scatter(
                x=top_items_df["item"],
                y=top_items_df["cum_pct"],
                name="Cumulative %",
                yaxis="y2",
                mode="lines+markers"
            )
        )

        fig4.update_layout(
            xaxis=dict(title="Item", tickangle=-45),
            yaxis=dict(title="Sales Value"),
            yaxis2=dict(
                title="Cumulative %",
                overlaying="y",
                side="right",
                range=[0, 110]
            ),
            legend=dict(orientation="h")
        )

        st.plotly_chart(fig4, use_container_width=True)

    else:
        st.info("No item data in the selected filter range.")

    # ==========================
    # ==============================
    # Chart 5: Top Items with Category (Sales)
    # ==============================

    st.subheader("Top Items (Colored by Category) — Sales")

    top_item_cat = (
        filtered
        .groupby(["item", "category"], as_index=False)["sales_value"]
        .sum()
        .sort_values("sales_value", ascending=False)
        .head(top_n)
    )

    fig5 = px.bar(
        top_item_cat,
        x="item",
        y="sales_value",
        color="category"
    )

    fig5.update_layout(
        xaxis_title="Item",
        yaxis_title="Sales Value",
        xaxis_tickangle=-45
    )

    fig5 = px.bar(
        top_item_cat,
        x="item",
        y="sales_value",
        color="category",
        color_discrete_map=COLOR_MAP
    )
    st.plotly_chart(fig5, use_container_width=True, key="top_items_sales_by_cat")
    st.divider()
    # ==========================
    # =========================
    # Charts (replace tables)
    # =========================

    st.subheader("Top Items")

    TOP_N = st.slider("Top N items", 3, 30, 10)

    topN = top_items_df.sort_values("sales_value", ascending=False).head(TOP_N)

    fig_top = px.bar(
        topN,
        x="sales_value",
        y="item",
        orientation="h",
        color="category" if "category" in topN.columns else None,
        text="sales_value",
        title=f"Top {TOP_N} Items"
    )

    fig_top.update_layout(yaxis={"categoryorder": "total ascending"})

    st.plotly_chart(
        fig_top,
        use_container_width=True,
        key="top_items_bar"
    )
    # =========================
    # ALERTS (SMART VERSION)
    # =========================

    st.subheader("🚨 Cost Alerts")

    if alerts is not None and len(alerts) > 0:

        # فلترة: بس الـ HIGH و أعلى تأثير
        alerts_filtered = (
            alerts
            .sort_values("impact_cost", ascending=False)
            .head(10)
        )

        fig_alerts = px.bar(
            alerts_filtered,
            x="impact_cost",
            y="item",
            color="severity",
            orientation="h",
            title="High Impact Cost Alerts",
            text="impact_cost",
            color_discrete_map={
                "HIGH": "#d62728",
                "MEDIUM": "#ff7f0e",
                "LOW": "#2ca02c"
            }
        )

        fig_alerts.update_layout(
            yaxis_title="Item",
            xaxis_title="Impact Cost",
            showlegend=True
        )

        st.plotly_chart(
            fig_alerts,
            use_container_width=True,
            key="alerts_chart"
        )

    else:
        st.success("✅ No critical alerts detected for this period.")
#with tab_sales_cost:
    #st.header("Sales & Cost Dashboard")
def render_sales_cost(filtered):
    st.header("Sales & Cost")
# ---------- KPIs ----------
    total_sales = filtered["sales_value"].sum()
    total_cost  = filtered["cost"].sum()
    cost_ratio = (total_cost / total_sales * 100) if total_sales else 0
    total_profit = filtered["profit"].sum()

    c1, c2, c3,c4 = st.columns(4)
    c1.metric("Total Sales (Revenue)", f"{total_sales:,.2f}")
    c2.metric("Total Cost (COGS)", f"{total_cost:,.2f}")
    c3.metric("Cost-to-Sales %", f"{cost_ratio:,.1f}%")
    c4.metric("Total Profit", f"{total_profit:,.2f}")
    st.divider()
        # =========================
    # Profit per Day (Trend)
    # =========================
    daily_profit = (
        filtered.groupby("day", as_index=False)
        .agg(
            sales_value=("sales_value", "sum"),
            cost=("cost", "sum"),
            profit=("profit", "sum")
        )
        .sort_values("day")
    )

    fig_profit = go.Figure()
    fig_profit.add_trace(go.Scatter(
        x=daily_profit["day"], y=daily_profit["profit"],
        mode="lines+markers", name="Profit"
    ))
    fig_profit.update_layout(
        title="Daily Profit Trend",
        xaxis_title="Day",
        yaxis_title="Profit"
    )
    st.plotly_chart(fig_profit, use_container_width=True, key="daily_profit_trend")

    # ---------- Daily Trend ----------
    daily = (filtered.groupby("day", as_index=False)
            .agg(sales_value=("sales_value", "sum"),
                cost=("cost", "sum")))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["day"], y=daily["sales_value"], mode="lines+markers", name="Sales"))
    fig.add_trace(go.Scatter(x=daily["day"], y=daily["cost"], mode="lines+markers", name="Cost"))
    fig.update_layout(title="Daily Sales vs Daily Cost", xaxis_title="Day", yaxis_title="Value")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---------- By Category ----------
    cat = (filtered.groupby("category", as_index=False)
        .agg(sales_value=("sales_value", "sum"),
                cost=("cost", "sum")))

    fig_cat = go.Figure()
    fig_cat.add_trace(go.Bar(x=cat["category"], y=cat["sales_value"], name="Sales"))
    fig_cat.add_trace(go.Bar(x=cat["category"], y=cat["cost"], name="Cost"))
    fig_cat.update_layout(title="Sales & Cost by Category", barmode="group", xaxis_title="Category", yaxis_title="Value")
    st.plotly_chart(fig_cat, use_container_width=True)

    # ---------- By Item Type (إذا موجود) ----------
    if "item_type" in filtered.columns:
        t = (filtered.groupby("item_type", as_index=False)
            .agg(sales_value=("sales_value", "sum"),
                cost=("cost", "sum")))

        fig_type = go.Figure()
        fig_type.add_trace(go.Bar(x=t["item_type"], y=t["sales_value"], name="Sales"))
        fig_type.add_trace(go.Bar(x=t["item_type"], y=t["cost"], name="Cost"))
        fig_type.update_layout(title="Sales & Cost by Item Type", barmode="group", xaxis_title="Item Type", yaxis_title="Value")
        st.plotly_chart(fig_type, use_container_width=True)

    st.divider()

    # ---------- Top Items ----------
    top_n = st.slider("Top N items", 5, 50, 15)

    top_sales = (filtered.groupby("item", as_index=False)["sales_value"]
                .sum().sort_values("sales_value", ascending=False).head(top_n))

    top_cost = (filtered.groupby("item", as_index=False)["cost"]
                .sum().sort_values("cost", ascending=False).head(top_n))

    colA, colB = st.columns(2)

    with colA:
        st.subheader("Top Items by Sales")
        fig_ts = px.bar(top_sales, x="sales_value", y="item", orientation="h")
        st.plotly_chart(fig_ts, use_container_width=True)

    with colB:
        st.subheader("Top Items by Cost")
        fig_tc = px.bar(top_cost, x="cost", y="item", orientation="h")
        st.plotly_chart(fig_tc, use_container_width=True)
if page == "Overview":
    render_overview(filtered, fig_alerts=None)
else: 
    render_sales_cost(filtered)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
# st.cache_data.clear()
st.set_page_config(page_title="LBACC Cost Dashboard", layout="wide")
st.markdown(
    """
    <div style="text-align:left; margin-top:10px;">
        <div style="font-size:64px; font-weight:900; letter-spacing:6px; line-height:1;">
            LBACC
        </div>
        <div style="font-size:26px; font-weight:600; margin-top:6px;">
            Cost Control Dashboard
        </div>
        <div style="font-size:20px; opacity:0.8; margin-top:6px;">
            By Nesreen
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

REQUIRED_SHEETS = ["Transactions_Long"]  # minimum required

@st.cache_data
def load_excel(uploaded_file):
    # Read only what we need (fast)
    xls = pd.ExcelFile(uploaded_file)
    sheets = xls.sheet_names

    # Ensure minimum sheet exists
    for s in REQUIRED_SHEETS:
        if s not in sheets:
            raise ValueError(f"Missing required sheet: {s}")

    tx = pd.read_excel(uploaded_file, sheet_name="Transactions_Long")

    # Optional sheets (if they exist)
    top_items = pd.read_excel(uploaded_file, sheet_name="Top_Cost_Items") if "Top_Cost_Items" in sheets else None
    alerts = pd.read_excel(uploaded_file, sheet_name="Alerts") if "Alerts" in sheets else None
    summary = pd.read_excel(uploaded_file, sheet_name="Management_Summary") if "Management_Summary" in sheets else None

    return tx, top_items, alerts, summary, sheets


def safe_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


#st.title("LBACC — Cost Control Dashboard")

uploaded = st.file_uploader("Upload the monthly output Excel (..xlsx)", type=["xlsx"])

if not uploaded:
    st.info("Upload the Excel output file to start.")
    st.stop()

try:
    tx, top_items, alerts, summary, sheet_names = load_excel(uploaded)
except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()

# --- Normalize columns ---
tx.columns = [str(c).strip() for c in tx.columns]

# --- Validate required columns in Transactions_Long ---
required_cols = ["day", "qty", "selling_price", "sales_value","cost"]
missing_cols = [c for c in required_cols if c not in tx.columns]
if missing_cols:
    st.error(f"Transactions_Long is missing columns: {missing_cols}")
    st.stop()

# Optional but recommended
if "item" not in tx.columns and "Text105" in tx.columns:
    tx["item"] = tx["Text105"].astype(str).str.strip()

if "category" not in tx.columns:
    tx["category"] = "UNKNOWN"

# --- Type cleaning ---
tx["day"] = pd.to_numeric(tx["day"], errors="coerce").astype("Int64")
tx["qty"] = safe_num(tx["qty"])
tx["selling_price"] = safe_num(tx["selling_price"])
tx["cost"] = safe_num(tx["cost"])

tx = tx.dropna(subset=["day"])
tx["day"] = tx["day"].astype(int)


# ----- Sidebar: Item Type Filter -----
st.sidebar.subheader("Item Type")

# optional: labels for nicer UI
type_labels = {
    "F": "Food (F)",
    "BEV": "Beverage (BEV)",
    "GI": "General Item (GI)"
}
TOTAL_PASSENGERS = 30000
total_passengers = "TOTAL_PASSENGERS"


# get available types in the current dataset
available_types = (
    tx["item_type"].dropna().astype(str).str.strip().unique().tolist()
)
available_types = [t for t in available_types if t != ""]
available_types = sorted(available_types)

# default = all
default_types = available_types

selected_types = st.sidebar.multiselect(
    "Filter by Item Type",
    options=available_types,
    default=default_types,
    format_func=lambda x: type_labels.get(x, x)
)
# Apply item_type filter
tx = tx[tx["item_type"].astype(str).str.strip().isin(selected_types)].copy()
# ==============
# Sidebar filters
# ==============
st.sidebar.header("Filters")

cats = sorted([c for c in tx["category"].dropna().unique()])
cat_choice = st.sidebar.selectbox("Category", ["ALL"] + cats, index=0)

day_min, day_max = int(tx["day"].min()), int(tx["day"].max())
day_range = st.sidebar.slider("Day range", day_min, day_max, (day_min, day_max))

top_n = st.sidebar.slider("Top N items", 3, 30, 15)

filtered = tx.copy()

filtered = filtered[(filtered["day"] >= day_range[0]) & (filtered["day"] <= day_range[1])]
if cat_choice != "ALL":
    filtered = filtered[filtered["category"] == cat_choice]
# NEW: item_type filter
if selected_types:
    filtered = filtered[filtered["item_type"].astype(str).str.strip().isin(selected_types)]
else:
    # if user deselects all, show nothing (or keep all if you prefer)
    filtered = filtered.iloc[0:0]

# =================
# KPI Cards (metrics)
# =================
st.subheader("Key Metrics")

# daily totals are already in the sheet (repeated per row) -> take first value per day
daily_totals = (
    filtered.groupby("day", as_index=False)
    .agg(
        daily_total_sales=("daily_total_sales", "first"),
        daily_total_cost=("daily_total_cost", "first"),
        daily_total_profit=("daily_total_profit", "first"),
    )
    .sort_values("day")
)

monthly_total = float(filtered["sales_value"].sum())
unique_items = int(filtered["item"].nunique()) if "item" in filtered.columns else 0

if len(daily_totals) > 0:
    peak_row = daily_totals.loc[daily_totals["daily_total_sales"].idxmax()]
    peak_day = int(peak_row["day"])
    peak_cost = float(peak_row["daily_total_sales"])
else:
    peak_day, peak_cost = None, 0.0

cat_cost = (
    filtered.groupby("category", as_index=False)["cost"]
    .sum()
    .sort_values("cost", ascending=False)
)
total_sales = filtered["sales_value"].sum()
sales_per_passenger = total_sales / TOTAL_PASSENGERS if TOTAL_PASSENGERS > 0 else 0
k1, k2, k3, k4, k5, k6= st.columns(6)
k1.metric("Monthly Total Value(Sales)", f"{monthly_total:,.2f}")
k2.metric("Unique items ordered", f"{unique_items:,}")
k3.metric("Peak day", "-" if peak_day is None else f"Day {peak_day}")
k4.metric("Peak day sales", f"{peak_cost:,.2f}")
k5.metric("Total Passengers" , f"{TOTAL_PASSENGERS:,}")
k6.metric ("Sales per Pass" , f"{sales_per_passenger:,.2f}")


st.divider()

COLOR_MAP = {
    "LBACC": "#142349",   
    "LOUNGE": "#23AFF0",
    "STORE": "#0B0ED4"
}
top_items_df = (
    filtered.groupby(["item", "category"], as_index=False)
    .agg(sales_value=("sales_value", "sum"))
)
#tab_overview, tab_sales_cost = st.tabs(["Overview", "Sales & Cost"])
#tab_overview, tab_sales_cost = st.tabs([
    #"Overview",
    #"Sales & Cost"
#])
#with tab_overview:
       #st.header("overview")
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select View",
    ["Overview", "Sales & Cost"],
    index=0
)


# ======================
# Chart 1: Daily Total Cost
# ======================
def render_overview(filtered, fig_alerts=None):
    st.header("Overview")
    st.subheader("Daily Total Sales Trend")
    fig1 = px.line(daily_totals, x="day", y="daily_total_sales", markers=True)
    fig1.update_layout(xaxis_title="Day", yaxis_title="Total Sales")
    st.plotly_chart(fig1, use_container_width=True, key="daily_sales_trend")
    # ================
    # second chart
    # =================
    st.subheader("Daily Sales by Category (Stacked)")

    daily_cat = (
        tx.groupby(["day", "category"], as_index=False)["sales_value"]
        .sum()
        .sort_values(["day", "category"])
    )

    # Apply same day-range filter to this view
    daily_cat = daily_cat[(daily_cat["day"] >= day_range[0]) & (daily_cat["day"] <= day_range[1])]

    if cat_choice != "ALL":
        daily_cat = daily_cat[daily_cat["category"] == cat_choice]

    fig2 = px.bar(daily_cat, x="day", y="sales_value", color="category", barmode="stack")
    fig2 = px.bar(
        daily_cat,
        x="day",
        y="sales_value",
        color="category",
        barmode="stack",
        color_discrete_map=COLOR_MAP
    )
    fig2.update_layout(xaxis_title="Day", yaxis_title="Sales Value")
    st.plotly_chart(fig2, use_container_width=True, key="daily_sales_by_cat")

    # ==========================
    # Chart 3: Monthly cost by category
    # ==========================
    cat_sales = (
        filtered.groupby("category", as_index=False)["sales_value"]
        .sum()
        .sort_values("sales_value", ascending=False)
    )
    st.subheader("Monthly Sales by Category")
    fig3 = px.bar(cat_sales, x="category", y="sales_value")
    fig3.update_layout(xaxis_title="Category", yaxis_title="Total Sales")
    st.plotly_chart(fig3, use_container_width=True, key="monthly_sales_by_cat")

    # ==========================
    # ==============================
    # Chart 4: Pareto Top Items (Sales)
    # ==============================

    st.subheader("Pareto – Top Items Contribution (80/20)")

    top_items_df = (
        filtered
        .groupby("item", as_index=False)["sales_value"]
        .sum()
        .sort_values("sales_value", ascending=False)
        .head(top_n)
    )

    if len(top_items_df) > 0:
        top_items_df["cum_pct"] = (
            top_items_df["sales_value"].cumsum()
            / top_items_df["sales_value"].sum()
            * 100
        )

        fig4 = go.Figure()

        # Bar: Sales
        fig4.add_trace(
            go.Bar(
                x=top_items_df["item"],
                y=top_items_df["sales_value"],
                name="Sales Value"
            )
        )

        # Line: Cumulative %
        fig4.add_trace(
            go.Scatter(
                x=top_items_df["item"],
                y=top_items_df["cum_pct"],
                name="Cumulative %",
                yaxis="y2",
                mode="lines+markers"
            )
        )

        fig4.update_layout(
            xaxis=dict(title="Item", tickangle=-45),
            yaxis=dict(title="Sales Value"),
            yaxis2=dict(
                title="Cumulative %",
                overlaying="y",
                side="right",
                range=[0, 110]
            ),
            legend=dict(orientation="h")
        )

        st.plotly_chart(fig4, use_container_width=True)

    else:
        st.info("No item data in the selected filter range.")

    # ==========================
    # ==============================
    # Chart 5: Top Items with Category (Sales)
    # ==============================

    st.subheader("Top Items (Colored by Category) — Sales")

    top_item_cat = (
        filtered
        .groupby(["item", "category"], as_index=False)["sales_value"]
        .sum()
        .sort_values("sales_value", ascending=False)
        .head(top_n)
    )

    fig5 = px.bar(
        top_item_cat,
        x="item",
        y="sales_value",
        color="category"
    )

    fig5.update_layout(
        xaxis_title="Item",
        yaxis_title="Sales Value",
        xaxis_tickangle=-45
    )

    fig5 = px.bar(
        top_item_cat,
        x="item",
        y="sales_value",
        color="category",
        color_discrete_map=COLOR_MAP
    )
    st.plotly_chart(fig5, use_container_width=True, key="top_items_sales_by_cat")
    st.divider()
    # ==========================
    # =========================
    # Charts (replace tables)
    # =========================

    st.subheader("Top Items")

    TOP_N = st.slider("Top N items", 3, 30, 10)

    topN = top_items_df.sort_values("sales_value", ascending=False).head(TOP_N)

    fig_top = px.bar(
        topN,
        x="sales_value",
        y="item",
        orientation="h",
        color="category" if "category" in topN.columns else None,
        text="sales_value",
        title=f"Top {TOP_N} Items"
    )

    fig_top.update_layout(yaxis={"categoryorder": "total ascending"})

    st.plotly_chart(
        fig_top,
        use_container_width=True,
        key="top_items_bar"
    )
    # =========================
    # ALERTS (SMART VERSION)
    # =========================

    st.subheader("🚨 Cost Alerts")

    if alerts is not None and len(alerts) > 0:

        # فلترة: بس الـ HIGH و أعلى تأثير
        alerts_filtered = (
            alerts
            .sort_values("impact_cost", ascending=False)
            .head(10)
        )

        fig_alerts = px.bar(
            alerts_filtered,
            x="impact_cost",
            y="item",
            color="severity",
            orientation="h",
            title="High Impact Cost Alerts",
            text="impact_cost",
            color_discrete_map={
                "HIGH": "#d62728",
                "MEDIUM": "#ff7f0e",
                "LOW": "#2ca02c"
            }
        )

        fig_alerts.update_layout(
            yaxis_title="Item",
            xaxis_title="Impact Cost",
            showlegend=True
        )

        st.plotly_chart(
            fig_alerts,
            use_container_width=True,
            key="alerts_chart"
        )

    else:
        st.success("✅ No critical alerts detected for this period.")
#with tab_sales_cost:
    #st.header("Sales & Cost Dashboard")
def render_sales_cost(filtered):
    st.header("Sales & Cost")
# ---------- KPIs ----------
    total_sales = filtered["sales_value"].sum()
    total_cost  = filtered["cost"].sum()
    cost_ratio = (total_cost / total_sales * 100) if total_sales else 0
    total_profit = filtered["profit"].sum()

    c1, c2, c3,c4 = st.columns(4)
    c1.metric("Total Sales (Revenue)", f"{total_sales:,.2f}")
    c2.metric("Total Cost (COGS)", f"{total_cost:,.2f}")
    c3.metric("Cost-to-Sales %", f"{cost_ratio:,.1f}%")
    c4.metric("Total Profit", f"{total_profit:,.2f}")
    st.divider()
        # =========================
    # Profit per Day (Trend)
    # =========================
    daily_profit = (
        filtered.groupby("day", as_index=False)
        .agg(
            sales_value=("sales_value", "sum"),
            cost=("cost", "sum"),
            profit=("profit", "sum")
        )
        .sort_values("day")
    )

    fig_profit = go.Figure()
    fig_profit.add_trace(go.Scatter(
        x=daily_profit["day"], y=daily_profit["profit"],
        mode="lines+markers", name="Profit"
    ))
    fig_profit.update_layout(
        title="Daily Profit Trend",
        xaxis_title="Day",
        yaxis_title="Profit"
    )
    st.plotly_chart(fig_profit, use_container_width=True, key="daily_profit_trend")

    # ---------- Daily Trend ----------
    daily = (filtered.groupby("day", as_index=False)
            .agg(sales_value=("sales_value", "sum"),
                cost=("cost", "sum")))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["day"], y=daily["sales_value"], mode="lines+markers", name="Sales"))
    fig.add_trace(go.Scatter(x=daily["day"], y=daily["cost"], mode="lines+markers", name="Cost"))
    fig.update_layout(title="Daily Sales vs Daily Cost", xaxis_title="Day", yaxis_title="Value")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---------- By Category ----------
    cat = (filtered.groupby("category", as_index=False)
        .agg(sales_value=("sales_value", "sum"),
                cost=("cost", "sum")))

    fig_cat = go.Figure()
    fig_cat.add_trace(go.Bar(x=cat["category"], y=cat["sales_value"], name="Sales"))
    fig_cat.add_trace(go.Bar(x=cat["category"], y=cat["cost"], name="Cost"))
    fig_cat.update_layout(title="Sales & Cost by Category", barmode="group", xaxis_title="Category", yaxis_title="Value")
    st.plotly_chart(fig_cat, use_container_width=True)

    # ---------- By Item Type (إذا موجود) ----------
    if "item_type" in filtered.columns:
        t = (filtered.groupby("item_type", as_index=False)
            .agg(sales_value=("sales_value", "sum"),
                cost=("cost", "sum")))

        fig_type = go.Figure()
        fig_type.add_trace(go.Bar(x=t["item_type"], y=t["sales_value"], name="Sales"))
        fig_type.add_trace(go.Bar(x=t["item_type"], y=t["cost"], name="Cost"))
        fig_type.update_layout(title="Sales & Cost by Item Type", barmode="group", xaxis_title="Item Type", yaxis_title="Value")
        st.plotly_chart(fig_type, use_container_width=True)

    st.divider()

    # ---------- Top Items ----------
    top_n = st.slider("Top N items", 5, 50, 15)

    top_sales = (filtered.groupby("item", as_index=False)["sales_value"]
                .sum().sort_values("sales_value", ascending=False).head(top_n))

    top_cost = (filtered.groupby("item", as_index=False)["cost"]
                .sum().sort_values("cost", ascending=False).head(top_n))

    colA, colB = st.columns(2)

    with colA:
        st.subheader("Top Items by Sales")
        fig_ts = px.bar(top_sales, x="sales_value", y="item", orientation="h")
        st.plotly_chart(fig_ts, use_container_width=True)

    with colB:
        st.subheader("Top Items by Cost")
        fig_tc = px.bar(top_cost, x="cost", y="item", orientation="h")
        st.plotly_chart(fig_tc, use_container_width=True)
if page == "Overview":
    render_overview(filtered, fig_alerts=None)
else: 
    render_sales_cost(filtered)

