import csv
import json
import os
import streamlit as st

st.set_page_config(page_title="E-Commerce Returns & RMA Explorer", layout="wide")
st.title("E-Commerce Returns & RMA Synthetic Dataset Explorer")
st.caption("Deterministic Rule-Based Synthetic Pipeline | Fixed Seed: 20261022 | 30,000 Orders & 5,000 RMAs")

@st.cache_data
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

manifest = load_json(os.path.join("output", "manifest.json"))
val_summary = load_json(os.path.join("output", "validation_summary.json"))
counts = manifest["row_counts"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Customers", f"{counts['customers']:,}")
c2.metric("Orders", f"{counts['orders']:,}")
c3.metric("Return Requests", f"{counts['return_requests']:,}")
c4.metric("State Audit Events", f"{counts['state_event_log']:,}")
c5.metric("Labelled Anomalies", f"{counts['ground_truth']:,}")

tab1, tab2, tab3, tab4 = st.tabs(["Table Explorer", "Ground Truth Anomalies", "Validation & Manifest", "Data Dictionary"])

with tab1:
    tables = ["customers", "orders", "order_lines", "return_requests", "return_lines", "return_authorizations", "return_shipments", "inspections", "refunds", "inventory_dispositions", "state_event_log"]
    selected = st.selectbox("Select Normalized Table", tables)
    csv_path = os.path.join("output", "csv", f"{selected}.csv")
    rows = load_csv(csv_path)
    st.write(f"Showing first 100 of **{len(rows):,}** rows from `{selected}.csv`")
    st.dataframe(rows[:100], use_container_width=True)
    with open(csv_path, "rb") as f:
        st.download_button(f"Download {selected}.csv", f, file_name=f"{selected}.csv", mime="text/csv")

with tab2:
    st.subheader("Isolated Ground-Truth Edge Cases (75 Labelled Anomalies)")
    gt_rows = load_csv(os.path.join("output", "ground_truth", "ground_truth.csv"))
    all_types = sorted({r["issue_type"] for r in gt_rows})
    issue_filter = st.multiselect("Filter by Issue Type", all_types, default=all_types)
    filtered = [r for r in gt_rows if r["issue_type"] in issue_filter]
    st.dataframe(filtered, use_container_width=True)

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Validation Summary")
        st.json(val_summary)
    with col_b:
        st.subheader("SHA-256 Manifest")
        st.json(manifest)

with tab4:
    with open(os.path.join("docs", "DATA_DICTIONARY.md"), "r", encoding="utf-8") as f:
        st.markdown(f.read())