"""Tests the agent loop with a scripted fake LLM (no API key or network needed)."""
from types import SimpleNamespace as NS
from engiagent.agent import EngiAgent


class FakeClient:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = 0
        self.messages = NS(create=self._create)

    def _create(self, **kwargs):
        self.calls += 1
        return next(self._responses)


def tool_turn(name, args, tid="t1"):
    return NS(stop_reason="tool_use",
              content=[NS(type="text", text="thinking"), NS(type="tool_use", id=tid, name=name, input=args)])


def final_turn(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


def test_agent_uses_tool_then_answers(tmp_path):
    client = FakeClient([tool_turn("calculator", {"expression": "12*12"}), final_turn("It is 144.")])
    agent = EngiAgent(client=client, memory_path=str(tmp_path / "n.json"), verbose=False)
    assert agent.run("what is 12 squared?") == "It is 144."
    tool_result = agent.messages[2]["content"][0]
    assert tool_result["type"] == "tool_result" and "144" in tool_result["content"]
    assert tool_result["is_error"] is False


def test_agent_recovers_from_tool_error(tmp_path):
    client = FakeClient([tool_turn("calculator", {"expression": "1/0"}),
                         tool_turn("calculator", {"expression": "1/2"}, "t2"), final_turn("0.5")])
    agent = EngiAgent(client=client, memory_path=str(tmp_path / "n.json"), verbose=False)
    assert agent.run("1/0?") == "0.5"
    assert agent.messages[2]["content"][0]["is_error"] is True


def test_step_limit_guardrail(tmp_path):
    client = FakeClient([tool_turn("calculator", {"expression": "1+1"}, f"t{i}") for i in range(5)])
    agent = EngiAgent(client=client, memory_path=str(tmp_path / "n.json"), verbose=False, max_steps=3)
    assert "Stopped after 3 steps" in agent.run("loop forever")
    assert client.calls == 3


def test_reflection_can_correct_answer(tmp_path):
    client = FakeClient([final_turn("wrong"), final_turn("corrected")])
    agent = EngiAgent(client=client, memory_path=str(tmp_path / "n.json"), verbose=False, reflect=True)
    assert agent.run("q") == "corrected"
