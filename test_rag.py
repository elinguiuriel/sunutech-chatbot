# app_chat_ordered.py

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

if "chat_state" not in st.session_state:
    st.session_state.chat_state = {"messages": []}

# Container pour le chat
chat_container = st.container()

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

    # ajouter le message utilisateur
    human = HumanMessage(content=user_text)
    append_message(st_state, human)
    st_state["user_query"] = user_text

    try:
        with st.spinner("L’agent réfléchit…"):
            new_state = GRAPH.invoke(st_state)
    except Exception as e:
        st.error(f"Erreur pendant l’inférence : {e}")
        st.code(traceback.format_exc())
        return st_state

    # ajouter la réponse IA si présente
    answer = new_state.get("answer")
    if answer:
        append_message(new_state, AIMessage(content=answer))
    st.session_state.chat_state = new_state
    return new_state

def render_full_chat(msgs: list[Any]):
    """Affiche la totalité des messages dans l’ordre."""
    with chat_container:
        for msg in msgs:
            if isinstance(msg, HumanMessage):
                with st.chat_message("user"):
                    st.markdown(_to_text(msg.content))
            elif isinstance(msg, AIMessage):
                with st.chat_message("assistant"):
                    st.markdown(_to_text(msg.content))
            else:
                # fallback
                with st.chat_message("assistant"):
                    st.markdown(_to_text(msg))

# Bouton reset
if st.button("Réinitialiser la conversation"):
    st.session_state.chat_state = {"messages": []}
    st.rerun() 

# Affichage de l’historique actuel
render_full_chat(st.session_state.chat_state.get("messages", []))

# Zone de saisie utilisateur
if user_input := st.chat_input("Votre question…"):
    new_state = call_graph_with_input(user_input)
    # On a déjà ajouté le message utilisateur et la réponse IA dans l’état
    # On peut juste **afficher la dernière paire message-utilisateur + réponse IA**
    # pour éviter de tout re-rendre (bien que render_full_chat ci-dessus ait déjà tout affiché).
    # Ici on n’a pas besoin d’appeler render_full_chat de nouveau car l’état mis à jour est visible.

    # (Optionnel) Si tu veux afficher uniquement le nouveau message IA :
    last = new_state.get("messages", [])[-1]
    if isinstance(last, AIMessage):
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(_to_text(last.content))
