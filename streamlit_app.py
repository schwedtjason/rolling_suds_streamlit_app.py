import io
from typing import Optional

import pandas as pd
import streamlit as st


def set_page():
\tst.set_page_config(
\t\ttitle=\"Rolling Suds Data Explorer\",
\t\tlayout=\"wide\",
\t\tinitial_sidebar_state=\"expanded\",
\t)
\tst.title(\"🧼 Rolling Suds • Data Explorer\")
\tst.caption(\"Upload a CSV or paste data to explore, summarize, and export.\")


@st.cache_data(show_spinner=False)
def load_csv(file_bytes: bytes, encoding: str) -> pd.DataFrame:
\tbuffer = io.BytesIO(file_bytes)
\treturn pd.read_csv(buffer, encoding=encoding)


def get_dataframe() -> Optional[pd.DataFrame]:
\tupload = st.sidebar.file_uploader(\"Upload CSV\", type=[\"csv\"])  # type: ignore[no-untyped-call]
\tencoding = st.sidebar.selectbox(\"Encoding\", [\"utf-8\", \"latin-1\", \"utf-16\"], index=0)

\twith st.sidebar.expander(\"Or paste CSV text\"):
\t\tpasted = st.text_area(\"Paste CSV here\", height=120)

\tif upload is not None:
\t\treturn load_csv(upload.getvalue(), encoding)  # type: ignore[no-untyped-call]

\tif pasted.strip():
\t\treturn pd.read_csv(io.StringIO(pasted))

\treturn None


def render_summary(df: pd.DataFrame) -> None:
\tleft, right = st.columns([2, 3])
\twith left:
\t\tst.subheader(\"Overview\")
\t\tst.write(f\"Rows: {len(df):,}\")
\t\tst.write(f\"Columns: {len(df.columns):,}\")
\t\tst.write(\"Numeric columns:\", list(df.select_dtypes(include=\"number\").columns))
\t\tst.write(\"Categorical columns:\", list(df.select_dtypes(exclude=\"number\").columns))

\twith right:
\t\tst.subheader(\"Quick stats (numeric)\")
\t\tst.dataframe(df.describe().T, use_container_width=True)


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
\twith st.expander(\"Filters\", expanded=False):
\t\tfiltered_df = df.copy()
\t\tfor column in df.columns:
\t\t\tcol_type = str(df[column].dtype)
\t\t\tif col_type.startswith(\"object\") or col_type == \"category\":
\t\t\t\tunique_values = sorted([str(x) for x in df[column].dropna().unique()])[:2000]
\t\t\t\tselected = st.multiselect(f\"{column}\", options=unique_values, default=[])
\t\t\t\tif selected:
\t\t\t\t\tfiltered_df = filtered_df[filtered_df[column].astype(str).isin(selected)]
\t\t\telif \"int\" in col_type or \"float\" in col_type:
\t\t\t\tmin_val = float(df[column].min())
\t\t\t\tmax_val = float(df[column].max())
\t\t\t\tval_range = st.slider(f\"{column}\", min_val, max_val, (min_val, max_val))
\t\t\t\tfiltered_df = filtered_df[(filtered_df[column] >= val_range[0]) & (filtered_df[column] <= val_range[1])]
\treturn filtered_df


def render_charts(df: pd.DataFrame) -> None:
\tst.subheader(\"Charts\")
\tnumeric_cols = list(df.select_dtypes(include=\"number\").columns)
\tif not numeric_cols:
\t\tst.info(\"No numeric columns to chart.\")
\t\treturn
\tx_col = st.selectbox(\"X axis\", options=numeric_cols, index=0)
\tchart_type = st.radio(\"Chart type\", [\"Line\", \"Area\", \"Bar\"], horizontal=True)
\tchart_df = df[[x_col]].copy()
\tchart_df.index.name = \"index\"
\tif chart_type == \"Line\":
\t\tst.line_chart(chart_df, use_container_width=True)
\telif chart_type == \"Area\":
\t\tst.area_chart(chart_df, use_container_width=True)
\telse:
\t\tst.bar_chart(chart_df, use_container_width=True)


def main() -> None:
\tset_page()
\twith st.sidebar:
\t\tst.markdown(\"### Options\")
\t\tshow_raw = st.checkbox(\"Show raw data\", value=False)
\t\tshow_filters = st.checkbox(\"Enable filters\", value=True)
\t\tshow_charts = st.checkbox(\"Show charts\", value=True)

\tdf = get_dataframe()
\tif df is None:
\t\tst.info(\"Upload or paste a CSV to get started.\")
\t\tst.markdown(\"Sample CSV format:\")
\t\tst.code(\"\"\"date,territory,amount\\n2024-01-01,TX-Dallas,1234.56\\n2024-01-02,TX-Austin,987.65\"\"\")
\t\treturn

\tst.success(\"Data loaded successfully.\")
\tif show_raw:
\t\tst.subheader(\"Raw data\")
\t\tst.dataframe(df, use_container_width=True)

\tif show_filters:
\t\tdf = render_filters(df)
\t\tst.caption(f\"Filtered rows: {len(df):,}\")

\trender_summary(df)
\tif show_charts:
\t\trender_charts(df)

\tst.divider()
\tcsv_bytes = df.to_csv(index=False).encode(\"utf-8\")
\tst.download_button(\"⬇️ Download filtered CSV\", data=csv_bytes, file_name=\"filtered.csv\", mime=\"text/csv\")
\tst.caption(\"v0.1 – Cached CSV parsing, filter widgets, simple charts, CSV export.\")


if __name__ == \"__main__\":
\tmain()
