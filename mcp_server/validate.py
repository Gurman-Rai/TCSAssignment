"""Integration smoke test: python -m mcp_server.validate (requires local Ollama)."""

import asyncio
from contextlib import closing
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys

import chromadb
from jsonschema import validate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from database.database import Database
from mcp_server import server


ROOT = Path(__file__).resolve().parents[1]
QUERY = "What is Apple's return policy?"
POLICY_SOURCE = "Apple - Legal - Sales Policies - Canadian Retail Sales.pdf"
CALLS = {
    "get_customer_by_email": {"email": "carrollallison@example.com"},
    "search_customers_by_name": {"name": "Marisa Obrien"},
    "get_customer_tickets": {"customer_id": 1},
    "search_policies": {"query": QUERY},
}


def check_results(results: dict) -> None:
    customer = results["get_customer_by_email"]
    assert customer["found"] and customer["customer"]["name"] == "Marisa Obrien"
    assert customer["customer"]["customer_id"] == 1
    matches = results["search_customers_by_name"]
    assert matches["count"] == len(matches["customers"])
    assert customer["customer"] in matches["customers"]
    tickets = results["get_customer_tickets"]
    assert tickets["count"] == len(tickets["tickets"])
    assert all(ticket["customer_id"] == 1 for ticket in tickets["tickets"])
    assert any(t["ticket_id"] == 1 and t["product_name"] == "GoPro Hero" for t in tickets["tickets"])
    policies = results["search_policies"]
    assert policies["query"] == QUERY and len(policies["results"]) == 3
    assert any(r["source_file"] == POLICY_SOURCE and "return" in r["text"].lower() for r in policies["results"])
    assert all(r["text"] and isinstance(r["page_index"], int) for r in policies["results"])


async def check_protocol() -> None:
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT)
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=90)) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            assert {tool.name for tool in tools} == set(CALLS)
            results = {}
            for tool in tools:
                validate(CALLS[tool.name], tool.inputSchema)
                assert tool.inputSchema["type"] == "object"
                result = await session.call_tool(tool.name, CALLS[tool.name])
                assert not result.isError, result.content
                assert result.structuredContent is not None
                if tool.outputSchema:
                    validate(result.structuredContent, tool.outputSchema)
                results[tool.name] = result.structuredContent
            check_results(results)
            for name, arguments in [
                ("get_customer_by_email", {"email": " "}),
                ("search_customers_by_name", {"name": ""}),
                ("get_customer_tickets", {"customer_id": 0}),
                ("search_policies", {"query": " "}),
                ("search_policies", {"query": QUERY, "k": 0}),
                ("get_customer_tickets", {"customer_id": "invalid"}),
            ]:
                assert (await session.call_tool(name, arguments)).isError
            print("Stdio handshake, four tool schemas, all tool calls, and error responses: passed")
            print("Registered tools:", ", ".join(sorted(CALLS)))
    # The SDK closes the session and terminates its subprocess here.


def main() -> None:
    db_path = ROOT / "database" / "customer_support.db"
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    collection = chromadb.PersistentClient(path=str(ROOT / "data" / "chroma_db")).get_collection("apple_policies")
    assert collection.count() == 202
    original_ids = set(collection.get()["ids"])
    results = {name: getattr(server, name)(**arguments) for name, arguments in CALLS.items()}
    json.dumps(results)  # Confirm the direct tool results are JSON-serializable.
    check_results(results)
    assert server.get_customer_by_email("missing-customer@example.invalid") == {"found": False, "customer": None}
    assert server.search_customers_by_name("MARISA OBRIEN")["customers"] == results["search_customers_by_name"]["customers"]
    for function, arguments in [
        (server.get_customer_by_email, {"email": " "}),
        (server.search_customers_by_name, {"name": " "}),
        (server.get_customer_tickets, {"customer_id": -1}),
        (server.search_policies, {"query": " "}),
        (server.search_policies, {"query": QUERY, "k": 0}),
        (server.search_policies, {"query": QUERY, "k": 1.5}),
    ]:
        try:
            function(**arguments)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid input was accepted")
    print("Direct tool calls, serialization, missing customer, and invalid inputs: passed")
    print("Customer: carrollallison@example.com -> Marisa Obrien (ID 1)")
    print("Ticket: customer 1 -> ticket 1 -> GoPro Hero")
    for result in results["search_policies"]["results"]:
        print(f"Policy: {result['source_file']}, page_index={result['page_index']}")
    asyncio.run(check_protocol())
    with closing(Database(db_path).get_connection()) as connection:
        counts = tuple(connection.execute(query).fetchone()[0] for query in (
            "SELECT COUNT(*) FROM customers", "SELECT COUNT(*) FROM products",
            "SELECT COUNT(*) FROM support_tickets",
        ))
    assert counts == (8320, 42, 8469)
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before
    assert collection.count() == 202 and set(collection.get()["ids"]) == original_ids
    print("SQLite counts:", counts, "(database SHA-256 unchanged)")
    print("Chroma: 202 chunks; document IDs unchanged")


if __name__ == "__main__":
    main()
