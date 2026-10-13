"""Command-line interface for EngiAgent.

Usage:
    python main.py                     # interactive session
    python main.py "your question"     # one-shot
    python main.py --reflect           # enable the self-review pass
"""
import argparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from engiagent import EngiAgent


def main():
    parser = argparse.ArgumentParser(description="EngiAgent - engineering problem-solving agent")
    parser.add_argument("question", nargs="?", help="one-shot question (omit for interactive mode)")
    parser.add_argument("--reflect", action="store_true", help="review the final answer before returning it")
    parser.add_argument("--quiet", action="store_true", help="hide thought/action/observation trace")
    parser.add_argument("--max-steps", type=int, default=12)
    args = parser.parse_args()

    agent = EngiAgent(reflect=args.reflect, verbose=not args.quiet, max_steps=args.max_steps)

    if args.question:
        print(agent.run(args.question))
        return

    print("EngiAgent ready. Type 'exit' to quit.")
    while True:
        try:
            question = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            print(f"\nagent> {agent.run(question)}")


if __name__ == "__main__":
    main()
