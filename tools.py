# tools.py

from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional

from langchain_core.tools import tool

DB_PATH = Path("sunutech_db.sqlite")


def _get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Base de données non trouvée : {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@tool
def list_products() -> str:
    """
    Renvoie la liste des produits en stock, avec id, nom, prix et quantités.
    Retourne un texte multi-lignes. En cas d'erreur, retourne un message d'erreur.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, price, stock FROM products ORDER BY name;")
        rows = cur.fetchall()
        if not rows:
            return "Aucun produit trouvé."
        lines = [
            f"{r['id']}: {r['name']} — {r['price']:.2f} € — stock : {r['stock']}"
            for r in rows
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Erreur dans list_products : {e}"
    finally:
        try:
            if conn is not None:
                conn.close()
        except:
            pass


@tool
def check_product_inventory(product_name: str) -> str:
    """
    Cherche les produits dont le nom contient 'product_name'.
    Retourne un texte multi-lignes (id, nom, description, prix, stock).
    En cas d'erreur, retourne un message d'erreur.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        if not product_name:
            return "Veuillez préciser un nom de produit."
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, price, stock "
            "FROM products WHERE name LIKE ? ORDER BY name;",
            (f"%{product_name}%",),
        )
        rows = cur.fetchall()
        if not rows:
            return f"Aucun produit trouvé pour « {product_name} »."
        chunks = []
        for r in rows:
            chunks.append(
                f"{r['id']}: {r['name']}\n"
                f"  Description : {r['description']}\n"
                f"  Prix : {r['price']:.2f} €\n"
                f"  Stock : {r['stock']}"
            )
        return "\n\n".join(chunks)
    except Exception as e:
        return f"Erreur dans check_product_inventory : {e}"
    finally:
        try:
            if conn is not None:
                conn.close()
        except:
            pass


@tool
def get_order_status(order_id: int) -> str:
    """
    Renvoie le statut d'une commande par son ID.
    Retourne un résumé (client, montant, statut) ou un message si introuvable/erreur.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT status, total_amount, customer_name FROM orders WHERE id = ?;",
            (order_id,),
        )
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
            if conn is not None:
                conn.close()
        except:
            pass


@tool
def create_order(order_details: Dict[str, Any]) -> str:
    """
    Crée une commande à partir d'un dict 'order_details' contenant :
      - customer_name (str), customer_email (str), address (str)
      - items: List[ { product_id:int, quantity:int } ]
    Retourne un récapitulatif + ID de commande, ou un message d'erreur.
    """
    conn: Optional[sqlite3.Connection] = None

    # Validation minimale d'entrée
    if not isinstance(order_details, dict):
        return "Détails de commande invalides : 'order_details' doit être un objet."
    items = order_details.get("items")
    if not isinstance(items, list) or not items:
        return "Détails de commande invalides : 'items' manquant ou mal formé."

    try:
        conn = _get_connection()
        cur = conn.cursor()

        total_amount = 0.0

        # 1) Validation & calcul du total
        for item in items:
            pid = item.get("product_id")
            qty = item.get("quantity", 0)
            if pid is None or not isinstance(qty, int) or qty <= 0:
                return f"Quantité ou ID invalide dans : {item}"
            cur.execute(
                "SELECT price, stock FROM products WHERE id = ?;", (pid,))
            row = cur.fetchone()
            if row is None:
                return f"Produit ID {pid} non trouvé."
            price_each = row["price"]
            stock = row["stock"]
            if qty > stock:
                return f"Pas assez de stock pour le produit ID {pid}. Disponible : {stock}, demandé : {qty}"
            total_amount += price_each * qty

        # 2) Création de la commande
        cur.execute(
            "INSERT INTO orders(customer_name, customer_email, address, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?);",
            (
                order_details.get("customer_name", ""),
                order_details.get("customer_email", ""),
                order_details.get("address", ""),
                total_amount,
                "PENDING",
            ),
        )
        order_id = cur.lastrowid

        # 3) Lignes de commande + décrément du stock
        for item in items:
            pid = item["product_id"]
            qty = item["quantity"]
            cur.execute("SELECT price FROM products WHERE id = ?;", (pid,))
            price_each = cur.fetchone()["price"]
            cur.execute(
                "INSERT INTO order_items(order_id, product_id, quantity, price_each) "
                "VALUES (?, ?, ?, ?);",
                (order_id, pid, qty, price_each),
            )
            cur.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?;", (qty, pid))

        conn.commit()

        return (
            f"✅ Commande créée avec succès. ID de commande : {order_id}.\n"
            f"Montant total : {total_amount:.2f} €.\n"
            "Vous recevrez bientôt un email de confirmation."
        )
    except Exception as e:
        try:
            if conn is not None:
                conn.rollback()
        except:
            pass
        return f"Erreur lors de la création de la commande : {e}"
    finally:
        try:
            if conn is not None:
                conn.close()
        except:
            pass
