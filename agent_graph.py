# agent_graph.py

import json
from typing import TypedDict, Literal, Any, Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from rag_system import DirectoryRAG
from tools import check_product_inventory, create_order, get_order_status

# --- Définition de l'état du graphe ---


class ChatState(TypedDict, total=False):
    messages: List[Any]
    user_query: str
    intent: Literal[
        "SUPPORT", "VENTE", "COMMANDE", "HANDOVER", "SALUTATION",
        "REMERCIEMENT", "AUREVOIR"
    ]
    answer: str
    trace: List[str]
    order_details: Optional[Dict[str, Any]]


# --- Initialisation des composants ---
rag = DirectoryRAG(folder_path="donnees", k=3)
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# --- Prompt de détection d'intention (y compris salutations etc.) ---
intent_template = ChatPromptTemplate.from_messages([
    ("system",
     "Tu es un détecteur d'intention pour un agent client. Analyse la requête et renvoie exactement un mot parmi : "
     "SUPPORT, VENTE, COMMANDE, HANDOVER, SALUTATION, REMERCIEMENT, AUREVOIR."),
    ("user", "{query}")
])

prompt_support = ChatPromptTemplate.from_messages([
    ("system", "Tu es agent de support technique. Utilise le CONTEXTE pour répondre."),
    ("user", "{query}\n\nCONTEXTE :\n{ctx}")
])

prompt_vente = ChatPromptTemplate.from_messages([
    ("system",
     "Tu es agent commercial. Si tu souhaites vérifier le stock/prix d'un produit, retourne un JSON littéral : "
     "{{\"tool\":\"check_product_inventory\",\"name\":\"nom_produit\"}}. Sinon, réponds normalement."),
    ("user", "{query}\n\nCONTEXTE :\n{ctx}")
])

prompt_commande = ChatPromptTemplate.from_messages([
    ("system",
     "Tu es agent de commande. Si tu veux créer une commande, retourne un JSON littéral : "
     "{{\"tool\":\"create_order\",\"order_details\":{...}}}. Sinon, réponds normalement."),
    ("user", "{query}\n\nCONTEXTE :\n{ctx}")
])

prompt_status = ChatPromptTemplate.from_messages([
    ("system",
     "Si l'utilisateur demande le statut d'une commande, retourne un JSON littéral : "
     "{{\"tool\":\"get_order_status\",\"order_id\":123}}."),
    ("user", "{query}")
])

prompt_handover = ChatPromptTemplate.from_messages([
    ("system", "Tu es agent général. Si la demande est hors périmètre, propose un transfert."),
    ("user", "{query}")
])

# --- Fonctions utilitaires ---


def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None

# --- Nœuds du graphe ---


