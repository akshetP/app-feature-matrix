import io
import re
from typing import Dict, Tuple

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib_venn import venn3


# ---------- Config ----------
st.set_page_config(page_title="SSCP Feature Matrix", layout="wide")

# Rename the Excel columns to your new naming
PRODUCT_MAP = {
    "Connect": "Sunsynk Connect",
    "Connect Pro (Free)": "SSCP (Free)",
    "Connect Pro (Pro Plan)": "SSCP (Pro Plan)",
}

EXPECTED_SHEETS = ["APP", "WEB"]  # mobile + web matrices


# ---------- Helpers ----------
def _norm_cell(x: str) -> str:
    """Normalize cell values into: Y / N / PARTIAL / TBD / ''."""
    if x is None:
        return ""
    s = str(x).strip()
    if not s:
        return ""
    up = s.upper()

    # common symbols in excel
    if s in ["✔", "✅", "Y", "YES", "TRUE", "1"]:
        return "Y"
    if s in ["✖", "❌", "N", "NO", "FALSE", "0"]:
        return "N"

    # allow these to pass through
    if up in ["Y", "N", "PARTIAL", "TBD"]:
        return up

    # anything else: keep as TBD-like, but preserve original in a separate field if you want
    return up


def load_excel(uploaded_bytes: bytes, sheet_names: list = None) -> Tuple[Dict[str, pd.DataFrame], list]:
    """Load specified sheets from uploaded Excel. If sheet_names is None, load all APP/WEB sheets."""
    xl = pd.ExcelFile(io.BytesIO(uploaded_bytes))
    sheets = {}
    all_names = xl.sheet_names

    # Sheet1 (optional overview list)
    if "Sheet1" in xl.sheet_names:
        s1 = pd.read_excel(xl, sheet_name="Sheet1").fillna("")
        sheets["SUMMARY"] = s1

    # Load requested sheets (or all expected ones)
    sheets_to_load = sheet_names if sheet_names else EXPECTED_SHEETS
    for name in sheets_to_load:
        if name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=name).fillna("")
            sheets[name] = df

    return sheets, all_names


def standardize_matrix(df: pd.DataFrame, channel_label: str) -> pd.DataFrame:
    """
    Takes sheet APP/WEB with columns like:
      SECTION, FEATURE, APP/WEB, Connect, Connect Pro (Free), Connect Pro (Pro Plan)
    Returns a standard unified dataframe with:
      CHANNEL, SECTION, FEATURE, SURFACE, Sunsynk Connect, SSCP (Free), SSCP (Pro Plan)
    """
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # Identify the "surface" column name (APP or WEB)
    surface_col = None
    for c in ["APP", "WEB", "App", "Web"]:
        if c in df.columns:
            surface_col = c
            break
    if surface_col is None:
        # fallback: third column often is APP/WEB label
        surface_col = df.columns[2]

    # Ensure base cols
    for base in ["SECTION", "FEATURE"]:
        if base not in df.columns:
            raise ValueError(f"Missing required column: {base}")

    out = pd.DataFrame()
    out["SECTION"] = df["SECTION"].astype(str).str.strip()
    out["FEATURE"] = df["FEATURE"].astype(str).str.strip()
    out["SURFACE"] = df[surface_col].astype(str).str.strip()
    out["CHANNEL"] = channel_label  # Assign after other columns so length is known

    # Map product columns
    for old, new in PRODUCT_MAP.items():
        if old not in df.columns:
            out[new] = ""
        else:
            out[new] = df[old].apply(_norm_cell)

    return out


def coverage_counts(df: pd.DataFrame, col: str) -> Tuple[int, int, int, int]:
    v = df[col].astype(str).str.upper().str.strip()
    y = (v == "Y").sum()
    n = (v == "N").sum()
    p = (v == "PARTIAL").sum()
    other = (~v.isin(["Y", "N", "PARTIAL"]) & (v != "")).sum()
    return int(y), int(n), int(p), int(other)


