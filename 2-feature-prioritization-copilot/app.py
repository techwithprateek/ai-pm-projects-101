import streamlit as st
from dotenv import load_dotenv

from prioritization_logic import PrioritizationError, rank_features, score_backlog, to_csv

load_dotenv()

st.set_page_config(page_title="Feature Prioritization Copilot", page_icon="📊")
st.title("📊 Feature Prioritization Copilot")
st.caption(
    "Upload a backlog CSV (columns: feature, description). The model estimates "
    "RICE or ICE inputs for every item and ranks the backlog for you."
)

with st.expander("Don't have a CSV handy? Use the sample backlog"):
    with open("sample_backlog.csv") as f:
        sample_csv = f.read()
    st.code(sample_csv, language="csv")
    st.download_button("Download sample_backlog.csv", data=sample_csv, file_name="sample_backlog.csv")

framework = st.radio("Framework", ["RICE", "ICE"], horizontal=True)
uploaded = st.file_uploader("Backlog CSV", type="csv")

use_sample = st.checkbox("Score the sample backlog instead of uploading")

if st.button("Score backlog", type="primary"):
    if use_sample:
        with open("sample_backlog.csv") as f:
            csv_text = f.read()
    elif uploaded is not None:
        csv_text = uploaded.getvalue().decode("utf-8")
    else:
        st.error("Upload a CSV or check the sample backlog box.")
        st.stop()

    with st.spinner(f"Scoring against {framework}..."):
        try:
            st.session_state.scored = score_backlog(csv_text, framework)
            st.session_state.framework = framework
        except PrioritizationError as e:
            st.error(str(e))

scored = st.session_state.get("scored")
if scored:
    st.divider()
    st.subheader(f"Ranked backlog ({st.session_state.framework})")

    rows = []
    for rank, s in enumerate(scored, start=1):
        row = {"Rank": rank, "Feature": s.name, "Score": s.score}
        row.update({k.title(): v for k, v in s.estimates.items()})
        row["Rationale"] = s.rationale
        rows.append(row)
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.download_button(
        "Download ranked backlog as CSV",
        data=to_csv(scored),
        file_name=f"ranked_backlog_{st.session_state.framework.lower()}.csv",
        mime="text/csv",
    )
