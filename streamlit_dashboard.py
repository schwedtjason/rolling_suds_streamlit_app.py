#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit app for 2026 Executive Dashboard
"""

import streamlit as st
import pandas as pd
import os
import subprocess
import sys

# Page config
st.set_page_config(
    page_title="2026 Executive Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 2026 Executive Dashboard - Financial Projections")
st.caption("Comprehensive financial projections and analytics for 2026")

# Sidebar for configuration
st.sidebar.header("⚙️ Configuration")

# File selection
DEFAULT_FILE = "2026 Projections (working Doc ) (version 1) (version 1).xlsx"
SHEET_NAME = "2026_Locations"

uploaded_file = st.sidebar.file_uploader(
    "Upload Excel Workbook",
    type=["xlsx", "xls"],
    help="Upload the 2026 Projections workbook"
)

if uploaded_file is not None:
    # Save uploaded file
    xlsx_path = f"temp_{uploaded_file.name}"
    with open(xlsx_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.sidebar.success(f"File uploaded: {uploaded_file.name}")
else:
    xlsx_path = DEFAULT_FILE
    if os.path.exists(xlsx_path):
        st.sidebar.info(f"Using default file: {DEFAULT_FILE}")
    else:
        st.sidebar.warning(f"Default file not found. Please upload a file.")

# Dashboard options
st.sidebar.header("📊 Dashboard Options")
top_n = st.sidebar.slider("Top N Locations", 10, 50, 20, 5)
tiers = st.sidebar.slider("Number of Tiers", 2, 6, 4, 1)

output_path = "outputs/plots/2026_executive_dashboard.html"

# Generate dashboard button
if st.sidebar.button("🔄 Generate/Refresh Dashboard", type="primary"):
    if not os.path.exists(xlsx_path):
        st.error(f"Excel file not found: {xlsx_path}")
    else:
        with st.spinner("Generating executive dashboard... This may take a moment."):
            try:
                # Run the dashboard generation script
                cmd = [
                    sys.executable,
                    "plot_2026_projections.py",
                    "--file", xlsx_path,
                    "--sheet", SHEET_NAME,
                    "--executive-dashboard",
                    "--top-n-locations", str(top_n),
                    "--tiers", str(tiers),
                    "--output", output_path,
                    "--title", "2026 Executive Dashboard - Financial Projections"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
                
                if result.returncode == 0:
                    st.sidebar.success("✅ Dashboard generated successfully!")
                    st.rerun()
                else:
                    st.sidebar.error(f"Error generating dashboard:\n{result.stderr}")
            except Exception as e:
                st.sidebar.error(f"Error: {str(e)}")

# Display dashboard
st.header("📈 Executive Dashboard")

if os.path.exists(output_path):
    # Read and display the HTML dashboard
    with open(output_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Display the dashboard
    st.components.v1.html(html_content, height=2000, scrolling=True)
    
    # Download button
    with open(output_path, "rb") as f:
        st.download_button(
            label="⬇️ Download Dashboard (HTML)",
            data=f.read(),
            file_name="2026_executive_dashboard.html",
            mime="text/html"
        )
else:
    st.info("👆 Please generate the dashboard using the button in the sidebar.")
    st.markdown("""
    ### Instructions:
    1. Upload your Excel workbook or use the default file
    2. Adjust the dashboard options (Top N Locations, Number of Tiers)
    3. Click "Generate/Refresh Dashboard" to create the dashboard
    4. The dashboard will display automatically once generated
    """)

# Footer
st.divider()
st.caption("💡 Tip: Use the sidebar to configure and regenerate the dashboard with different settings.")
