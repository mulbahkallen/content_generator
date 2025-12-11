from typing import Dict, Any, Optional

import streamlit as st

EXAMPLE_LIBRARY: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Default agency style": {
        "home": {},
        "service": {},
        "sub service": {},
        "about": {},
        "location": {},
    }
}


def get_example_for(style_profile: str, page_type: str) -> Optional[Dict[str, Any]]:
    """Return an example JSON for a given style profile and page type.

    The lookup prefers user-uploaded examples stored in
    ``st.session_state["uploaded_examples"]``. If none are available for the
    requested page_type, it falls back to ``EXAMPLE_LIBRARY``.
    """
    try:
        uploaded = st.session_state.get("uploaded_examples", {})
        if page_type in uploaded:
            return uploaded[page_type]
    except Exception:
        pass

    style_block = EXAMPLE_LIBRARY.get(style_profile)
    if not style_block:
        return None
    return style_block.get(page_type)
