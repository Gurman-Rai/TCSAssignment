"""Streamlit presentation layer for the existing async SupportGraph."""

import asyncio

import streamlit as st

from graph.support_graph import SupportGraph


EXAMPLES = (
    ("CUSTOMER", "Show me the support tickets for Marisa Obrien."),
    ("POLICY", "What is Apple's return policy?"),
    ("BOTH", "Marisa Obrien wants to return the product from her support ticket. What does Apple's policy say?"),
    ("EMAIL + BOTH", "Can carrollallison@example.com return the product from their support ticket under Apple's return policy?"),
)


def show_fields(record, fields):
    """Display populated fields without exposing null placeholders."""
    rows = [
        {"Field": label, "Value": str(record[key])}
        for key, label in fields
        if record.get(key) is not None and str(record[key]).strip()
    ]
    if rows:
        st.table(rows)


def display_result(result):
    st.subheader("Answer")
    st.caption(f"Route: {result['route']}")
    st.write(result["answer"])

    customer = result.get("customer")
    tickets = result.get("tickets") or []
    sources = list({
        (source["source_file"], source["page_index"]): source
        for source in result.get("sources", [])
    }.values())

    if customer:
        st.subheader("Customer")
        show_fields(customer, (
            ("customer_id", "Customer ID"), ("name", "Name"),
            ("email", "Email"), ("age", "Age"), ("gender", "Gender"),
        ))

    if tickets:
        st.subheader("Support Tickets")
        for ticket in tickets:
            st.markdown(f"#### Ticket {ticket['ticket_id']}")
            show_fields(ticket, (
                ("product_name", "Product"), ("ticket_type", "Type"),
                ("subject", "Subject"), ("status", "Status"),
                ("priority", "Priority"), ("date_of_purchase", "Purchase date"),
                ("channel", "Channel"),
            ))
            details = (
                ("description", "Description"), ("resolution", "Resolution"),
                ("first_response_time", "First response time"),
                ("time_to_resolution", "Time to resolution"),
                ("satisfaction_rating", "Satisfaction rating"),
            )
            if any(ticket.get(key) is not None and str(ticket[key]).strip() for key, _ in details):
                with st.expander(f"Details for ticket {ticket['ticket_id']}"):
                    show_fields(ticket, details)

    if sources:
        st.subheader("Policy Sources")
        st.caption("Pages are displayed as page_index + 1; backend metadata stays zero-based.")
        st.table([
            {"Source file": source["source_file"], "Page": source["page_index"] + 1}
            for source in sources
        ])

    with st.expander("Technical Details"):
        st.write({
            "Selected route": result["route"],
            "Customer returned": bool(customer),
            "Tickets": len(tickets),
            "Policy sources (unique)": len(sources),
        })


async def ask_support(question):
    # Create and use the graph in the same loop; no shared async resources.
    return await SupportGraph().ask(question)


def main():
    st.set_page_config(
        page_title="AI Customer Support Assistant", page_icon="💬", layout="wide"
    )
    st.title("AI Customer Support Assistant")
    st.write("Ask questions about customers, support tickets, and company policies.")

    with st.expander("Example questions", expanded=True):
        for label, question in EXAMPLES:
            st.write(f"**{label}:** {question}")

    with st.form("support_question"):
        question = st.text_input("Your question", placeholder="Enter a customer or policy question")
        submitted = st.form_submit_button("Ask", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            # Clear stale answers so a failure cannot look like a new result.
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_question", None)
            try:
                with st.spinner("Analyzing your question..."):
                    result = asyncio.run(ask_support(question.strip()))
                st.session_state["last_result"] = result
                st.session_state["last_question"] = question.strip()
            except Exception as exc:
                st.error(f"Unable to answer your question: {exc}")

    if "last_result" in st.session_state:
        st.caption(f"Question: {st.session_state['last_question']}")
        display_result(st.session_state["last_result"])


if __name__ == "__main__":
    main()