def detect_intent(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    msg = intent_template.format_messages(query=q)
    resp = llm.invoke(msg).content.strip().upper()
    # Détection simplifiée selon mots clés
    if any(w in resp for w in ["BONJOUR", "SALUT", "HELLO"]):
        state["intent"] = "SALUTATION"
    elif any(w in resp for w in ["MERCI", "THANKS"]):
        state["intent"] = "REMERCIEMENT"
    elif any(w in resp for w in ["AU REVOIR", "BYE", "AUREVOIR"]):
        state["intent"] = "AUREVOIR"
    elif "SUPPORT" in resp:
        state["intent"] = "SUPPORT"
    elif "COMMANDE" in resp or "COMMANDER" in resp or "ACHAT" in resp:
        state["intent"] = "COMMANDE"
    elif "VENTE" in resp or "DISPONIBLE" in resp or "PRIX" in resp:
        state["intent"] = "VENTE"
    else:
        state["intent"] = "HANDOVER"
    state.setdefault("trace", []).append(
        f"[intent détectée] {state['intent']}")
    return state


def agent_support(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    ctx = rag.make_context(q)
    msg = prompt_support.format_messages(query=q, ctx=ctx)
    resp = llm.invoke(msg).content.strip()
    state["answer"] = resp
    state["trace"].append("[support] réponse modèle")
    return state


def agent_vente(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    ctx = rag.make_context(q)
    msg = prompt_vente.format_messages(query=q, ctx=ctx)
    resp = llm.invoke(msg).content.strip()
    state["trace"].append("[vente] réponse modèle brut")

    parsed = try_parse_json(resp)
    if parsed and parsed.get("tool") == "check_product_inventory" and "name" in parsed:
        tool_res = check_product_inventory(parsed["name"])
        state["answer"] = tool_res
        state["trace"].append(
            f"[vente] outil check_product_inventory({parsed['name']})")
    else:
        state["answer"] = resp
    return state


def agent_commande(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    ctx = rag.make_context(q)
    msg = prompt_commande.format_messages(query=q, ctx=ctx)
    resp = llm.invoke(msg).content.strip()
    state["trace"].append("[commande] réponse modèle brut")

    parsed = try_parse_json(resp)
    if parsed and parsed.get("tool") == "create_order" and "order_details" in parsed:
        tool_res = create_order(parsed["order_details"])
        state["answer"] = tool_res
        state["trace"].append("[commande] outil create_order")
    else:
        msg2 = prompt_status.format_messages(query=q)
        resp2 = llm.invoke(msg2).content.strip()
        parsed2 = try_parse_json(resp2)
        if parsed2 and parsed2.get("tool") == "get_order_status" and "order_id" in parsed2:
            tool_res2 = get_order_status(parsed2["order_id"])
            state["answer"] = tool_res2
            state["trace"].append("[commande] outil get_order_status")
        else:
            state["answer"] = resp
    return state


def agent_handover(state: ChatState) -> ChatState:
    state["answer"] = "Votre demande dépasse mes capacités. Je la transfère à un agent humain."
    state["trace"].append("[handover] escalade")
    return state


def agent_salutation(state: ChatState) -> ChatState:
    state["answer"] = "Bonjour ! En quoi puis-je vous aider aujourd'hui ?"
    state["trace"].append("[salutation]")
    return state


def agent_remerciement(state: ChatState) -> ChatState:
    state["answer"] = "Merci à vous ! Si vous avez d'autres questions, je suis là."
    state["trace"].append("[remerciement]")
    return state


def agent_aurevoir(state: ChatState) -> ChatState:
    state["answer"] = "Au revoir ! Passez une excellente journée !"
    state["trace"].append("[aurevoir]")
    return state


def route(state: ChatState) -> str:
    intent = state.get("intent")
    if intent == "SUPPORT":
        return "support"
    if intent == "VENTE":
        return "vente"
    if intent == "COMMANDE":
        return "commande"
    if intent == "SALUTATION":
        return "salutation"
    if intent == "REMERCIEMENT":
        return "remerciement"
    if intent == "AUREVOIR":
        return "aurevoir"
    return "handover"


def build_graph():
    g = StateGraph(ChatState)
    g.add_node("detect_intent", detect_intent)
    g.add_node("support", agent_support)
    g.add_node("vente", agent_vente)
    g.add_node("commande", agent_commande)
    g.add_node("handover", agent_handover)
    g.add_node("salutation", agent_salutation)
    g.add_node("remerciement", agent_remerciement)
    g.add_node("aurevoir", agent_aurevoir)

    g.set_entry_point("detect_intent")
    g.add_conditional_edges("detect_intent", route, {
        "support": "support",
        "vente": "vente",
        "commande": "commande",
        "salutation": "salutation",
        "remerciement": "remerciement",
        "aurevoir": "aurevoir",
        "handover": "handover",
    })
    g.add_edge("support", END)
    g.add_edge("vente", END)
    g.add_edge("commande", END)
    g.add_edge("handover", END)
    g.add_edge("salutation", END)
    g.add_edge("remerciement", END)
    g.add_edge("aurevoir", END)

    return g.compile()


GRAPH = build_graph()
