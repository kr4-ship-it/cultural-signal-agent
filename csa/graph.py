from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import State, after_critic, answer, approve, critic, draft, retrieve, revise, route


def build(checkpointer=None):
    g = StateGraph(State)
    g.add_node("route", route)
    g.add_node("retrieve", retrieve)
    g.add_node("draft", draft)
    g.add_node("critic", critic)
    g.add_node("revise", revise)
    g.add_node("approve", approve)
    g.add_node("answer", answer)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", lambda s: "answer" if s["intent"] == "not_found" else "retrieve",
                            {"answer": "answer", "retrieve": "retrieve"})
    g.add_edge("retrieve", "draft")
    g.add_edge("draft", "critic")
    g.add_conditional_edges("critic", after_critic, {"revise": "revise", "approve": "approve"})
    g.add_edge("revise", "critic")
    g.add_edge("approve", "answer")
    g.add_edge("answer", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def ask(question: str, thread: str = "default", require_approval: bool = False) -> dict:
    app = build()
    cfg = {"configurable": {"thread_id": thread, "require_approval": require_approval}}
    return app.invoke({"question": question}, cfg)