def filter_df(df: pd.DataFrame, channel: str, sections, search: str) -> pd.DataFrame:
    f = df[df["CHANNEL"] == channel].copy()
    if sections:
        f = f[f["SECTION"].isin(sections)]
    if search.strip():
        pat = re.escape(search.strip())
        f = f[
            f["FEATURE"].str.contains(pat, case=False, na=False)
            | f["SECTION"].str.contains(pat, case=False, na=False)
        ]
    return f


# ---------- UI ----------
st.title("Feature Matrix: Sunsynk Connect vs SSCP (Mobile/Web + Pro Plan)")
st.caption("Upload the Excel and manage all 6 combinations (Mobile/Web × 3 products) in one app.")

uploaded = st.file_uploader("Upload: APP FEATURE MATRIX.xlsx", type=["xlsx"])

if not uploaded:
    st.info("Upload your Excel to begin.")
    st.stop()

# First pass: get all available sheets
temp_sheets, all_sheet_names = load_excel(uploaded.getvalue())

# Sheet selector for feature matrices (exclude Sheet1)
feature_sheets = [s for s in all_sheet_names if s in EXPECTED_SHEETS]
if len(feature_sheets) > 1:
    st.subheader("Select Sheets")
    selected_sheets = st.multiselect(
        "Choose which sheets to view:",
        options=feature_sheets,
        default=feature_sheets
    )
else:
    selected_sheets = feature_sheets

if not selected_sheets:
    st.warning("Please select at least one sheet.")
    st.stop()

st.divider()

# Reload with only selected sheets
sheets, _ = load_excel(uploaded.getvalue(), sheet_names=selected_sheets)

# Build unified dataset from selected sheets
frames = []

if "APP" in selected_sheets and "APP" in sheets:
    frames.append(standardize_matrix(sheets["APP"], channel_label="Mobile"))
if "WEB" in selected_sheets and "WEB" in sheets:
    frames.append(standardize_matrix(sheets["WEB"], channel_label="Web"))

if not frames:
    st.error(f"Could not load requested sheets. Available sheets: {all_sheet_names}")
    st.stop()

data = pd.concat(frames, ignore_index=True)

PRODUCTS = list(PRODUCT_MAP.values())  # ["Sunsynk Connect", "SSCP (Free)", "SSCP (Pro Plan)"]

# Top-level tabs
tab_matrix, tab_analytics = st.tabs(["Matrix (Mobile/Web)", "Analytics"])

def render_matrix_view(channel_label: str, key_prefix: str = ""):
    st.subheader(f"{channel_label} matrix")

    channel_data = data[data["CHANNEL"] == channel_label]
    sections = sorted([s for s in channel_data["SECTION"].unique() if str(s).strip()])

    selected_sections = st.multiselect("Sections", sections, default=sections, key=f"{key_prefix}sections")

    # Search removed for simplicity; only section filtering applied
    fdf = filter_df(data, channel=channel_label, sections=selected_sections, search="")

    # Coverage snapshot per product
    st.markdown("**Coverage summary (filtered)**")
    sum_rows = []
    for col in PRODUCTS:
        y, n, p, other = coverage_counts(fdf, col)
        sum_rows.append(
            {
                "Product": col,
                "Y": y,
                "N": n,
                "PARTIAL": p,
                "TBD/Other": other,
                "Coverage % (Y only)": (y / len(fdf) * 100.0) if len(fdf) else 0.0,
            }
        )
    st.dataframe(pd.DataFrame(sum_rows), width="stretch", hide_index=True)

    st.divider()

    st.subheader("Editable matrix")
    fdf = fdf.reset_index(drop=True)
    edited = st.data_editor(
        fdf,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "CHANNEL": st.column_config.TextColumn(disabled=True, width="small"),
            "SURFACE": st.column_config.TextColumn(disabled=True, width="small"),
            "SECTION": st.column_config.TextColumn(width="medium"),
            "FEATURE": st.column_config.TextColumn(width="large"),
            PRODUCTS[0]: st.column_config.SelectboxColumn(options=["Y", "N", "PARTIAL", "TBD", ""], width="small"),
            PRODUCTS[1]: st.column_config.SelectboxColumn(options=["Y", "N", "PARTIAL", "TBD", ""], width="small"),
            PRODUCTS[2]: st.column_config.SelectboxColumn(options=["Y", "N", "PARTIAL", "TBD", ""], width="small"),
        },
    )

    csv_bytes = edited.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV (current view)",
        data=csv_bytes,
        file_name=f"feature_matrix_{channel_label.lower()}_view.csv",
        mime="text/csv",
    )



