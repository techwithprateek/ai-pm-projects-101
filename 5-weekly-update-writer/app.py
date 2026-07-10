import streamlit as st
from dotenv import load_dotenv

from update_logic import AUDIENCES, TONES, UpdateGenerationError, generate_update

load_dotenv()

st.set_page_config(page_title="Weekly Update Writer", page_icon="🗓️")
st.title("🗓️ Weekly Update Writer")
st.caption(
    "Paste your rough, messy notes from the week. The model turns them into a "
    "clean, honest update - organized into what got done, what's in "
    "progress, what's blocked, and what's next."
)

notes = st.text_area(
    "Rough notes",
    placeholder=(
        "e.g. finally shipped the export feature, still stuck waiting on legal "
        "sign-off for the pricing page, onboarding interviews went well - 6 done, "
        "need to start the RICE scoring doc next week"
    ),
    height=180,
)

col1, col2 = st.columns(2)
with col1:
    tone = st.radio("Tone", TONES, horizontal=True)
with col2:
    audience = st.radio("Audience", AUDIENCES, horizontal=True)

if st.button("Write my update", type="primary"):
    if not notes.strip():
        st.error("Paste some notes first.")
    else:
        with st.spinner("Writing update..."):
            try:
                st.session_state.update = generate_update(notes, tone, audience)
            except UpdateGenerationError as e:
                st.error(str(e))

update = st.session_state.get("update")
if update:
    st.divider()
    st.subheader("Your update")

    if update.accomplishments:
        st.markdown("**Accomplishments this week**")
        for item in update.accomplishments:
            st.markdown(f"- {item}")
    if update.in_progress:
        st.markdown("**In progress**")
        for item in update.in_progress:
            st.markdown(f"- {item}")
    if update.blockers:
        st.markdown("**Blockers**")
        for item in update.blockers:
            st.markdown(f"- {item}")
    if update.next_steps:
        st.markdown("**Next week**")
        for item in update.next_steps:
            st.markdown(f"- {item}")

    st.divider()
    message = update.to_message()
    st.text_area("Copy-paste ready version", value=message, height=200)
    st.download_button("Download as .txt", data=message, file_name="weekly_update.txt")
