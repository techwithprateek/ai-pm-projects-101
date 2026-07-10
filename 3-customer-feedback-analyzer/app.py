import csv
import io

import matplotlib.pyplot as plt
import streamlit as st
from dotenv import load_dotenv

from feedback_logic import (
    FeedbackAnalysisError,
    analyze_feedback,
    example_quote,
    sentiment_counts,
    top_themes,
)

load_dotenv()

# Status colors (fixed meaning: good / warning / critical) and a single
# sequential blue hue for magnitude ranking - see the dataviz skill's
# color-formula: status colors are reserved for state, never reused as a
# generic series color, and a ranked count uses one hue, not a rainbow.
SENTIMENT_COLORS = {"positive": "#0ca30c", "neutral": "#fab219", "negative": "#d03b3b"}
SEQUENTIAL_BLUE = "#2a78d6"

st.set_page_config(page_title="Customer Feedback Analyzer", page_icon="🔍")
st.title("🔍 Customer Feedback Analyzer")
st.caption(
    "Upload raw customer feedback (a CSV with a review_text column). The model "
    "tags each comment with sentiment and themes, then we aggregate into "
    "insights a product team can actually act on."
)

with st.expander("Don't have a CSV handy? Use the sample feedback dataset"):
    with open("sample_feedback.csv") as f:
        sample_csv = f.read()
    st.caption("40 sample reviews shaped like a typical Kaggle product-review export.")
    preview_rows = list(csv.DictReader(io.StringIO(sample_csv)))[:5]
    st.dataframe(preview_rows, hide_index=True)
    st.download_button("Download sample_feedback.csv", data=sample_csv, file_name="sample_feedback.csv")

uploaded = st.file_uploader("Feedback CSV", type="csv")
use_sample = st.checkbox("Analyze the sample feedback instead of uploading")

if st.button("Analyze feedback", type="primary"):
    if use_sample:
        with open("sample_feedback.csv") as f:
            csv_text = f.read()
    elif uploaded is not None:
        csv_text = uploaded.getvalue().decode("utf-8")
    else:
        st.error("Upload a CSV or check the sample feedback box.")
        st.stop()

    with st.spinner("Analyzing feedback... this may take a moment for larger files"):
        try:
            st.session_state.analyzed = analyze_feedback(csv_text)
        except FeedbackAnalysisError as e:
            st.error(str(e))

analyzed = st.session_state.get("analyzed")
if analyzed:
    st.divider()
    counts = sentiment_counts(analyzed)
    total = sum(counts.values())

    st.subheader("Sentiment breakdown")
    cols = st.columns(3)
    for col, sentiment in zip(cols, counts):
        pct = (counts[sentiment] / total * 100) if total else 0
        col.metric(sentiment.title(), f"{counts[sentiment]}", f"{pct:.0f}% of {total}")

    fig, ax = plt.subplots(figsize=(6, 2))
    labels = [s.title() for s in counts]
    values = list(counts.values())
    colors = [SENTIMENT_COLORS[s] for s in counts]
    bars = ax.barh(labels, values, color=colors, height=0.55)
    ax.bar_label(bars, padding=4, color="#52514e")
    ax.set_xlabel("")
    ax.spines[["top", "right", "bottom"]].set_visible(False)
    ax.tick_params(axis="both", length=0)
    ax.set_xticks([])
    ax.invert_yaxis()
    st.pyplot(fig, use_container_width=True)

    st.divider()
    st.subheader("Top themes")
    themes = top_themes(analyzed, n=10)
    if themes:
        fig2, ax2 = plt.subplots(figsize=(6, max(2, 0.4 * len(themes))))
        names = [t.title() for t, _ in reversed(themes)]
        counts_list = [c for _, c in reversed(themes)]
        bars2 = ax2.barh(names, counts_list, color=SEQUENTIAL_BLUE, height=0.6)
        ax2.bar_label(bars2, padding=4, color="#52514e")
        ax2.spines[["top", "right", "bottom"]].set_visible(False)
        ax2.tick_params(axis="both", length=0)
        ax2.set_xticks([])
        st.pyplot(fig2, use_container_width=True)

        st.caption("Example quote per theme")
        for theme, count in themes:
            with st.expander(f"{theme.title()} ({count} mentions)"):
                st.write(f"\"{example_quote(analyzed, theme)}\"")
    else:
        st.info("No themes extracted.")
