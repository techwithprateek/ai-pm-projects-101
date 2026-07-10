import streamlit as st
from dotenv import load_dotenv

from prd_logic import PRDGenerationError, critique_prd, generate_prd, revise_prd

load_dotenv()

st.set_page_config(page_title="PRD Generator", page_icon="📝")
st.title("📝 PRD Generator")
st.caption(
    "Feed it a rough feature idea and whatever research notes you have. "
    "Get back a structured PRD, then have the model critique its own draft."
)

if "prd" not in st.session_state:
    st.session_state.prd = None
if "critique" not in st.session_state:
    st.session_state.critique = None

with st.form("prd_form"):
    feature_idea = st.text_area(
        "Feature idea",
        placeholder="e.g. Let users bulk-archive notifications instead of dismissing one at a time",
        height=100,
    )
    research_notes = st.text_area(
        "Research notes (optional)",
        placeholder="Paste interview quotes, support tickets, survey results, analytics...",
        height=150,
    )
    submitted = st.form_submit_button("Generate PRD", type="primary")

if submitted:
    if not feature_idea.strip():
        st.error("Give it at least a one-line feature idea.")
    else:
        with st.spinner("Drafting PRD..."):
            try:
                st.session_state.prd = generate_prd(feature_idea, research_notes)
                st.session_state.critique = None
            except PRDGenerationError as e:
                st.error(str(e))

prd = st.session_state.prd
if prd:
    st.divider()
    st.subheader("Problem")
    st.write(prd.problem)

    st.subheader("Goals")
    for g in prd.goals:
        st.markdown(f"- {g}")

    st.subheader("User Stories")
    for s in prd.user_stories:
        st.markdown(f"- {s}")

    st.subheader("Success Metrics")
    for m in prd.success_metrics:
        st.markdown(f"- {m}")

    if prd.open_questions:
        st.subheader("Open Questions")
        for q in prd.open_questions:
            st.markdown(f"- {q}")

    st.download_button(
        "Download as Markdown",
        data=prd.to_markdown(),
        file_name="prd.md",
        mime="text/markdown",
    )

    st.divider()
    st.subheader("Critique & Score")
    st.caption("How would you know if this PRD is actually good? Have the model review it like a skeptical peer.")
    if st.button("Critique this PRD"):
        with st.spinner("Reviewing..."):
            try:
                st.session_state.critique = critique_prd(prd)
            except PRDGenerationError as e:
                st.error(str(e))

    critique = st.session_state.critique
    if critique:
        cols = st.columns(len(critique.scores))
        for col, (dimension, score) in zip(cols, critique.scores.items()):
            col.metric(dimension.replace("_", " ").title(), f"{score}/5")
        st.info(critique.feedback)

    st.divider()
    st.subheader("Iterate")
    st.caption("Tell it what to change and regenerate the draft.")
    feedback = st.text_area("Feedback to incorporate", key="revision_feedback", height=80)
    if st.button("Revise PRD"):
        if not feedback.strip():
            st.error("Enter feedback to incorporate first.")
        else:
            with st.spinner("Revising..."):
                try:
                    st.session_state.prd = revise_prd(prd, feedback)
                    st.session_state.critique = None
                    st.rerun()
                except PRDGenerationError as e:
                    st.error(str(e))
