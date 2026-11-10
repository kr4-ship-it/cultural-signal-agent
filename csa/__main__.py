"""python -m csa "What connects Gaming and Fashion?" [--approve] [--trace]"""
import argparse
import uuid

from langgraph.types import Command

from .graph import build


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--approve", action="store_true", help="pause for human approval before answering")
    p.add_argument("--trace", action="store_true", help="print each node's step")
    a = p.parse_args()
    app = build()
    cfg = {"configurable": {"thread_id": str(uuid.uuid4()), "require_approval": a.approve}}
    out = app.invoke({"question": a.question}, cfg)
    if "__interrupt__" in out:
        pending = out["__interrupt__"][0].value
        print("Draft for review:")
        for c in pending["claims"] or []:
            print(" -", c["text"], c["cites"])
        out = app.invoke(Command(resume=input("Approve? [y/n] ")), cfg)
    if a.trace:
        print("\n".join(out.get("log", [])), "\n")
    print(out["answer"])


if __name__ == "__main__":
    main()
