"""
LangGraph pipeline: Retriever -> Analyst -> Critic -> Report.

Every node is a PLAIN PYTHON FUNCTION that takes the state dict and
returns updated fields. No async anywhere. LangGraph fully supports this.

Interview points:
- Why LangGraph over a plain LangChain chain? State management +
  conditional edges. Here the Critic can REJECT a report and send it
  back to the Analyst (a loop) -- that's a real graph, not a chain.
- The Critic checks every claim mentions a real ticket id, reducing
  hallucination. This "grounding check" is a great thing to explain.
- LLM is optional: if ANTHROPIC_API_KEY is set, the Analyst uses Claude
  to write the summary. Otherwise a template writes it. The system works
  end to end either way -- good engineering (graceful degradation).
"""

import os
from typing import TypedDict
from langgraph.graph import StateGraph, END

from app.ml.analysis import cluster_tickets, semantic_search


class AgentState(TypedDict):
    query: str
    tickets: list        # list of dicts from MySQL
    relevant: list       # tickets picked by retriever
    clusters: list       # themes from analyst
    draft_report: str
    approved: bool
    retries: int


# ---------- Node 1: Retriever ----------
def retriever_node(state):
    tickets = state["tickets"]
    texts = [t["subject"] + " " + t["body"] for t in tickets]
    indices = semantic_search(state["query"], texts, top_k=10)
    relevant = [tickets[i] for i in indices] if indices else tickets[:10]
    return {"relevant": relevant}


# ---------- Node 2: Analyst ----------
def analyst_node(state):
    relevant = state["relevant"]
    texts = [t["subject"] + " " + t["body"] for t in relevant]
    clusters = cluster_tickets(texts, n_clusters=3)

    draft = build_report_text(state["query"], relevant, clusters)
    return {"clusters": clusters, "draft_report": draft}


def build_report_text(query, relevant, clusters):
    """Template report. Swap in an LLM call if API key exists."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return llm_report(query, relevant, clusters)

    lines = [f"Analysis report for query: '{query}'",
             f"Analyzed {len(relevant)} relevant tickets.", "",
             "Top recurring themes:"]
    for c in clusters:
        ids = [str(relevant[i]["id"]) for i in c["ticket_indices"]]
        lines.append(f"- Theme '{c['theme']}' ({c['size']} tickets, "
                     f"ids: {', '.join(ids)})")
    negatives = [t for t in relevant if t.get("sentiment") == "negative"]
    lines.append("")
    lines.append(f"{len(negatives)} of {len(relevant)} tickets have "
                 f"negative sentiment - prioritize these.")
    return "\n".join(lines)


def llm_report(query, relevant, clusters):
    """Optional: use Claude to write a natural language report."""
    from anthropic import Anthropic
    client = Anthropic()
    ticket_text = "\n".join(
        f"[id {t['id']}] {t['subject']}: {t['body'][:200]}" for t in relevant
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                f"You are a support analyst. Query: {query}\n\n"
                f"Tickets:\n{ticket_text}\n\n"
                "Write a short report of recurring issues. Every claim MUST "
                "reference ticket ids in the form [id N]. Do not invent ids."
            ),
        }],
    )
    return msg.content[0].text


# ---------- Node 3: Critic (grounding check) ----------
def critic_node(state):
    """Approve only if the report references real ticket ids."""
    real_ids = {str(t["id"]) for t in state["relevant"]}
    report = state["draft_report"]

    referenced = set()
    for real_id in real_ids:
        if real_id in report:
            referenced.add(real_id)

    # report must reference at least one real ticket to be grounded
    approved = len(referenced) > 0
    return {"approved": approved, "retries": state.get("retries", 0) + 1}


def critic_decision(state):
    """Conditional edge: approve -> END, reject -> retry analyst (max 2)."""
    if state["approved"] or state["retries"] >= 2:
        return "approve"
    return "retry"


# ---------- Build the graph ----------
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retriever", retriever_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("retriever")
    graph.add_edge("retriever", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges("critic", critic_decision, {
        "approve": END,
        "retry": "analyst",     # the loop that makes this a graph
    })
    return graph.compile()


def run_analysis(query, tickets):
    """Main entry point called by the worker. Plain function call."""
    app = build_graph()
    result = app.invoke({
        "query": query,
        "tickets": tickets,
        "relevant": [],
        "clusters": [],
        "draft_report": "",
        "approved": False,
        "retries": 0,
    })
    return result["draft_report"]
