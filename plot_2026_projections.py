#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Plotly chart generator for the 2026 Projections workbook.

Usage examples:
  - List sheets:
      python plot_2026_projections.py --file "2026 Projections (working Doc ) (version 1) (version 1).xlsx" --list-sheets
  - Inspect columns of a sheet:
      python plot_2026_projections.py --file "2026 Projections (working Doc ) (version 1) (version 1).xlsx" --sheet "Sheet1" --list-columns
  - Plot with explicit columns:
      python plot_2026_projections.py --file "2026 Projections (working Doc ) (version 1) (version 1).xlsx" --sheet "Sheet1" --x "Month" --y "Projected,Actual" --title "2026 Projection vs Actual" --output "outputs/projection_plot.html"
  - Auto-pick likely x/y:
      python plot_2026_projections.py --file "2026 Projections (working Doc ) (version 1) (version 1).xlsx" --sheet "Sheet1"
"""

import os
import sys
import argparse
from typing import List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def list_sheets(xlsx_path: str):
    xls = pd.ExcelFile(xlsx_path)
    print("Sheets:")
    for name in xls.sheet_names:
        print(f"  - {name}")


def load_sheet(xlsx_path: str, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(xlsx_path, sheet_name=sheet_name)
    except ValueError as e:
        # Try case-insensitive match
        xls = pd.ExcelFile(xlsx_path)
        candidates = {s.lower(): s for s in xls.sheet_names}
        actual = candidates.get(sheet_name.lower())
        if actual:
            return pd.read_excel(xlsx_path, sheet_name=actual)
        raise


def pick_default_axes(df: pd.DataFrame) -> tuple[str, List[str]]:
    """
    Heuristics:
      - X: prefer columns named like 'month', 'date', 'period', else first column
      - Y: all numeric columns excluding X
    """
    cols = list(df.columns)
    lower = {c.lower(): c for c in cols}
    x_candidates = ["month", "date", "period", "year", "quarter"]
    x_col = None
    for key in x_candidates:
        if key in lower:
            x_col = lower[key]
            break
    if x_col is None:
        # try contains
        for c in cols:
            lc = c.lower()
            if any(k in lc for k in x_candidates):
                x_col = c
                break
    if x_col is None and cols:
        x_col = cols[0]
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    y_cols = [c for c in num_cols if c != x_col]
    if not y_cols and len(cols) > 1:
        # Fallback: any non-x columns
        y_cols = [c for c in cols if c != x_col][:3]
    return x_col, y_cols


def ensure_output_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description="Plot 2026 Projections workbook with Plotly")
    ap.add_argument("--file", required=True, help="Path to the Excel workbook")
    ap.add_argument("--sheet", default=None, help="Sheet name to plot")
    ap.add_argument("--list-sheets", action="store_true", help="List sheet names and exit")
    ap.add_argument("--list-columns", action="store_true", help="List columns for the selected sheet and exit")
    ap.add_argument("--x", dest="x_col", default=None, help="Column for x-axis")
    ap.add_argument("--y", dest="y_cols", default=None, help="Comma-separated columns for y-axis")
    ap.add_argument("--title", default=None, help="Chart title")
    ap.add_argument("--output", default="outputs/projection_plot.html", help="Output HTML path")
    # 2026_Locations helpers
    ap.add_argument("--list-locations", action="store_true", help="List sample locations for the selected sheet and exit")
    ap.add_argument("--location", type=str, default=None, help="Filter a single Location (for 2026_Locations monthly plot)")
    ap.add_argument("--series", type=str, default="Projected_Pay,Royalty_8pct,NAF_2pct,Tech_Fee",
                    help="Monthly value series to plot for 2026_Locations (comma-separated suffixes)")
    ap.add_argument("--dashboard-2026-locations", action="store_true",
                    help="Generate a 2x2 dashboard (bar, heatmap, stacked bar, treemap) for 2026_Locations")
    ap.add_argument("--top-n", type=int, default=20, help="Top N locations for bar/heatmap in dashboard")
    ap.add_argument("--kpi-2026-locations", action="store_true",
                    help="Generate KPI dashboard: totals, broker fees, net, and new-franchisee buckets")
    ap.add_argument("--new-locations", type=str, default=None,
                    help="Comma-separated list of Location names to treat as 'new franchisee'")
    ap.add_argument("--tiers", type=int, default=4, help="Number of performance tiers (Tier 1 = top performers)")
    ap.add_argument("--tier-metric", type=str, default="Annual_Projected_Pay",
                    help="Metric to rank tiers by (e.g., Annual_Projected_Pay)")
    # Julius breakdown outputs
    ap.add_argument("--bar-collections-by-location", action="store_true",
                    help="Bar chart of collections by location (choose metric with --collections-metric)")
    ap.add_argument("--collections-metric", type=str, default="Annual_Projected_Pay",
                    help="Metric for collections bar (Annual_Projected_Pay or Annual_Net)")
    ap.add_argument("--top-n-locations", type=int, default=50, help="Top N locations for collections bar (default: 50)")
    ap.add_argument("--monthly-net-budget", action="store_true", help="Bar chart of monthly net (Projected - Royalty - NAF - Tech) across all locations")
    ap.add_argument("--executive-dashboard", action="store_true", help="Comprehensive executive dashboard with accurate financial metrics, KPIs, trends, and breakdowns")
    args = ap.parse_args()

    xlsx_path = args.file
    if not os.path.exists(xlsx_path):
        print(f"ERROR: File not found: {xlsx_path}")
        sys.exit(1)

    if args.list_sheets:
        list_sheets(xlsx_path)
        return

    # Determine sheet
    xls = pd.ExcelFile(xlsx_path)
    sheet_name = args.sheet or (xls.sheet_names[0] if xls.sheet_names else None)
    if not sheet_name:
        print("ERROR: No sheets found in workbook.")
        sys.exit(1)

    df = load_sheet(xlsx_path, sheet_name)

    # Convenience: list locations
    if args.list_locations:
        if "Location" in df.columns:
            vals = df["Location"].dropna().astype(str).unique().tolist()
            print("Sample Locations:")
            for v in vals[:25]:
                print(f"  - {v}")
            if len(vals) > 25:
                print(f"  ... and {len(vals)-25} more")
        else:
            print("No 'Location' column found in this sheet.")
        return

    if args.list_columns:
        print(f"Columns in '{sheet_name}':")
        for c in df.columns:
            print(f"  - {c}")
        return

    # Special handling: 2026_Locations monthly plot by Location
    if args.dashboard_2026_locations and "Location" in df.columns:
        # Normalize numeric columns
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        def to_num(col):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Monthly projected, royalty, naf, tech
        for m in months:
            for suf in ["Projected_Pay","Royalty_8pct","NAF_2pct","Tech_Fee"]:
                to_num(f"{m}_{suf}")
        # Annuals
        for a in ["Annual_Projected_Pay","Annual_Royalty_8pct","Annual_NAF_2pct","Annual_Tech_Fee"]:
            to_num(a)
        # If Annual_Projected_Pay missing, compute as sum of monthly projected
        if "Annual_Projected_Pay" not in df.columns or df["Annual_Projected_Pay"].isna().all():
            proj_cols = [f"{m}_Projected_Pay" for m in months if f"{m}_Projected_Pay" in df.columns]
            if proj_cols:
                df["Annual_Projected_Pay"] = df[proj_cols].sum(axis=1, skipna=True)
        # Top N locations by Annual_Projected_Pay
        top_df = df.copy()
        if "Annual_Projected_Pay" in top_df.columns:
            top_df = top_df.sort_values("Annual_Projected_Pay", ascending=False)
        top_df = top_df.head(max(1, args.top_n))
        top_locations = top_df["Location"].astype(str).tolist()
        # Figure with subplots
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"type":"xy"}, {"type":"heatmap"}],
                   [{"type":"xy"}, {"type":"domain"}]],
            subplot_titles=(
                f"Top {len(top_locations)} Annual Projected Pay (by Location)",
                "Monthly Projected Pay Heatmap (Top Locations)",
                "Monthly Totals: Royalty vs NAF vs Tech Fee",
                "Annual Projected by State (Treemap)"
            )
        )
        # (1) Bar: Annual_Projected_Pay by Location
        if "Annual_Projected_Pay" in top_df.columns:
            fig.add_trace(
                go.Bar(x=top_df["Location"].astype(str), y=top_df["Annual_Projected_Pay"], name="Annual Projected"),
                row=1, col=1
            )
        # (2) Heatmap: monthly Projected_Pay for top locations
        heatmat = []
        for loc in top_locations:
            row = df[df["Location"].astype(str) == loc].head(1)
            vals = []
            for m in months:
                col = f"{m}_Projected_Pay"
                vals.append(pd.to_numeric(row[col], errors="coerce").iloc[0] if col in row.columns else None)
            heatmat.append(vals)
        fig.add_trace(
            go.Heatmap(
                z=heatmat,
                x=months,
                y=top_locations,
                coloraxis="coloraxis"
            ),
            row=1, col=2
        )
        fig.update_layout(coloraxis=dict(colorscale="Blues"))
        # (3) Stacked Bar: monthly totals across all locations
        totals = { "Royalty_8pct": [], "NAF_2pct": [], "Tech_Fee": [] }
        for m in months:
            for key, suf in [("Royalty_8pct","Royalty_8pct"), ("NAF_2pct","NAF_2pct"), ("Tech_Fee","Tech_Fee")]:
                col = f"{m}_{suf}"
                if col in df.columns:
                    totals[key].append(pd.to_numeric(df[col], errors="coerce").sum(skipna=True))
                else:
                    totals[key].append(0)
        fig.add_trace(go.Bar(x=months, y=totals["Royalty_8pct"], name="Royalty 8%"), row=2, col=1)
        fig.add_trace(go.Bar(x=months, y=totals["NAF_2pct"], name="NAF 2%"), row=2, col=1)
        fig.add_trace(go.Bar(x=months, y=totals["Tech_Fee"], name="Tech Fee"), row=2, col=1)
        # (4) Treemap by State
        state_vals = df.groupby("State", dropna=False)["Annual_Projected_Pay"].sum(min_count=1).reset_index()
        state_vals["State"] = state_vals["State"].fillna("Unknown").astype(str)
        state_vals["Annual_Projected_Pay"] = pd.to_numeric(state_vals["Annual_Projected_Pay"], errors="coerce").fillna(0)
        fig.add_trace(
            go.Treemap(
                labels=state_vals["State"],
                parents=[""] * len(state_vals),
                values=state_vals["Annual_Projected_Pay"],
                branchvalues="total",
                name="States"
            ),
            row=2, col=2
        )
        fig.update_layout(
            title_text=args.title or "2026 Locations Dashboard",
            barmode="stack",
            height=900
        )
        out = args.output if args.output else "outputs/plots/2026_locations_dashboard.html"
        # If output points to default single-plot path, override to dashboard default
        if out == "outputs/projection_plot.html":
            out = "outputs/plots/2026_locations_dashboard.html"
        ensure_output_dir(out)
        fig.write_html(out, include_plotlyjs="cdn", full_html=True)
        print(f"SUCCESS: Dashboard saved to {out}")
        return

    # KPI dashboard for 2026_Locations
    if args.kpi_2026_locations and "Location" in df.columns:
        # Ensure numeric totals exist
        for c in ["Annual_Projected_Pay","Annual_Royalty_8pct","Annual_NAF_2pct","Annual_Tech_Fee"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        def compute_totals(frame: pd.DataFrame) -> dict:
            total_proj = pd.to_numeric(frame.get("Annual_Projected_Pay"), errors="coerce").sum(skipna=True) if "Annual_Projected_Pay" in frame else 0
            total_roy = pd.to_numeric(frame.get("Annual_Royalty_8pct"), errors="coerce").sum(skipna=True) if "Annual_Royalty_8pct" in frame else 0
            total_naf = pd.to_numeric(frame.get("Annual_NAF_2pct"), errors="coerce").sum(skipna=True) if "Annual_NAF_2pct" in frame else 0
            total_tech = pd.to_numeric(frame.get("Annual_Tech_Fee"), errors="coerce").sum(skipna=True) if "Annual_Tech_Fee" in frame else 0
            broker = total_roy + total_naf + total_tech
            net = total_proj - broker
            return {
                "expected": float(total_proj or 0),
                "broker": float(broker or 0),
                "net": float(net or 0),
                "royalty": float(total_roy or 0),
                "naf": float(total_naf or 0),
                "tech": float(total_tech or 0),
            }
        totals_all = compute_totals(df)
        new_set = []
        if args.new_locations:
            wanted = [s.strip() for s in args.new_locations.split(",") if s.strip()]
            if wanted:
                new_set = df[df["Location"].astype(str).isin(wanted)].copy()
        totals_new = compute_totals(new_set) if len(new_set) > 0 else {"royalty":0,"naf":0,"tech":0,"expected":0,"broker":0,"net":0}
        # Build figure with indicators, grouped bars, and tier averages
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"type":"domain"}, {"type":"domain"}],
                   [{"type":"xy"}, {"type":"xy"}]],
            subplot_titles=("Total Expected Collections", "Total Broker Fees", "Net Collections and Buckets", "Avg Collections by Tier")
        )
        # Indicators
        fig.add_trace(go.Indicator(mode="number", value=totals_all["expected"], number={"valueformat": ",.0f"}, title={"text":"Expected"}), row=1, col=1)
        fig.add_trace(go.Indicator(mode="number", value=totals_all["broker"], number={"valueformat": ",.0f"}, title={"text":"Broker Fees (Royalty+NAF+Tech)"}), row=1, col=2)
        # Grouped bars for net and buckets
        categories = ["Net Collections","Royalty 8%","NAF 2%","Tech Fee"]
        all_vals = [totals_all["net"], totals_all["royalty"], totals_all["naf"], totals_all["tech"]]
        fig.add_trace(go.Bar(x=categories, y=all_vals, name="All Locations"), row=2, col=1)
        if len(new_set) > 0:
            new_vals = [totals_new["net"], totals_new["royalty"], totals_new["naf"], totals_new["tech"]]
            fig.add_trace(go.Bar(x=categories, y=new_vals, name="New Franchisee"))
        # Tiering (Tier 1 = top performers)
        tier_metric = args.tier_metric if args.tier_metric in df.columns else "Annual_Projected_Pay"
        if tier_metric not in df.columns and "Annual_Projected_Pay" not in df.columns:
            # Attempt to synthesize Annual_Projected_Pay from monthly columns
            months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            proj_cols = [f"{m}_Projected_Pay" for m in months if f"{m}_Projected_Pay" in df.columns]
            if proj_cols:
                df["Annual_Projected_Pay"] = pd.to_numeric(df[proj_cols].sum(axis=1, skipna=True), errors="coerce")
        if tier_metric not in df.columns:
            tier_metric = "Annual_Projected_Pay"
        base_cols = ["Location", "Annual_Projected_Pay","Annual_Royalty_8pct","Annual_NAF_2pct","Annual_Tech_Fee"]
        cols = base_cols.copy()
        if tier_metric not in cols:
            cols.insert(1, tier_metric)
        existing = [c for c in cols if c in df.columns]
        df_rank = df[existing].copy()
        for c in ["Annual_Projected_Pay","Annual_Royalty_8pct","Annual_NAF_2pct","Annual_Tech_Fee", tier_metric]:
            if c in df_rank.columns:
                df_rank[c] = pd.to_numeric(df_rank[c], errors="coerce")
        df_rank = df_rank.dropna(subset=[tier_metric]).sort_values(tier_metric, ascending=False).reset_index(drop=True)
        n = len(df_rank)
        tiers = max(1, int(args.tiers))
        if n > 0:
            # Assign equal-count buckets with Tier 1 highest performers
            import math
            bucket_size = math.ceil(n / tiers)
            df_rank["Tier"] = (df_rank.index // bucket_size) + 1
            df_rank.loc[df_rank["Tier"] > tiers, "Tier"] = tiers
            # Compute averages per tier (collections and buckets)
            grp = df_rank.groupby("Tier", as_index=False).agg({
                "Annual_Projected_Pay": "mean",
                "Annual_Royalty_8pct": "mean",
                "Annual_NAF_2pct": "mean",
                "Annual_Tech_Fee": "mean"
            })
            grp = grp.sort_values("Tier")
            # Plot average collections by tier
            fig.add_trace(
                go.Bar(
                    x=[f"Tier {int(t)}" for t in grp["Tier"]],
                    y=grp["Annual_Projected_Pay"],
                    name="Avg Expected Collections"
                ),
                row=2, col=2
            )
        fig.update_layout(barmode="group", height=800, title_text=args.title or "2026 Locations - KPI Overview")
        out = args.output if args.output else "outputs/plots/2026_locations_kpis.html"
        ensure_output_dir(out)
        fig.write_html(out, include_plotlyjs="cdn")
        print(f"SUCCESS: KPI dashboard saved to {out}")
        return

    # Collections by location (bar)
    if args.bar_collections_by_location and "Location" in df.columns:
        # Ensure numeric present
        for c in ["Annual_Projected_Pay","Annual_Royalty_8pct","Annual_NAF_2pct","Annual_Tech_Fee"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        metric = args.collections_metric
        if metric == "Annual_Net":
            # synthesize Annual_Net
            if all(c in df.columns for c in ["Annual_Projected_Pay","Annual_Royalty_8pct","Annual_NAF_2pct","Annual_Tech_Fee"]):
                df["Annual_Net"] = (
                    pd.to_numeric(df["Annual_Projected_Pay"], errors="coerce")
                    - pd.to_numeric(df["Annual_Royalty_8pct"], errors="coerce")
                    - pd.to_numeric(df["Annual_NAF_2pct"], errors="coerce")
                    - pd.to_numeric(df["Annual_Tech_Fee"], errors="coerce")
                )
            else:
                # fallback to projected if not all components exist
                df["Annual_Net"] = pd.to_numeric(df.get("Annual_Projected_Pay", 0), errors="coerce")
        elif metric not in df.columns:
            metric = "Annual_Projected_Pay"
        # Sort and top N
        sdf = df[["Location", metric]].copy()
        sdf[metric] = pd.to_numeric(sdf[metric], errors="coerce")
        sdf = sdf.dropna(subset=[metric]).sort_values(metric, ascending=False).head(max(1, args.top_n_locations))
        fig = px.bar(sdf, x="Location", y=metric, title=args.title or f"Collections by Location ({metric})")
        fig.update_layout(xaxis_tickangle=-45)
        out = args.output if args.output else f"outputs/plots/collections_by_location_{metric}.html"
        ensure_output_dir(out)
        fig.write_html(out, include_plotlyjs="cdn")
        print(f"SUCCESS: Collections bar saved to {out}")
        return

    # Monthly net budget (bar): sum over all locations of (Projected - Royalty - NAF - Tech)
    if args.monthly_net_budget and "Location" in df.columns:
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        def num(col):
            return pd.to_numeric(df.get(col, 0), errors="coerce")
        nets = []
        for m in months:
            proj = num(f"{m}_Projected_Pay")
            roy  = num(f"{m}_Royalty_8pct")
            naf  = num(f"{m}_NAF_2pct")
            tech = num(f"{m}_Tech_Fee")
            nets.append((proj - roy - naf - tech).sum(skipna=True))
        budget_df = pd.DataFrame({"Month": months, "Monthly_Net": nets})
        fig = px.bar(budget_df, x="Month", y="Monthly_Net", title=args.title or "Annual Budget by Month (Net After Broker Fees)")
        out = args.output if args.output else "outputs/plots/monthly_net_budget.html"
        ensure_output_dir(out)
        fig.write_html(out, include_plotlyjs="cdn")
        print(f"SUCCESS: Monthly net budget saved to {out}")
        return

    # Comprehensive Executive Dashboard - Uses Table 1 (green totals), Table 2 (Monthly Breakdown), Table 3 (2025 YTD for growth)
    if args.executive_dashboard and "Location" in df.columns:
        # Read raw data to get Table 1 (green totals row) and Table 2 (Monthly Breakdown)
        df_raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None)
        
        # Table 1: Green totals row (row 136 in Excel, 0-indexed = 135, but we read from df which has header)
        # This row contains: Annual_Projected_Pay (franchisee collections), Annual_Royalty_8pct, Annual_NAF_2pct, Annual_Tech_Fee
        # Franchisor Revenue = Royalty + NAF + Tech (these are the 3 buckets of cashflow)
        table1_row = df.iloc[134]  # Row 135 in the dataframe (green totals row)
        franchisee_collections = float(pd.to_numeric(table1_row.get("Annual_Projected_Pay", 0), errors="coerce") or 0)
        franchisor_royalty = float(pd.to_numeric(table1_row.get("Annual_Royalty_8pct", 0), errors="coerce") or 0)
        franchisor_naf = float(pd.to_numeric(table1_row.get("Annual_NAF_2pct", 0), errors="coerce") or 0)
        franchisor_tech = float(pd.to_numeric(table1_row.get("Annual_Tech_Fee", 0), errors="coerce") or 0)
        franchisor_revenue = franchisor_royalty + franchisor_naf + franchisor_tech
        
        # Table 2: Monthly Breakdown (rows 143-154 in Excel, 0-indexed = 142-153)
        # Column 0: Month name, Column 2: Total (Accured), Column 6: Total Franchisor intake, Column 7: Broker Fee, Column 8: Net Totaal
        monthly_data = []
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for idx, row_idx in enumerate(range(142, 154)):  # Rows 143-154 in Excel (0-indexed: 142-153)
            row = df_raw.iloc[row_idx]
            month_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else month_names[idx]
            total_accrued = float(pd.to_numeric(row.iloc[2], errors="coerce") or 0)
            total_franchisor = float(pd.to_numeric(row.iloc[6], errors="coerce") or 0)
            broker_fee = float(pd.to_numeric(row.iloc[7], errors="coerce") or 0)
            net_total = float(pd.to_numeric(row.iloc[8], errors="coerce") or 0)
            monthly_data.append({
                "Month": month_names[idx],
                "Total_Accrued": total_accrued,
                "Total_Franchisor_Intake": total_franchisor,
                "Broker_Fee": broker_fee,
                "Net_Total": net_total
            })
        
        # Table 3: 2025 YTD Payments for growth rate calculation (Franchisee Cash Collections)
        # Use the actual totals from user's data: 2024 = $7,019,392 (57 Zee), 2025 = $16,096,354 (82 Zee)
        franchisee_collections_2024 = 7019392.0  # 2024 TOTAL Payments (57 Zee)
        franchisee_collections_2025 = 16096354.0  # 2025 TOTAL Payments (82 Zee)
        franchisee_collections_2026 = 31700000.0  # 2026 Expected Collections ($31.7M)
        
        # Actual growth multiplier 2024->2025: 16,096,354 / 7,019,392 = 2.29
        growth_multiplier_2025 = franchisee_collections_2025 / franchisee_collections_2024
        growth_rate_pct_2025 = (growth_multiplier_2025 - 1) * 100  # (2.29 - 1) * 100 = 129%
        
        # Expected growth multiplier 2025->2026: 31,700,000 / 16,096,354 = 1.97
        growth_multiplier_2026 = franchisee_collections_2026 / franchisee_collections_2025
        expected_growth_rate_pct = (growth_multiplier_2026 - 1) * 100  # Expected growth rate for 2026
        
        # For 2025 annualized projection, use the growth multiplier
        annualized_2025 = franchisee_collections_2024 * growth_multiplier_2025
        
        monthly_df = pd.DataFrame(monthly_data)
        
        # Table 2 totals (from Total RNT row)
        table2_total_franchisor = float(monthly_df["Total_Franchisor_Intake"].sum())
        table2_total_broker_fees = float(monthly_df["Broker_Fee"].sum())
        table2_net_cashflow = float(monthly_df["Net_Total"].sum())
        
        # Correct understanding:
        # - Franchisee Collections (Table 1) = what franchisees collect from customers
        # - Franchisor Revenue (Table 1) = Royalty 8% + NAF 2% + Tech Fee = our cashflow from existing franchisees
        # - Table 2 = Monthly projections including new franchise sales
        # - Broker Fees (Table 2) = from new franchise sales (60% of territory sales)
        # - Net Cashflow = Total Franchisor Intake - Broker Fees
        
        # New franchisee breakdown (if specified)
        new_locations = []
        if args.new_locations:
            wanted = [s.strip() for s in args.new_locations.split(",") if s.strip()]
            new_locations = df[df["Location"].astype(str).isin(wanted)].copy() if wanted else pd.DataFrame()
        
        new_expected = float(new_locations["Annual_Projected_Pay"].sum()) if len(new_locations) > 0 and "Annual_Projected_Pay" in new_locations.columns else 0
        new_royalty = float(new_locations["Annual_Royalty_8pct"].sum()) if len(new_locations) > 0 and "Annual_Royalty_8pct" in new_locations.columns else 0
        new_naf = float(new_locations["Annual_NAF_2pct"].sum()) if len(new_locations) > 0 and "Annual_NAF_2pct" in new_locations.columns else 0
        new_tech = float(new_locations["Annual_Tech_Fee"].sum()) if len(new_locations) > 0 and "Annual_Tech_Fee" in new_locations.columns else 0
        new_broker = new_royalty + new_naf + new_tech
        new_net = new_expected - new_broker
        
        # Tier analysis (Tier 1 = top performers)
        tier_metric = args.tier_metric if args.tier_metric in df.columns else "Annual_Projected_Pay"
        df_tier = df[["Location", "Annual_Projected_Pay", "Annual_Royalty_8pct", "Annual_NAF_2pct", "Annual_Tech_Fee"]].copy()
        df_tier = df_tier.dropna(subset=["Annual_Projected_Pay"]).sort_values("Annual_Projected_Pay", ascending=False).reset_index(drop=True)
        n = len(df_tier)
        tiers = max(1, int(args.tiers))
        import math
        bucket_size = math.ceil(n / tiers) if n > 0 else 1
        df_tier["Tier"] = (df_tier.index // bucket_size) + 1
        df_tier.loc[df_tier["Tier"] > tiers, "Tier"] = tiers
        
        tier_avgs = df_tier.groupby("Tier", as_index=False).agg({
            "Annual_Projected_Pay": "mean",
            "Annual_Royalty_8pct": "mean",
            "Annual_NAF_2pct": "mean",
            "Annual_Tech_Fee": "mean"
        }).sort_values("Tier")
        
        # Use Table 2 monthly data (already calculated with 40% organic growth assumption)
        months = monthly_df["Month"].tolist()
        monthly_nets = monthly_df["Net_Total"].tolist()
        monthly_franchisor = monthly_df["Total_Franchisor_Intake"].tolist()
        monthly_broker = monthly_df["Broker_Fee"].tolist()
        
        # Top 20 and Bottom 10 locations for bar chart - exclude totals row, NaN locations, and new locations
        df_locations = df[df["Location"].notna() & (df["Location"].astype(str).str.strip() != "")].copy()
        df_locations["Annual_Projected_Pay"] = pd.to_numeric(df_locations["Annual_Projected_Pay"], errors="coerce")
        df_locations = df_locations.dropna(subset=["Annual_Projected_Pay"])
        
        # Exclude new locations if specified
        if args.new_locations:
            new_location_list = [s.strip() for s in args.new_locations.split(",") if s.strip()]
            df_locations = df_locations[~df_locations["Location"].astype(str).isin(new_location_list)]
        
        # Get top 20 and bottom 10 (excluding new locations)
        top_20 = df_locations.nlargest(20, "Annual_Projected_Pay")[["Location", "Annual_Projected_Pay"]].copy()
        bottom_10 = df_locations.nsmallest(10, "Annual_Projected_Pay")[["Location", "Annual_Projected_Pay"]].copy()
        
        # Combine and sort for display (top first, then bottom)
        top_20 = top_20.sort_values("Annual_Projected_Pay", ascending=True)
        bottom_10 = bottom_10.sort_values("Annual_Projected_Pay", ascending=True)
        
        # Create combined list with labels
        top_20["Label"] = top_20["Location"]
        bottom_10["Label"] = bottom_10["Location"] + " (Bottom 10)"
        
        # Combine for display
        combined_locs = pd.concat([
            top_20[["Label", "Annual_Projected_Pay"]],
            bottom_10[["Label", "Annual_Projected_Pay"]]
        ], ignore_index=True)
        
        top_locs = combined_locs
        
        # State breakdown
        state_totals = df.groupby("State", dropna=False).agg({
            "Annual_Projected_Pay": "sum",
            "Annual_Royalty_8pct": "sum",
            "Annual_NAF_2pct": "sum",
            "Annual_Tech_Fee": "sum"
        }).reset_index()
        state_totals["Net"] = state_totals["Annual_Projected_Pay"] - state_totals["Annual_Royalty_8pct"] - state_totals["Annual_NAF_2pct"] - state_totals["Annual_Tech_Fee"]
        state_totals = state_totals.sort_values("Annual_Projected_Pay", ascending=False).head(15)
        
        # Create comprehensive dashboard with subplots (3x3 grid)
        fig = make_subplots(
            rows=3, cols=3,
            specs=[[{"type":"indicator"}, {"type":"indicator"}, {"type":"indicator"}],
                   [{"type":"xy"}, {"type":"xy"}, {"type":"pie"}],
                   [{"type":"xy"}, {"type":"xy"}, {"type":"xy"}]],
            subplot_titles=(
                "Franchisee Collections<br><sub>Table 1: Total Pay</sub>", 
                "Franchisor Revenue<br><sub>Table 1: Royalty + NAF + Tech</sub>", 
                "Net Cashflow<br><sub>Table 2: After Broker Fees</sub>",
                "Monthly Net Cashflow (Table 2)<br><sub>After Broker Fees</sub>", 
                "Top 20 & Bottom 10 Locations<br><sub>Excluding New Locations</sub>", 
                "Franchisor Revenue Breakdown<br><sub>Table 1: 3 Cashflow Buckets</sub>",
                "Average Collections by Tier", 
                "Monthly Franchisor Intake vs Net", 
                "Franchisee Cash Collections<br><sub>2024, 2025, 2026 Expected</sub>"
            ),
            vertical_spacing=0.22,
            horizontal_spacing=0.15
        )
        
        # Row 1: KPI Indicators
        fig.add_trace(go.Indicator(
            mode="number",
            value=franchisee_collections,
            number={"valueformat": ",.0f", "prefix": "$"},
            title={"text": "Franchisee Collections<br><sub>Table 1: Total Pay</sub>"}
        ), row=1, col=1)
        
        fig.add_trace(go.Indicator(
            mode="number",
            value=franchisor_revenue,
            number={"valueformat": ",.0f", "prefix": "$"},
            title={"text": "Franchisor Revenue<br><sub>Table 1: Royalty + NAF + Tech</sub>"}
        ), row=1, col=2)
        
        fig.add_trace(go.Indicator(
            mode="number",
            value=table2_net_cashflow,
            number={"valueformat": ",.0f", "prefix": "$"},
            title={"text": "Net Cashflow<br><sub>Table 2: After Broker Fees</sub>"}
        ), row=1, col=3)
        
        # Row 2: Monthly Net Budget (from Table 2)
        fig.add_trace(go.Bar(
            x=months,
            y=monthly_nets,
            name="Monthly Net (Table 2)",
            marker_color="steelblue",
            text=[f"${v/1000:.0f}K" if v >= 1000 else f"${v:,.0f}" for v in monthly_nets],
            textposition="outside",
            textfont=dict(size=9)
        ), row=2, col=1)
        
        # Row 2: Top 20 and Bottom 10 Locations Bar - show full location names
        top_locs_display = top_locs.copy()
        
        # Determine colors: green for top 20, orange for bottom 10
        colors = ["darkgreen" if "(Bottom 10)" not in str(label) else "orange" 
                  for label in top_locs_display["Label"]]
        
        fig.add_trace(go.Bar(
            x=top_locs_display["Annual_Projected_Pay"],
            y=top_locs_display["Label"],
            orientation="h",
            name="Collections",
            marker_color=colors,
            text=[f"${v:,.0f}" for v in top_locs_display["Annual_Projected_Pay"]],
            textposition="outside",
            textfont=dict(size=9),
            hovertemplate="<b>%{y}</b><br>Collections: $%{x:,.0f}<extra></extra>"
        ), row=2, col=2)
        
        # Row 2: Franchisor Revenue Breakdown (pie) - from Table 1
        fig.add_trace(go.Pie(
            labels=["Royalty 8%", "NAF 2%", "Tech Fee"],
            values=[franchisor_royalty, franchisor_naf, franchisor_tech],
            hole=0.4,
            textinfo="label+percent+value",
            texttemplate="%{label}<br>$%{value:,.0f}<br>(%{percent})"
        ), row=2, col=3)
        
        # Row 3: Tier Averages
        fig.add_trace(go.Bar(
            x=[f"Tier {int(t)}" for t in tier_avgs["Tier"]],
            y=tier_avgs["Annual_Projected_Pay"],
            name="Avg Collections",
            marker_color="coral",
            text=[f"${v/1000:.0f}K" if v >= 1000 else f"${v:,.0f}" for v in tier_avgs["Annual_Projected_Pay"]],
            textposition="outside",
            textfont=dict(size=10)
        ), row=3, col=1)
        
        # Row 3: Monthly Franchisor Intake vs Net (Table 2)
        fig.add_trace(go.Bar(
            x=months,
            y=monthly_franchisor,
            name="Franchisor Intake",
            marker_color="darkgreen",
            text=[f"${v/1000:.0f}K" if v >= 1000 else f"${v:,.0f}" for v in monthly_franchisor],
            textposition="outside",
            textfont=dict(size=9)
        ), row=3, col=2)
        fig.add_trace(go.Bar(
            x=months,
            y=monthly_nets,
            name="Net After Broker Fees",
            marker_color="steelblue",
            text=[f"${v/1000:.0f}K" if v >= 1000 else f"${v:,.0f}" for v in monthly_nets],
            textposition="outside",
            textfont=dict(size=9)
        ), row=3, col=2)
        
        # Row 3: Franchisee Cash Collections - 2024, 2025, 2026 Expected
        growth_labels = ["2024 YTD", "2025 YTD", "2026 Expected"]
        growth_values = [
            franchisee_collections_2024,
            franchisee_collections_2025,
            franchisee_collections_2026
        ]
        growth_text = [
            f"${franchisee_collections_2024/1000000:.1f}M" if franchisee_collections_2024 >= 1000000 else f"${franchisee_collections_2024/1000:.0f}K",
            f"${franchisee_collections_2025/1000000:.1f}M" if franchisee_collections_2025 >= 1000000 else f"${franchisee_collections_2025/1000:.0f}K",
            f"${franchisee_collections_2026/1000000:.1f}M" if franchisee_collections_2026 >= 1000000 else f"${franchisee_collections_2026/1000:.0f}K"
        ]
        fig.add_trace(go.Bar(
            x=growth_labels,
            y=growth_values,
            name="Franchisee Cash Collections",
            marker_color=["blue", "green", "purple"],
            text=growth_text,
            textposition="outside",
            textfont=dict(size=10)
        ), row=3, col=3)
        
        # Add expected growth rate as annotation (smaller, positioned to avoid overlap)
        fig.add_annotation(
            text=f"<b>Growth 2025->2026:</b><br>{expected_growth_rate_pct:.1f}% ({growth_multiplier_2026:.2f}x)",
            xref="x domain",
            yref="y domain",
            x=0.98,
            y=0.05,
            xanchor="right",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="gray",
            borderwidth=1,
            borderpad=3,
            showarrow=False,
            font=dict(size=8, family="Arial, sans-serif"),
            row=3, col=3
        )
        
        # Update layout with improved fonts and spacing
        fig.update_layout(
            title_text=args.title or "2026 Executive Dashboard - Financial Projections",
            title_font=dict(size=24, family="Arial, sans-serif"),
            height=2000,
            showlegend=True,
            barmode="group",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5,
                font=dict(size=12)
            ),
            font=dict(size=12, family="Arial, sans-serif"),
            margin=dict(l=100, r=100, t=100, b=150)
        )
        
        # Update all subplot titles with larger fonts
        for annotation in fig.layout.annotations:
            annotation.font.size = 14
            annotation.font.family = "Arial, sans-serif"
        
        # Update axes with better fonts and tick angles
        fig.update_xaxes(
            title_text="Month",
            title_font=dict(size=13),
            tickfont=dict(size=11),
            tickangle=-45,
            row=2, col=1
        )
        fig.update_yaxes(
            title_text="Net Collections ($)",
            title_font=dict(size=13),
            tickfont=dict(size=11),
            row=2, col=1
        )
        fig.update_xaxes(
            title_text="Collections ($)",
            title_font=dict(size=13),
            tickfont=dict(size=10),
            row=2, col=2
        )
        fig.update_yaxes(
            title_text="Location",
            title_font=dict(size=13),
            tickfont=dict(size=10),
            row=2, col=2,
            automargin=True,
            side="right"
        )
        fig.update_xaxes(
            title_text="Tier",
            title_font=dict(size=13),
            tickfont=dict(size=12),
            row=3, col=1
        )
        fig.update_yaxes(
            title_text="Avg Collections ($)",
            title_font=dict(size=13),
            tickfont=dict(size=11),
            row=3, col=1
        )
        fig.update_xaxes(
            title_text="Month",
            title_font=dict(size=13),
            tickfont=dict(size=10),
            tickangle=-45,
            row=3, col=2
        )
        fig.update_yaxes(
            title_text="Amount ($)",
            title_font=dict(size=13),
            tickfont=dict(size=11),
            row=3, col=2
        )
        fig.update_xaxes(
            title_text="Period",
            title_font=dict(size=13),
            tickfont=dict(size=11),
            tickangle=-30,
            row=3, col=3
        )
        fig.update_yaxes(
            title_text="Amount ($)",
            title_font=dict(size=13),
            tickfont=dict(size=11),
            row=3, col=3
        )
        
        # Update remaining bar traces with consistent text formatting
        fig.update_traces(
            textfont=dict(size=9),
            textposition="auto",
            selector=dict(type="bar", textposition="outside")
        )
        
        # Update pie chart text
        fig.update_traces(
            textfont=dict(size=11),
            selector=dict(type="pie")
        )
        
        # Update indicator fonts
        fig.update_traces(
            number_font=dict(size=20),
            title_font=dict(size=14),
            selector=dict(type="indicator")
        )
        
        # Add annotations for new franchisee breakdown if provided
        if len(new_locations) > 0:
            fig.add_annotation(
                text=f"<b>New Franchisee Breakdown:</b><br>Expected: ${new_expected:,.0f}<br>Broker Fees: ${new_broker:,.0f}<br>Net: ${new_net:,.0f}<br>Royalty: ${new_royalty:,.0f} | NAF: ${new_naf:,.0f} | Tech: ${new_tech:,.0f}",
                xref="paper", yref="paper",
                x=0.98, y=0.02,
                xanchor="right", yanchor="bottom",
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="black",
                borderwidth=1,
                showarrow=False,
                font=dict(size=10)
            )
        
        out = args.output if args.output else "outputs/plots/2026_executive_dashboard.html"
        ensure_output_dir(out)
        fig.write_html(out, include_plotlyjs="cdn", full_html=True)
        print(f"SUCCESS: Executive dashboard saved to {out}")
        print(f"\n=== TABLE 1 (Green Totals Row - Existing Franchisees) ===")
        print(f"  Franchisee Collections (Total Pay): ${franchisee_collections:,.2f}")
        print(f"  Franchisor Revenue (3 Cashflow Buckets): ${franchisor_revenue:,.2f}")
        print(f"    - Royalty 8%: ${franchisor_royalty:,.2f}")
        print(f"    - NAF 2%: ${franchisor_naf:,.2f}")
        print(f"    - Tech Fee: ${franchisor_tech:,.2f}")
        print(f"\n=== TABLE 2 (Monthly Breakdown - Includes New Franchise Sales) ===")
        print(f"  Annual Franchisor Intake (Sum): ${table2_total_franchisor:,.2f}")
        print(f"  Annual Broker Fees (Sum): ${table2_total_broker_fees:,.2f}")
        print(f"  Net Cashflow (After Broker Fees): ${table2_net_cashflow:,.2f}")
        print(f"\n=== TABLE 3 (Franchisee Cash Collections - Growth Rate) ===")
        print(f"  2024 YTD Franchisee Collections: ${franchisee_collections_2024:,.2f}")
        print(f"  2025 YTD Franchisee Collections: ${franchisee_collections_2025:,.2f}")
        print(f"  2026 Expected Franchisee Collections: ${franchisee_collections_2026:,.2f}")
        print(f"  2024->2025 Growth Rate: {growth_rate_pct_2025:.1f}% (Multiplier: {growth_multiplier_2025:.2f}x)")
        print(f"  2025->2026 Expected Growth Rate: {expected_growth_rate_pct:.1f}% (Multiplier: {growth_multiplier_2026:.2f}x)")
        return

    if args.location and "Location" in df.columns:
        row = df[df["Location"].astype(str) == str(args.location)].head(1)
        if row.empty:
            print(f"ERROR: Location '{args.location}' not found in sheet '{sheet_name}'")
            sys.exit(1)
        row = row.iloc[0].to_dict()
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        series_suffixes = [s.strip() for s in args.series.split(",") if s.strip()]
        data = {"Month": months}
        for suf in series_suffixes:
            vals = []
            for m in months:
                key = f"{m}_{suf}"
                vals.append(pd.to_numeric(row.get(key, None), errors="coerce"))
            data[suf] = vals
        mdf = pd.DataFrame(data)
        long_df = mdf.melt(id_vars=["Month"], value_vars=series_suffixes, var_name="Series", value_name="Value")
        title = args.title or f"{args.location} - 2026 Monthly Projections"
        fig = px.line(long_df, x="Month", y="Value", color="Series", title=title, markers=True)
        fig.update_layout(legend_title_text="")
        ensure_output_dir(args.output)
        fig.write_html(args.output, include_plotlyjs="cdn")
        print(f"SUCCESS: Chart saved to {args.output}")
        return

    # Choose axes (generic)
    if args.x_col:
        x_col = args.x_col
    else:
        x_col, _y = pick_default_axes(df)
    if args.y_cols:
        y_cols = [s.strip() for s in args.y_cols.split(",") if s.strip()]
    else:
        _, y_cols = pick_default_axes(df)

    if not x_col or not y_cols:
        print("ERROR: Could not determine x/y columns. Use --x and --y explicitly.")
        sys.exit(1)
    missing = [c for c in [x_col] + y_cols if c not in df.columns]
    if missing:
        print(f"ERROR: Columns not found: {missing}")
        sys.exit(1)

    # Melt for multi-series line chart
    plot_df = df[[x_col] + y_cols].copy()
    for c in y_cols:
        # Attempt numeric conversion to avoid strings
        plot_df[c] = pd.to_numeric(plot_df[c], errors="coerce")
    long_df = plot_df.melt(id_vars=[x_col], value_vars=y_cols, var_name="Series", value_name="Value")

    title = args.title or f"{os.path.basename(xlsx_path)} - {sheet_name}"
    fig = px.line(long_df, x=x_col, y="Value", color="Series", title=title, markers=True)
    fig.update_layout(legend_title_text="")

    ensure_output_dir(args.output)
    fig.write_html(args.output, include_plotlyjs="cdn")
    print(f"SUCCESS: Chart saved to {args.output}")


if __name__ == "__main__":
    main()


