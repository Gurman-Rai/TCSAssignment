from dataclasses import asdict
from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from services.customer_service import CustomerService
from services.vector_store_service import VectorStoreService


mcp = FastMCP("Customer Support MCP Server")


@lru_cache(maxsize=1)
def _customer_service() -> CustomerService:
    return CustomerService()


@lru_cache(maxsize=1)
def _policy_service() -> VectorStoreService:
    return VectorStoreService()


def _nonempty(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be empty.")
    return value.strip()


def _positive_integer(value: int, label: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer.")


@mcp.tool()
def get_customer_by_email(email: str) -> dict[str, Any]:
    """Find a customer by email; return found=false when no customer matches."""
    customer = _customer_service().get_customer_by_email(_nonempty(email, "Email"))
    return {"found": customer is not None, "customer": asdict(customer) if customer else None}


@mcp.tool()
def search_customers_by_name(name: str) -> dict[str, Any]:
    """Search customer names using case-insensitive partial matching."""
    customers = _customer_service().search_customers_by_name(_nonempty(name, "Name"))
    return {"count": len(customers), "customers": [asdict(customer) for customer in customers]}


@mcp.tool()
def get_customer_tickets(customer_id: int) -> dict[str, Any]:
    """Retrieve all historical tickets for a customer, including product names."""
    _positive_integer(customer_id, "Customer ID")
    tickets = _customer_service().get_tickets_by_customer_id(customer_id)
    return {"count": len(tickets), "tickets": [asdict(ticket) for ticket in tickets]}


@mcp.tool()
def search_policies(query: str, k: int = 3) -> dict[str, Any]:
    """Search existing policy chunks. page_index is the stored zero-based page."""
    query = _nonempty(query, "Policy query")
    _positive_integer(k, "k")
    documents = _policy_service().search(query, k=k)
    return {
        "query": query,
        "results": [
            {
                "text": document.page_content,
                "source_file": document.metadata.get("source_file"),
                "page_index": document.metadata.get("page"),
            }
            for document in documents
        ],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