with tab_matrix:
    tab_mob, tab_web = st.tabs(["Mobile", "Web"])
    with tab_mob:
        render_matrix_view("Mobile", key_prefix="mob_")
    with tab_web:
        render_matrix_view("Web", key_prefix="web_")

# Analytics Tab
with tab_analytics:
    st.subheader("Coverage Analytics")
    
    analytics_channel = st.selectbox("Channel for analytics", ["Mobile", "Web"], index=0, key="analytics_channel")
    analytics_data = data[data["CHANNEL"] == analytics_channel]
    
    # Coverage by Section
    st.markdown("### Coverage by Section")
    section_stats = []
    for section in sorted(analytics_data["SECTION"].unique()):
        section_df = analytics_data[analytics_data["SECTION"] == section]
        for product in PRODUCTS:
            y, n, p, o = coverage_counts(section_df, product)
            total = len(section_df)
            section_stats.append({
                "Section": section,
                "Product": product,
                "Y": y,
                "N": n,
                "PARTIAL": p,
                "Total": total,
                "Coverage %": round((y / total * 100), 1) if total else 0
            })
    
    section_df_stats = pd.DataFrame(section_stats)
    
    # Bar chart
    import plotly.express as px
    fig_bar = px.bar(
        section_df_stats,
        x="Section",
        y="Coverage %",
        color="Product",
        barmode="group",
        title=f"{analytics_channel} - Coverage % by Section",
        height=400
    )
    st.plotly_chart(fig_bar, width="stretch")
    
    # Heatmap
    st.markdown("### Feature Parity Heatmap")
    st.caption("Color-coded view: Green=Y, Red=N, Yellow=PARTIAL, Gray=TBD")
    
    heatmap_data = analytics_data[["SECTION", "FEATURE"] + PRODUCTS].copy()
    
    # Color mapping function
    def color_map(val):
        val_str = str(val).strip().upper()
        if val_str == "Y":
            return "background-color: #90EE90"  # light green
        elif val_str == "N":
            return "background-color: #FFB6C6"  # light red
        elif val_str == "PARTIAL":
            return "background-color: #FFE484"  # light yellow
        else:
            return "background-color: #E0E0E0"  # gray
    
    styled_heatmap = heatmap_data.style.map(color_map, subset=PRODUCTS)
    st.dataframe(styled_heatmap, width="stretch", hide_index=True, height=600)

    st.markdown("### Product Overlap (Venn)")
    st.caption("Based on features marked Y for each product")

    # Build feature sets per product (SECTION + FEATURE as key) for Y only
    def feature_set(df: pd.DataFrame, product: str) -> set:
        v = df[df[product].astype(str).str.upper().str.strip() == "Y"]
        return set(v["SECTION"].astype(str).str.strip() + " | " + v["FEATURE"].astype(str).str.strip())

    set_a = feature_set(analytics_data, PRODUCTS[0])
    set_b = feature_set(analytics_data, PRODUCTS[1])
    set_c = feature_set(analytics_data, PRODUCTS[2])

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        fig, ax = plt.subplots(figsize=(6, 5))
        venn3(subsets=(set_a, set_b, set_c), set_labels=(PRODUCTS[0], PRODUCTS[1], PRODUCTS[2]), ax=ax)
        st.pyplot(fig, width="stretch")

