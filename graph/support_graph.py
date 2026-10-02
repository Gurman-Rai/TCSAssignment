"""Run router checks and sequential live graph tests: python -m graph.support_graph."""

import asyncio
import json
import re
import sys
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.customer_agent import CustomerAgent
from agents.policy_agent import PolicyAgent


Route = Literal["CUSTOMER", "POLICY", "BOTH"]
EMAIL = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+")
POLICY = re.compile(
    r"\b(?:polic(?:y|ies)|returns?|refunds?|accessibility|accommodations?|"
    r"human rights|business conduct|terms|eligible|eligibility)\b", re.I
)
CUSTOMER = re.compile(
    r"\b(?:tickets?|profiles?|support\s+(?:history|issues?|requests?)|purchases?|purchased)\b", re.I
)
# Only a small, explicit combined-question form; no arbitrary entity parsing.
LEADING_NAME = re.compile(
    r"^\s*(?P<name>[^\W\d_]+(?:[-’'][^\W\d_]+)*(?:\s+[^\W\d_]+(?:[-’'][^\W\d_]+)*){1,3})"
    r"\s+(?:wants|needs|would like)\b", re.I
)
ELIGIBILITY_LIMITATION = (
    "The available information does not establish this customer's return or refund "
    "eligibility. Policy applicability to the ticket's product, seller, return timing, "
    "receipt, and product condition must be verified."
)


class SupportState(TypedDict):
    question: str
    route: Route
    customer_result: dict[str, Any] | None
    policy_result: dict[str, Any] | None
    final_answer: str
    sources: list[dict[str, Any]]


