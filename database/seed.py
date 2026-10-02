import csv
from pathlib import Path

from database.database import Database


CSV_PATH = Path("data/raw/customer_support_tickets.csv")


def seed_database():
    db = Database()
    db.initialize()

    with open(CSV_PATH, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        with db.get_connection() as connection:
            cursor = connection.cursor()

            for row in reader:

                # Insert customer
                cursor.execute("""
                    INSERT OR IGNORE INTO customers (
                        name,
                        email,
                        age,
                        gender
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    row["Customer Name"],
                    row["Customer Email"],
                    int(row["Customer Age"]),
                    row["Customer Gender"]
                ))

                # Insert product
                cursor.execute("""
                    INSERT OR IGNORE INTO products (
                        product_name
                    )
                    VALUES (?)
                """, (
                    row["Product Purchased"],
                ))

                # Get customer ID
                customer = cursor.execute("""
                    SELECT customer_id
                    FROM customers
                    WHERE email = ?
                """, (
                    row["Customer Email"],
                )).fetchone()

                customer_id = customer["customer_id"]

                # Get product ID
                product = cursor.execute("""
                    SELECT product_id
                    FROM products
                    WHERE product_name = ?
                """, (
                    row["Product Purchased"],
                )).fetchone()

                product_id = product["product_id"]

                # Insert support ticket
                cursor.execute("""
                    INSERT OR IGNORE INTO support_tickets (
                        ticket_id,
                        customer_id,
                        product_id,
                        date_of_purchase,
                        ticket_type,
                        subject,
                        description,
                        status,
                        resolution,
                        priority,
                        channel,
                        first_response_time,
                        time_to_resolution,
                        satisfaction_rating
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(row["Ticket ID"]),
                    customer_id,
                    product_id,
                    row["Date of Purchase"],
                    row["Ticket Type"],
                    row["Ticket Subject"],
                    row["Ticket Description"],
                    row["Ticket Status"],

                    # Store missing values as SQL NULL
                    row["Resolution"] or None,

                    row["Ticket Priority"],
                    row["Ticket Channel"],

                    # Store missing timestamps as SQL NULL
                    row["First Response Time"] or None,
                    row["Time to Resolution"] or None,

                    # Convert rating to float if one exists
                    float(row["Customer Satisfaction Rating"])
                    if row["Customer Satisfaction Rating"]
                    else None
                ))

            # Save all inserts
            connection.commit()

            # Verify imported data
            customer_count = cursor.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]

            product_count = cursor.execute(
                "SELECT COUNT(*) FROM products"
            ).fetchone()[0]

            ticket_count = cursor.execute(
                "SELECT COUNT(*) FROM support_tickets"
            ).fetchone()[0]

            print("Database seeded successfully.")
            print(f"Customers imported: {customer_count}")
            print(f"Products imported: {product_count}")
            print(f"Support tickets imported: {ticket_count}")


if __name__ == "__main__":
    seed_database()