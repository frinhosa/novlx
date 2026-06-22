if len(st.session_state.chat_history) > 0:
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Starta en ny session"):
        st.session_state.chat_history = []
        if "senaste_referens" in st.session_state:
            del st.session_state.senaste_referens
        st.rerun()
