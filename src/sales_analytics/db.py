import sqlite3

from sqlite3 import Connection

def create_in_memory_db() -> Connection:
    """Create an in-memory SQLite database and initialize its schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn

def init_schema(conn: Connection) -> None:
    """Create the database tables, foreign keys, and indexes."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            country TEXT
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            total_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_orders_customer_id
            ON orders(customer_id);

        CREATE INDEX IF NOT EXISTS idx_orders_order_date
            ON orders(order_date);
            
        """
    )
    conn.commit()
