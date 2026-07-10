import streamlit as st
from dotenv import load_dotenv

from idea_logic import IdeaRatingError, generate_questions, rate_idea

load_dotenv()

st.set_page_config(page_title="Idea Rater", page_icon="💡")
st.title("💡 Idea Rater")
st.caption(
    "Type a product idea. The model asks a few clarifying questions, then gives "
    "you a pros-and-cons list and an honest score."
)

for key, default in [("idea", ""), ("questions", None), ("rating", None)]:
    if key not in st.session_state:
        st.session_state[key] = default


def reset():
    st.session_state.idea = ""
    st.session_state.questions = None
    st.session_state.rating = None


idea = st.text_area(
    "Your idea",
    value=st.session_state.idea,
    placeholder="e.g. A browser extension that auto-summarizes long Slack threads",
    height=100,
)

if st.button("Get clarifying questions", type="primary"):
    if not idea.strip():
        st.error("Type an idea first.")
    else:
        with st.spinner("Thinking of questions..."):
            try:
                st.session_state.idea = idea
                st.session_state.questions = generate_questions(idea)
                st.session_state.rating = None
            except IdeaRatingError as e:
                st.error(str(e))

questions = st.session_state.questions
if questions:
    st.divider()
    st.subheader("A few questions first")
    answers = []
    with st.form("answers_form"):
        for i, q in enumerate(questions):
            answers.append(st.text_input(q, key=f"answer_{i}"))
        submitted = st.form_submit_button("Rate my idea", type="primary")

    if submitted:
        with st.spinner("Rating your idea..."):
            try:
                qa_pairs = list(zip(questions, answers))
                st.session_state.rating = rate_idea(st.session_state.idea, qa_pairs)
            except IdeaRatingError as e:
                st.error(str(e))

rating = st.session_state.rating
if rating:
    st.divider()
    st.subheader(f"Score: {rating.score}/10")
    st.progress(rating.score / 10)
    st.write(rating.rationale)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pros**")
        for p in rating.pros:
            st.markdown(f"- {p}")
    with col2:
        st.markdown("**Cons**")
        for c in rating.cons:
            st.markdown(f"- {c}")

    st.divider()
    if st.button("Rate another idea"):
        reset()
        st.rerun()