def route_question(question: str) -> Route:
    """Specific customer signals override generic policy wording.

    Generic 'customers' in an accommodation question is not an identifier.
    Unrecognized nonempty questions default to POLICY, whose evidence handling
    can report insufficient information. Routing never invokes a model.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("The question must not be empty.")
    policy = bool(POLICY.search(question))
    customer = bool(EMAIL.search(question) or CUSTOMER.search(question) or LEADING_NAME.search(question))
    if policy:
        return "BOTH" if customer else "POLICY"
    if customer or re.search(r"\bcustomers?\b", question, re.I) or CustomerAgent._identifier(question):
        return "CUSTOMER"
    return "POLICY"


def customer_question(question: str) -> str:
    """Ask for customer facts separately from policy in combined questions."""
    if EMAIL.search(question):
        identifier = CustomerAgent._identifier(question)
        if identifier is None:
            return question  # Preserve the agent's multiple-identifier handling.
        name = identifier[1]
    else:
        match = LEADING_NAME.search(question)
        if not match:
            return question
        name = match.group("name")
    if re.search(r"\b(?:tickets?|issues?|support\s+(?:history|requests?))\b", question, re.I):
        return f"Show me the support tickets for {name}."
    return f"Tell me about {name}."


def policy_question(question: str) -> str:
    """Remove customer context only for combined return/refund retrieval."""
    if re.search(r"\breturns?\b", question, re.I):
        return "What is Apple's return policy?"
    if re.search(r"\brefunds?\b", question, re.I):
        return "What is Apple's refund policy?"
    return question


class SupportGraph:
    """A compiled LangGraph; BOTH runs customer then policy without fan-out."""

    def __init__(self, customer_agent: CustomerAgent | None = None,
                 policy_agent: PolicyAgent | None = None) -> None:
        self.customer_agent = customer_agent if customer_agent is not None else CustomerAgent()
        self.policy_agent = policy_agent if policy_agent is not None else PolicyAgent()
        builder = StateGraph(SupportState)
        builder.add_node("router", self._router)
        builder.add_node("customer", self._customer)
        builder.add_node("policy", self._policy)
        builder.add_node("combine", self._combine)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "router")
        builder.add_conditional_edges("router", lambda s: s["route"], {
            "CUSTOMER": "customer", "POLICY": "policy", "BOTH": "customer",
        })
        builder.add_conditional_edges("customer", lambda s: s["route"], {
            "CUSTOMER": "finalize", "BOTH": "policy",
        })
        builder.add_conditional_edges("policy", lambda s: s["route"], {
            "POLICY": "finalize", "BOTH": "combine",
        })
        builder.add_edge("combine", END)
        builder.add_edge("finalize", END)
        self.workflow = builder.compile()

    @staticmethod
    def _router(state: SupportState) -> dict:
        return {"route": route_question(state["question"])}

    async def _customer(self, state: SupportState) -> dict:
        question = customer_question(state["question"]) if state["route"] == "BOTH" else state["question"]
        return {"customer_result": await self.customer_agent.ask(question)}

    async def _policy(self, state: SupportState) -> dict:
        question = policy_question(state["question"]) if state["route"] == "BOTH" else state["question"]
        result = await self.policy_agent.ask(question)
        return {"policy_result": result, "sources": result["sources"]}

    @staticmethod
    def _combine(state: SupportState) -> dict:
        # Preserve the agents' answers verbatim rather than generating new facts.
        answer = (
            f"Customer information:\n{state['customer_result']['answer']}\n\n"
            f"Policy information:\n{state['policy_result']['answer']}"
        )
        if re.search(r"\b(?:returns?|refunds?|eligible|eligibility)\b", state["question"], re.I):
            answer += "\n\n" + ELIGIBILITY_LIMITATION
        return {"final_answer": answer}

    @staticmethod
    def _finalize(state: SupportState) -> dict:
        result = state["customer_result"] if state["route"] == "CUSTOMER" else state["policy_result"]
        return {"final_answer": result["answer"]}

    async def ask(self, question: str) -> dict[str, Any]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("The question must not be empty.")
        state = await self.workflow.ainvoke({
            "question": question.strip(), "customer_result": None,
            "policy_result": None, "sources": [], "final_answer": "",
        })
        customer_result = state["customer_result"] or {}
        return {
            "question": state["question"], "route": state["route"],
            "answer": state["final_answer"], "customer": customer_result.get("customer"),
            "tickets": customer_result.get("tickets", []), "sources": state["sources"],
            "customer_result": state["customer_result"], "policy_result": state["policy_result"],
        }


def check_router() -> None:
    examples = {
        "What is Apple's return policy?": "POLICY",
        "Show me Marisa Obrien's tickets.": "CUSTOMER",
        "Tell me about carrollallison@example.com": "CUSTOMER",
        "Can carrollallison@example.com get a refund under Apple's policy?": "BOTH",
        "What accommodations are available for customers with disabilities?": "POLICY",
        "What is Apple's human rights policy?": "POLICY",
        "Tell me about Marisa Obrien.": "CUSTOMER",
        "Marisa Obrien wants a refund.": "BOTH",
        "What support issues has carrollallison@example.com had?": "CUSTOMER",
        "Explain quantum gravity in detail": "POLICY",
    }
    for question, expected in examples.items():
        assert route_question(question) == expected, question
    for question in ("", "   ", None):
        try:
            route_question(question)
        except ValueError:
            pass
        else:
            raise AssertionError("Empty router input accepted")
    print(f"Deterministic router: {len(examples)} cases and empty-input checks passed.", flush=True)


async def main() -> None:
    from importlib.metadata import version
    from unittest.mock import patch

    check_router()
    graph = SupportGraph()
    print("LangGraph version:", version("langgraph"), flush=True)
    questions = [
        "Show me the support tickets for Marisa Obrien.",
        "What is Apple's return policy?",
        "Marisa Obrien wants to return the product from her support ticket. What does Apple's policy say?",
        "Can carrollallison@example.com return the product from their support ticket under Apple's return policy?",
    ]
    expected = [("CUSTOMER", ["CustomerAgent"]), ("POLICY", ["PolicyAgent"]),
                ("BOTH", ["CustomerAgent", "PolicyAgent"]), ("BOTH", ["CustomerAgent", "PolicyAgent"])]
    ran = []
    customer_ask, policy_ask = graph.customer_agent.ask, graph.policy_agent.ask

    async def customer_trace(question):
        ran.append("CustomerAgent")
        return await customer_ask(question)

    async def policy_trace(question):
        ran.append("PolicyAgent")
        return await policy_ask(question)

    with patch.object(graph.customer_agent, "ask", customer_trace), patch.object(
        graph.policy_agent, "ask", policy_trace
    ), patch.object(graph.customer_agent.llm_service, "invoke", wraps=graph.customer_agent.llm_service.invoke) as c_llm, patch.object(
        graph.policy_agent.llm_service, "invoke", wraps=graph.policy_agent.llm_service.invoke
    ) as p_llm:
        for value in ("", "   ", None):
            try:
                await graph.ask(value)
            except ValueError:
                pass
            else:
                raise AssertionError("Empty graph input accepted")
        assert ran == []
        for question, (route, agents) in zip(questions, expected):
            ran.clear()
            before = c_llm.call_count, p_llm.call_count
            print(f"\n{'=' * 50}\nLANGGRAPH TEST\nQuestion: {question}", flush=True)
            result = await graph.ask(question)
            assert result["route"] == route and ran == agents
            assert result["question"] == question
            assert (c_llm.call_count - before[0], p_llm.call_count - before[1]) == (
                int("CustomerAgent" in agents), int("PolicyAgent" in agents)
            )
            if route != "POLICY":
                assert result["customer"]["customer_id"] == 1
                assert result["customer"]["name"] == "Marisa Obrien"
                assert any(t["ticket_id"] == 1 and t["product_name"] == "GoPro Hero" for t in result["tickets"])
            else:
                assert result["customer"] is None and result["tickets"] == []
            if route != "CUSTOMER":
                assert any(s["source_file"] == "Apple - Legal - Sales Policies - Canadian Retail Sales.pdf" for s in result["sources"])
            else:
                assert result["sources"] == []
            if route == "BOTH":
                assert ELIGIBILITY_LIMITATION in result["answer"]
            print("Actual agents:", ran, flush=True)
            print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    print("\nAll four live LangGraph tests passed; agent isolation and sequential execution verified.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
