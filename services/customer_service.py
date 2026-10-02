from contextlib import closing
from pathlib import Path

from database.database import Database
from models.customer import Customer
from models.support_ticket import SupportTicket


class CustomerService:
    """Read customer profiles and historical tickets from the existing database."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database if database is not None else Database(
            Path(__file__).resolve().parents[1] / "database" / "customer_support.db"
        )
        # sqlite3.connect would otherwise create an empty database at a missing path.
        if not self.database.db_path.is_file():
            raise FileNotFoundError(f"Database not found: {self.database.db_path}")

    def get_customer_by_email(self, email: str) -> Customer | None:
        with closing(self.database.get_connection()) as connection:
            row = connection.execute(
                """
                SELECT customer_id, name, email, age, gender
                FROM customers WHERE email = ?
                """,
                (email,),
            ).fetchone()
        return Customer(**dict(row)) if row is not None else None

    def search_customers_by_name(self, name: str) -> list[Customer]:
        name = name.strip()
        if not name:
            return []
        # Treat LIKE wildcards as literal characters in the supplied name.
        pattern = name.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        with closing(self.database.get_connection()) as connection:
            rows = connection.execute(
                """
                SELECT customer_id, name, email, age, gender
                FROM customers
                WHERE name COLLATE NOCASE LIKE ? ESCAPE '!'
                ORDER BY customer_id
                """,
                (f"%{pattern}%",),
            ).fetchall()
        return [Customer(**dict(row)) for row in rows]

    def get_tickets_by_customer_id(self, customer_id: int) -> list[SupportTicket]:
        with closing(self.database.get_connection()) as connection:
            rows = connection.execute(
                """
                SELECT t.ticket_id, t.customer_id, p.product_name,
                       t.date_of_purchase, t.ticket_type, t.subject,
                       t.description, t.status, t.resolution, t.priority,
                       t.channel, t.first_response_time, t.time_to_resolution,
                       t.satisfaction_rating
                FROM support_tickets AS t
                LEFT JOIN products AS p ON p.product_id = t.product_id
                WHERE t.customer_id = ?
                ORDER BY t.ticket_id
                """,
                (customer_id,),
            ).fetchall()
        return [SupportTicket(**dict(row)) for row in rows]

    def get_customer_with_tickets(
        self, email: str
    ) -> tuple[Customer, list[SupportTicket]] | None:
        customer = self.get_customer_by_email(email)
        if customer is None:
            return None
        return customer, self.get_tickets_by_customer_id(customer.customer_id)


if __name__ == "__main__":
    service = CustomerService()
    with closing(service.database.get_connection()) as connection:
        row = connection.execute(
            "SELECT customer_id, name, email, age, gender "
            "FROM customers ORDER BY customer_id LIMIT 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("The existing database has no customers to test.")
        expected_customer = Customer(**dict(row))
        expected_tickets = connection.execute(
            """
            SELECT t.ticket_id, t.customer_id, p.product_name
            FROM support_tickets AS t
            LEFT JOIN products AS p ON p.product_id = t.product_id
            WHERE t.customer_id = ? ORDER BY t.ticket_id
            """,
            (expected_customer.customer_id,),
        ).fetchall()

    customer = service.get_customer_by_email(expected_customer.email)
    assert isinstance(customer, Customer) and customer == expected_customer
    matches = service.search_customers_by_name(expected_customer.name.swapcase())
    assert customer in matches and all(isinstance(match, Customer) for match in matches)
    tickets = service.get_tickets_by_customer_id(customer.customer_id)
    assert all(isinstance(ticket, SupportTicket) for ticket in tickets)
    assert [(t.ticket_id, t.customer_id, t.product_name) for t in tickets] == [
        tuple(row) for row in expected_tickets
    ]
    assert all(ticket.customer_id == customer.customer_id for ticket in tickets)
    assert service.get_customer_with_tickets(customer.email) == (customer, tickets)

    print(f"{'=' * 50}\nCUSTOMER LOOKUP TEST\n{'=' * 50}")
    print(f"\nCustomer:\nID: {customer.customer_id}\nName: {customer.name}")
    print(f"Email: {customer.email}\nAge: {customer.age}\nGender: {customer.gender}")
    print(f"\nCase-insensitive name matches: {len(matches)}")
    print(f"Support Tickets: {len(tickets)}")
    for ticket in tickets:
        print(f"\n{'-' * 50}\nTicket ID: {ticket.ticket_id}")
        print(f"Product: {ticket.product_name}\nType: {ticket.ticket_type}")
        print(f"Subject: {ticket.subject}\nStatus: {ticket.status}")
        print(f"Priority: {ticket.priority}\n{'-' * 50}")
    print("\nCustomer, ticket ownership, product join, and model checks passed.")
