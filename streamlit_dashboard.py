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

# Add custom CSS for Rolling Suds branding with sky blue background
st.markdown("""
    <style>
    .main {
        background-color: #E0F2FE;
    }
    .main .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
        max-width: 100%;
        background-color: #E0F2FE;
    }
    .stApp {
        background-color: #E0F2FE;
    }
    h1 {
        margin-bottom: 0.25rem;
        color: #20B2AA;
        font-weight: 700;
        text-align: center;
        font-size: 1.8rem;
    }
    h2, h3 {
        color: #20B2AA;
        font-size: 1.2rem;
    }
    .stMarkdown {
        margin-bottom: 0.25rem;
    }
    iframe {
        border: none;
        border-radius: 8px;
        width: 100%;
        max-height: 1850px;
        min-height: 1850px;
    }
    .logo-header {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 1rem;
        padding: 0.5rem 0;
    }
    .logo-header img {
        max-height: 60px;
        width: auto;
        margin: 0 auto;
    }
    .stButton>button {
        background-color: #20B2AA;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: 600;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #008B8B;
        color: white;
    }
    .sidebar .sidebar-content {
        background-color: #F5F5F5;
    }
    /* Hide Streamlit default elements for cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# Rolling Suds Logo and Header - compact centered layout
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    # Get script directory for absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try local logo file first with absolute paths, then fallback to URLs, then text
    logo_paths = [
        os.path.join(script_dir, "assets", "rolling_suds_logo.png"),
        os.path.join(script_dir, "rolling_suds_logo.png"),
        os.path.join(script_dir, "assets", "logo.png"),
        "assets/rolling_suds_logo.png",  # Relative fallback
        "rolling_suds_logo.png"
    ]
    
    logo_urls = [
        "https://www.rollingsudspowerwashing.com/wp-content/uploads/2023/05/Rolling-Suds-Logo.png",
        "https://rollingsudspowerwashing.com/wp-content/uploads/2023/05/Rolling-Suds-Logo.png"
    ]
    
    logo_displayed = False
    
    # Try local files first (PNG, SVG, JPG) - smaller size
    for logo_path in logo_paths:
        if os.path.exists(logo_path):
            try:
                st.image(logo_path, width=150, use_container_width=False)
                logo_displayed = True
                break
            except Exception as e:
                continue
    
    # Also try SVG - smaller size
    svg_paths = [
        os.path.join(script_dir, "assets", "rolling_suds_logo.svg"),
        "assets/rolling_suds_logo.svg"
    ]
    if not logo_displayed:
        for svg_path in svg_paths:
            if os.path.exists(svg_path):
                try:
                    st.image(svg_path, width=150, use_container_width=False)
                    logo_displayed = True
                    break
                except:
                    pass
    
    # If local file not found, try URLs - smaller size
    if not logo_displayed:
        for logo_url in logo_urls:
            try:
                st.image(logo_url, width=150, use_container_width=False)
                logo_displayed = True
                break
            except:
                continue
    
    # Final fallback: Show styled text
    if not logo_displayed:
        st.markdown("""
            <div style="text-align: center; color: #20B2AA; font-size: 28px; font-weight: bold; margin-bottom: 1rem; letter-spacing: 2px;">
                🧼 ROLLING SUDS
            </div>
        """, unsafe_allow_html=True)

st.title("📊 2026 Executive Dashboard - Financial Projections")
st.caption("Comprehensive financial projections and analytics for 2026")

# Minimal spacing
st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

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
    # Save uploaded file with absolute path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = os.path.join(script_dir, f"temp_{uploaded_file.name}")
    with open(xlsx_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.sidebar.success(f"File uploaded: {uploaded_file.name}")
else:
    # Use absolute path for default file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(script_dir, DEFAULT_FILE)
    if os.path.exists(default_path):
        xlsx_path = default_path
        st.sidebar.info(f"Using default file: {DEFAULT_FILE}")
    else:
        xlsx_path = DEFAULT_FILE  # Fallback to relative
        if os.path.exists(xlsx_path):
            xlsx_path = os.path.abspath(xlsx_path)
            st.sidebar.info(f"Using default file (relative path): {DEFAULT_FILE}")
        else:
            st.sidebar.warning(f"Default file not found. Please upload a file.")

# Dashboard options
st.sidebar.header("📊 Dashboard Options")
top_n = st.sidebar.slider("Top N Locations", 10, 50, 20, 5)
tiers = st.sidebar.slider("Number of Tiers", 2, 6, 4, 1)

output_path = "outputs/plots/2026_executive_dashboard.html"

# Ensure output directory exists
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# Get the script directory (already set above, but ensure it's available)
if 'script_dir' not in locals():
    script_dir = os.path.dirname(os.path.abspath(__file__))
plot_script_path = os.path.join(script_dir, "plot_2026_projections.py")

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
                    plot_script_path,
                    "--file", xlsx_path,
                    "--sheet", SHEET_NAME,
                    "--executive-dashboard",
                    "--top-n-locations", str(top_n),
                    "--tiers", str(tiers),
                    "--output", output_path,
                    "--title", "2026 Executive Dashboard - Financial Projections"
                ]
                # Use absolute path for output
                abs_output_path = os.path.join(script_dir, output_path) if not os.path.isabs(output_path) else output_path
                cmd[-2] = abs_output_path  # Update output path in command
                
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=script_dir, timeout=120)
                
                if result.returncode == 0:
                    # Check if output file was created
                    if os.path.exists(abs_output_path):
                        st.sidebar.success("✅ Dashboard generated successfully!")
                        if result.stdout:
                            # Show summary from stdout
                            stdout_lines = result.stdout.split('\n')
                            summary = [line for line in stdout_lines if 'TABLE' in line or 'Franchisee' in line or 'Franchisor' in line or 'Growth' in line or 'TIER' in line or 'Tier' in line]
                            if summary:
                                with st.sidebar.expander("📊 Dashboard Summary", expanded=False):
                                    st.text('\n'.join(summary[:15]))
                        st.rerun()
                    else:
                        st.sidebar.warning(f"⚠️ Script completed but output file not found. Check console output.")
                        st.info(f"**Output path:** {abs_output_path}\n**Script output:**\n{result.stdout[:500]}")
                    else:
                        st.sidebar.error(f"Script completed but output file not found at: {abs_output_path}")
                        st.error(f"Script output:\n{result.stdout}\n\nScript errors:\n{result.stderr}")
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    st.sidebar.error(f"❌ Error generating dashboard")
                    st.error(f"**Error Details:**\n\n{error_msg[:2000]}\n\n**Command:**\n{' '.join(cmd)}")
            except Exception as e:
                import traceback
                st.sidebar.error(f"Error: {str(e)}")
                st.error(f"Exception details:\n{traceback.format_exc()}")

# Display dashboard with compact layout
st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
st.header("📈 Executive Dashboard")

# Use absolute path for output file
abs_output_path = os.path.join(script_dir, output_path) if 'script_dir' in locals() and not os.path.isabs(output_path) else output_path
if not os.path.isabs(abs_output_path) and 'script_dir' in locals():
    abs_output_path = os.path.join(script_dir, output_path)

if os.path.exists(abs_output_path):
    # Check file modification time to warn if it's old
    import time
    file_age = time.time() - os.path.getmtime(abs_output_path)
    if file_age > 300:  # Older than 5 minutes
        st.info("ℹ️ **Tip:** This dashboard was generated more than 5 minutes ago. Click 'Generate/Refresh Dashboard' to see the latest changes (2-per-row layout, new tier system).")
    
    # Read and display the HTML dashboard
    with open(abs_output_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Create a centered container for compact display
    col1, col2, col3 = st.columns([1, 10, 1])
    with col2:
        # Display the dashboard with proper height and scrolling to see all charts
        st.components.v1.html(
            html_content, 
            height=1850, 
            scrolling=True,
            width=None
        )
    
    # Download button - centered
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        with open(abs_output_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Dashboard (HTML)",
                data=f.read(),
                file_name="2026_executive_dashboard.html",
                mime="text/html",
                use_container_width=True
            )
else:
    st.warning("⚠️ **Dashboard not found. Please generate it first!**")
    st.info("👆 Click 'Generate/Refresh Dashboard' in the sidebar to create the dashboard.")
    st.markdown("""
    ### Instructions:
    1. Upload your Excel workbook or use the default file
    2. Adjust the dashboard options (Top N Locations, Number of Tiers)
    3. Click **"🔄 Generate/Refresh Dashboard"** button in the sidebar
    4. Wait for the generation to complete (you'll see a success message)
    5. The dashboard will display automatically with the new 2-per-row layout
    6. **Note:** You must regenerate after code updates to see changes!
    """)

# Footer with spacing
st.markdown("<br>", unsafe_allow_html=True)
st.divider()
st.caption("💡 Tip: Use the sidebar to configure and regenerate the dashboard with different settings.")
