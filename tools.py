# tools.py

from pathlib import Path
import sqlite3
from typing import Any, Dict

from langchain_core.tools import tool

DB_PATH = Path("sunutech_db.sqlite")

def _get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Base de données non trouvée : {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@tool
def list_products(_: str = "") -> str:
    """
    Renvoie la liste des produits en stock, avec leurs noms, prix et quantités.
    Retourne une chaîne de caractères contenant les informations demandées.
    Si une erreur survient, renvoie un message d'erreur.
    """

    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, stock FROM products ORDER BY name")
        rows = cur.fetchall()
        if not rows:
            return "Aucun produit trouvé."
        lines = []
        for r in rows:
            lines.append(f"{r['id']}: {r['name']} — {r['price']:.2f} € — stock : {r['stock']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Erreur dans list_products : {e}"
    finally:
        try:
            conn.close()
        except:
            pass

@tool
def check_product_inventory(name_query: str) -> str:
    """
    Cherche les produits dont le nom contient une chaîne de caractères.
    Retourne une chaîne de caractères contenant les informations demandées.
    Si une erreur survient, renvoie un message d'erreur.
    Les résultats sont tris par ordre alphabétique.
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, price, stock FROM products WHERE name LIKE ?",
            (f"%{name_query}%",)
        )
        rows = cur.fetchall()
        if not rows:
            return f"Aucun produit trouvé pour « {name_query} »."
        lines = []
        for r in rows:
            lines.append(
                f"{r['id']}: {r['name']}\n"
                f"  Description : {r['description']}\n"
                f"  Prix : {r['price']:.2f} €\n"
                f"  Stock : {r['stock']}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Erreur dans check_product_inventory : {e}"
    finally:
        try:
            conn.close()
        except:
            pass

@tool
def get_order_status(order_id: int) -> str:
    """
    Cherche une commande par son ID.
    Retourne une chaîne de caractères contenant les informations demandées.
    Si une erreur survient, renvoie un message d'erreur.
    Les résultats sont tris par ordre alphabétique.
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status, total_amount, customer_name FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        if row is None:
            return f"Aucune commande trouvée pour l'ID {order_id}."
        return (
            f"Commande ID {order_id}\n"
            f"Client : {row['customer_name']}\n"
            f"Montant : {row['total_amount']:.2f} €\n"
            f"Statut : {row['status']}"
        )
    except Exception as e:
        return f"Erreur dans get_order_status : {e}"
    finally:
        try:
            conn.close()
        except:
            pass

@tool
def create_order(order_details: Dict[str, Any]) -> str:
    """
    Crée une commande à partir d'un dictionnaire contenant les détails de la commande.
    Le dictionnaire doit contenir la clé "items" avec une liste de dictionnaires, 
    chacun contenant les clés "product_id" et "quantity".
    Retourne une chaîne de caractères contenant les informations de la commande créée, 
    ou un message d'erreur si une erreur survient.
    """
    if "items" not in order_details or not isinstance(order_details["items"], list):
        return "Détails de commande invalides : 'items' manquant ou mal formé."
    try:
        conn = _get_connection()
        cur = conn.cursor()

        total_amount = 0.0
        for item in order_details["items"]:
            pid = item.get("product_id")
            qty = item.get("quantity", 0)
            if pid is None or qty <= 0:
                return f"Quantité ou ID invalide dans : {item}"
            cur.execute("SELECT price, stock FROM products WHERE id = ?", (pid,))
            row = cur.fetchone()
            if row is None:
                return f"Produit ID {pid} non trouvé."
            price_each = row["price"]
            stock = row["stock"]
            if qty > stock:
                return f"Pas assez de stock pour le produit ID {pid}. Disponible : {stock}, demandé : {qty}"
            total_amount += price_each * qty

        cur.execute(
            "INSERT INTO orders(customer_name, customer_email, address, total_amount, status) VALUES (?, ?, ?, ?, ?)",
            (
                order_details.get("customer_name", ""),
                order_details.get("customer_email", ""),
                order_details.get("address", ""),
                total_amount,
                "PENDING",
            ),
        )
        order_id = cur.lastrowid

        for item in order_details["items"]:
            pid = item["product_id"]
            qty = item["quantity"]
            cur.execute("SELECT price FROM products WHERE id = ?", (pid,))
            price_each = cur.fetchone()["price"]
            cur.execute(
                "INSERT INTO order_items(order_id, product_id, quantity, price_each) VALUES (?, ?, ?, ?)",
                (order_id, pid, qty, price_each),
            )
            cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, pid))

        conn.commit()

        return (
            f"✅ Commande créée avec succès. ID de commande : {order_id}.\n"
            f"Montant total : {total_amount:.2f} €.\n"
            "Vous recevrez bientôt un email de confirmation."
        )
    except Exception as e:
        conn.rollback()
        return f"Erreur lors de la création de la commande : {e}"
    finally:
        try:
            conn.close()
        except:
            pass
