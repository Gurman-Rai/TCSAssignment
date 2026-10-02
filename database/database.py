import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path="database/customer_support.db"):
        self.db_path = Path(db_path)

    def get_connection(self):
        connection = sqlite3.connect(self.db_path)

        # Lets us access query results by column name
        connection.row_factory = sqlite3.Row

        # SQLite does not enforce foreign keys by default
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def initialize(self):
        with self.get_connection() as connection:
            cursor = connection.cursor()

            # Customer information
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    age INTEGER,
                    gender TEXT
                )
            """)

            # Products referenced by support tickets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL UNIQUE
                )
            """)

            # Historical customer support tickets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS support_tickets (
                    ticket_id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    product_id INTEGER,
                    date_of_purchase TEXT,
                    ticket_type TEXT,
                    subject TEXT,
                    description TEXT,
                    status TEXT,
                    resolution TEXT,
                    priority TEXT,
                    channel TEXT,
                    first_response_time TEXT,
                    time_to_resolution TEXT,
                    satisfaction_rating REAL,

                    FOREIGN KEY (customer_id)
                        REFERENCES customers(customer_id),

                    FOREIGN KEY (product_id)
                        REFERENCES products(product_id)
                )
            """)

            connection.commit()


if __name__ == "__main__":
    db = Database()
    db.initialize()

    print("Database initialized successfully.")