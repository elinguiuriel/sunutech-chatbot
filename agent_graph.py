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
        "SUPPORT", "VENTE", "COMMANDE", "HANDOVER",
        "SALUTATION", "REMERCIEMENT", "AUREVOIR"
    ]
    answer: str
    trace: List[str]
    order_details: Optional[Dict[str, Any]]


# --- Initialisation des composants ---
rag = DirectoryRAG(folder_path="donnees", k=3)
llm = ChatOpenAI(model="gpt-4o", temperature=0)


# --- Prompts (accolades doublées pour JSON littéral !) ---
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
     "Tu es agent commercial. Si tu souhaites vérifier le stock/prix d'un produit, renvoie un JSON littéral EXACT : "
     "{{\"tool\": \"check_product_inventory\", \"name\": \"<nom_produit>\"}}. "
     "Sinon, réponds normalement."),
    ("user", "{query}\n\nCONTEXTE :\n{ctx}")
])

prompt_commande = ChatPromptTemplate.from_messages([
    ("system",
     "Tu es agent de commande. Si tu veux créer une commande, renvoie un JSON littéral EXACT, par ex. :\n"
     "{{\"tool\": \"create_order\", \"order_details\": {{"
     "\"customer_name\": \"<nom>\", "
     "\"customer_email\": \"<email>\", "
     "\"address\": \"<adresse>\", "
     "\"items\": [{{\"product_id\": 1, \"quantity\": 2}}, {{\"product_id\": 3, \"quantity\": 1}}]"
     "}}}}\n"
     "Sinon, réponds normalement."),
    ("user", "{query}\n\nCONTEXTE :\n{ctx}")
])

prompt_status = ChatPromptTemplate.from_messages([
    ("system",
     "Si l'utilisateur demande le statut d'une commande, renvoie un JSON littéral EXACT : "
     "{{\"tool\": \"get_order_status\", \"order_id\": 123}}."),
    ("user", "{query}")
])

prompt_handover = ChatPromptTemplate.from_messages([
    ("system", "Tu es agent général. Si la demande est hors périmètre, propose un transfert."),
    ("user", "{query}")
])


# --- Utilitaires ---
def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text.strip())
    except Exception:
        return None


def _safe_tool_call(tool_fn, payload: Dict) -> str:
    """Appelle un outil LangChain (@tool) en passant un dict avec les bons champs."""
    try:
        return tool_fn(payload)
    except Exception as e:
        return f"[outil:{getattr(tool_fn, 'name', tool_fn.__name__)}] erreur: {e}"


# --- Nœuds du graphe ---
def detect_intent(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    msg = intent_template.format_messages(query=q)
    try:
        resp = llm.invoke(msg).content.strip().upper()
    except Exception as e:
        state["intent"] = "HANDOVER"
        state.setdefault("trace", []).append(f"[intent] erreur LLM: {e}")
        return state

    # Détection simplifiée selon mots clés + label retourné
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
    try:
        resp = llm.invoke(msg).content.strip()
    except Exception as e:
        resp = f"Désolé, une erreur est survenue côté support : {e}"
    state["answer"] = resp
    state.setdefault("trace", []).append("[support] réponse modèle")
    return state


def agent_vente(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    ctx = rag.make_context(q)
    msg = prompt_vente.format_messages(query=q, ctx=ctx)
    try:
        resp = llm.invoke(msg).content.strip()
    except Exception as e:
        state["answer"] = f"Désolé, une erreur est survenue côté vente : {e}"
        state.setdefault("trace", []).append("[vente] erreur LLM")
        return state

    state.setdefault("trace", []).append("[vente] réponse modèle brut")
    parsed = try_parse_json(resp)
    if parsed and parsed.get("tool") == "check_product_inventory" and "name" in parsed:
        # ✅ passer le bon payload attendu par @tool
        payload = {"product_name": parsed["name"]}
        tool_res = _safe_tool_call(check_product_inventory, payload)
        state["answer"] = tool_res
        state["trace"].append(
            f"[vente] outil check_product_inventory payload={payload}")
    else:
        state["answer"] = resp
    return state


def agent_commande(state: ChatState) -> ChatState:
    q = state.get("user_query", "")
    ctx = rag.make_context(q)
    msg = prompt_commande.format_messages(query=q, ctx=ctx)
    try:
        resp = llm.invoke(msg).content.strip()
    except Exception as e:
        state["answer"] = f"Désolé, une erreur est survenue côté commande : {e}"
        state.setdefault("trace", []).append("[commande] erreur LLM")
        return state

    state.setdefault("trace", []).append("[commande] réponse modèle brut")
    parsed = try_parse_json(resp)

    if parsed and parsed.get("tool") == "create_order" and "order_details" in parsed:
        # ✅ passer le bon payload attendu par @tool
        payload = {"order_details": parsed["order_details"]}
        tool_res = _safe_tool_call(create_order, payload)
        state["answer"] = tool_res
        state["trace"].append(
            f"[commande] outil create_order payload=order_details")
        return state

    # sinon on tente un statut de commande
    msg2 = prompt_status.format_messages(query=q)
    try:
        resp2 = llm.invoke(msg2).content.strip()
    except Exception as e:
        state["answer"] = f"Désolé, une erreur est survenue côté statut de commande : {e}"
        state["trace"].append("[commande] erreur LLM (status)")
        return state

    parsed2 = try_parse_json(resp2)
    if parsed2 and parsed2.get("tool") == "get_order_status" and "order_id" in parsed2:
        try:
            oid = int(parsed2["order_id"])
        except Exception:
            oid = parsed2["order_id"]
        payload = {"order_id": oid}
        tool_res2 = _safe_tool_call(get_order_status, payload)
        state["answer"] = tool_res2
        state["trace"].append(
            f"[commande] outil get_order_status payload={payload}")
    else:
        # pas d'appel d'outil, on renvoie la réponse libre
        state["answer"] = resp

    return state


def agent_handover(state: ChatState) -> ChatState:
    state["answer"] = "Votre demande dépasse mes capacités. Je la transfère à un agent humain."
    state.setdefault("trace", []).append("[handover] escalade")
    return state


def agent_salutation(state: ChatState) -> ChatState:
    state["answer"] = "Bonjour ! En quoi puis-je vous aider aujourd'hui ?"
    state.setdefault("trace", []).append("[salutation]")
    return state


def agent_remerciement(state: ChatState) -> ChatState:
    state["answer"] = "Merci à vous ! Si vous avez d'autres questions, je suis là."
    state.setdefault("trace", []).append("[remerciement]")
    return state


def agent_aurevoir(state: ChatState) -> ChatState:
    state["answer"] = "Au revoir ! Passez une excellente journée !"
    state.setdefault("trace", []).append("[aurevoir]")
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
