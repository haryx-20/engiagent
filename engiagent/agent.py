"""EngiAgent: a tool-using agent with planning, memory, guardrails and optional self-review."""
import os

from anthropic import Anthropic

from .memory import NoteMemory
from .tools import ToolBox

SYSTEM_PROMPT = """You are EngiAgent, an engineering problem-solving agent focused on mechanical engineering.

Work like this:
1. For any task needing more than one calculation, call create_plan first (2-6 steps).
2. Execute the plan with tools. NEVER do arithmetic in your head: use calculator, unit_convert or beam_analysis.
3. Call mark_step_done after each step.
4. Use material_lookup for material properties instead of guessing, and state that values are typical handbook values.
5. Use save_note for results worth keeping and recall_notes when the user refers to earlier work.
6. If a tool returns an error, read it, fix the input and retry once before asking the user.
7. Finish with a short answer: result, key assumptions, units, and a one-line sanity check
   (e.g. compare stress with yield strength and give a safety factor).
Be concise. Ask a question only when a required input is truly missing."""


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


class EngiAgent:
    def __init__(self, client=None, model=None, max_steps=12, memory_path="memory/notes.json",
                 reflect=False, verbose=True):
        self.client = client or Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        self.model = model or os.getenv("ENGIAGENT_MODEL", "claude-sonnet-5-5")
        self.max_steps = max_steps
        self.reflect = reflect
        self.verbose = verbose
        self.toolbox = ToolBox(NoteMemory(memory_path))
        self.messages: list = []  # short-term memory: the running conversation

    def _log(self, tag: str, text: str):
        if self.verbose:
            print(f"[{tag}] {text[:400]}")

    def run(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        for step in range(1, self.max_steps + 1):
            response = self.client.messages.create(
                model=self.model, max_tokens=2048, system=SYSTEM_PROMPT,
                tools=self.toolbox.schemas, messages=self.messages)
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                answer = _text(response)
                return self._review(user_input, answer) if self.reflect else answer

            if _text(response):
                self._log(f"thought {step}", _text(response))
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                self._log(f"action {step}", f"{block.name}({block.input})")
                output, is_error = self.toolbox.run(block.name, block.input)
                self._log(f"observation {step}", output)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output, "is_error": is_error})
            self.messages.append({"role": "user", "content": results})

        return f"Stopped after {self.max_steps} steps without a final answer. Try a narrower question."

    def _review(self, question: str, answer: str) -> str:
        """Reflection: a second pass that checks the draft for unit, logic or arithmetic errors."""
        self._log("reflect", "reviewing draft answer")
        review = self.client.messages.create(
            model=self.model, max_tokens=1024,
            system="You are a strict engineering reviewer. Check units, formulas and sanity of results.",
            messages=[{"role": "user", "content": (
                f"Question:\n{question}\n\nDraft answer:\n{answer}\n\n"
                "If the draft has no errors reply with exactly: OK\n"
                "Otherwise reply with the corrected final answer only.")}])
        verdict = _text(review)
        return answer if verdict == "OK" else verdict
