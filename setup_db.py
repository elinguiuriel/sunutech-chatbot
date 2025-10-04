# setup_db.py

import sqlite3
from pathlib import Path

DB_PATH = Path("sunutech_db.sqlite")

def create_tables(conn: sqlite3.Connection):
    """
    Crée les tables de la base de données si elles n'existent pas.

    Les tables créées sont :
        - products : id, name, description, price, stock
        - orders : id, customer_name, customer_email, address, total_amount, status
        - order_items : id, order_id, product_id, quantity, price_each

    Les clés étrangères sont :
        - products.id : clé primaire auto-incrément
        - orders.id : clé primaire auto-incrément
        - order_items.id : clé primaire auto-incrément
        - order_items.order_id : clé étrangère vers orders.id
        - order_items.product_id : clé étrangère vers products.id
    """
    cur = conn.cursor()
    # Table produits
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    );
    """)
    # Table commandes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        customer_email TEXT,
        address TEXT,
        total_amount REAL,
        status TEXT DEFAULT 'PENDING'
    );
    """)
    # Table des articles d'une commande
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        price_each REAL,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)
    conn.commit()

def seed_products(conn: sqlite3.Connection):
    cur = conn.cursor()
    produits = [
        ("PC Basic 8 Go", "Ordinateur de bureau simple, 8 Go RAM", 250.0, 15),
        ("PC Gamer RTX", "PC gamer avec carte graphique RTX 4070", 1200.0, 5),
        ("Serveur Entry", "Serveur d'entrée 4 cœurs, 16 Go RAM", 800.0, 3),
        ("SSD 1To NVMe", "Disque SSD NVMe 1 To haute vitesse", 100.0, 20),
        ("SSD 2To NVMe", "Disque SSD NVMe 2 To", 180.0, 10),
        ("RAM 16 Go DDR4", "Barrette mémoire 16 Go DDR4", 60.0, 25),
        ("RAM 32 Go DDR4", "Barrette mémoire 32 Go DDR4", 110.0, 10),
        ("Moniteur 27\" 144Hz", "Moniteur 27 pouces, rafraîchissement 144 Hz", 300.0, 8),
        ("Clavier Mécanique", "Clavier mécanique RGB", 80.0, 30),
        ("Souris Gaming", "Souris gaming haute précision", 70.0, 30),
    ]
    for name, desc, price, stock in produits:
        cur.execute("""
        INSERT OR IGNORE INTO products(name, description, price, stock)
        VALUES (?, ?, ?, ?)
        """, (name, desc, price, stock))
    conn.commit()

def main():
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    seed_products(conn)
    conn.close()
    print("Base de données SunuTech créée à :", DB_PATH.resolve())

if __name__ == "__main__":
    main()
