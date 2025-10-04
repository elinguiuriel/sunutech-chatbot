# app.py

import json
import traceback
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

from agent_graph import GRAPH

load_dotenv()

st.set_page_config(page_title="SunuTech Chatbot", layout="wide")
st.title("SunuTech — Agent Chat")

# --- état session ---
if "chat_state" not in st.session_state:
    st.session_state.chat_state = {"messages": []}

# conteneur unique pour le chat
chat_container = st.container()


def render_messages_once(msgs: list[Any]) -> None:
    """Render each message exactly once in the container."""
    with chat_container:
        for msg in msgs:
            if isinstance(msg, HumanMessage):
                with st.chat_message("user"):
                    st.markdown(_to_text(msg.content))
            elif isinstance(msg, AIMessage):
                with st.chat_message("assistant"):
                    st.markdown(_to_text(msg.content))
            else:
                with st.chat_message("assistant"):
                    st.markdown(_to_text(msg))


def _to_text(content: Any) -> str:
    if isinstance(content, (str, int, float)):
        return str(content)
    try:
        return "```json\n" + json.dumps(content, ensure_ascii=False, indent=2) + "\n```"
    except Exception:
        return str(content)


def append_message(state: dict, msg: Any) -> None:
    state.setdefault("messages", []).append(msg)


def call_graph_with_input(user_text: str) -> dict:
    st_state = st.session_state.chat_state

    human = HumanMessage(content=user_text)
    append_message(st_state, human)

    st_state["user_query"] = user_text

    try:
        # tu peux garder le spinner mais attention aux effets de ghost
        with st.spinner("L'agent réfléchit…"):
            new_state = GRAPH.invoke(st_state)
    except Exception as e:
        st.error(f"Erreur pendant l'inférence : {e}")
        st.code(traceback.format_exc())
        return st_state

    answer = new_state.get("answer")
    if answer:
        append_message(new_state, AIMessage(content=answer))
    st.session_state.chat_state = new_state
    return new_state


# --- bouton reset ---
if st.button("Réinitialiser la conversation"):
    st.session_state.chat_state = {"messages": []}
    st.rerun()  # remplace experimental_rerun()

# --- afficher tout l'historique une seule fois ---
render_messages_once(st.session_state.chat_state.get("messages", []))

# --- entrée utilisateur ---
if user_input := st.chat_input("Votre question…"):
    new_state = call_graph_with_input(user_input)
    # n'affiche ici **que** le dernier message AI (ou nouveau message)
    # pour éviter doublons, on ne réaffiche pas tout l'historique
    last_msg = new_state.get(
        "messages", [])[-1] if new_state.get("messages") else None
    if isinstance(last_msg, AIMessage):
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(_to_text(last_msg.content))
