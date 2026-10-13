import json
import pytest
from engiagent.memory import NoteMemory
from engiagent.tools import ToolBox, safe_eval, unit_convert, material_lookup, beam_analysis


def test_calculator_basic():
    assert safe_eval("2 + 3 * 4") == 14
    assert safe_eval("sqrt(16) + pi") == pytest.approx(4 + 3.14159265, rel=1e-6)


@pytest.mark.parametrize("bad", ["__import__('os').system('ls')", "open('x')", "2**9999", "a + 1"])
def test_calculator_rejects_unsafe(bad):
    with pytest.raises(Exception):
        safe_eval(bad)


def test_unit_convert():
    assert unit_convert(1, "in", "mm")["result"] == pytest.approx(25.4)
    assert unit_convert(1, "hp", "kW")["result"] == pytest.approx(0.7457, rel=1e-3)
    assert unit_convert(100, "C", "F")["result"] == pytest.approx(212)
    assert unit_convert(1000, "psi", "MPa")["result"] == pytest.approx(6.8948, rel=1e-3)
    with pytest.raises(ValueError):
        unit_convert(1, "m", "kg")


def test_material_lookup():
    assert "Aluminium 6061-T6" in material_lookup("6061")["matches"]
    assert material_lookup("unobtainium")["matches"] == {}


def test_beam_simply_supported_center_point():
    r = beam_analysis("simply_supported_center_point", 1.0, 1000, 205, 20, 40)
    assert r["max_moment_Nm"] == pytest.approx(250)
    assert r["max_deflection_mm"] == pytest.approx(0.9527, rel=1e-3)
    assert r["max_bending_stress_MPa"] == pytest.approx(46.875, rel=1e-4)


def test_beam_cantilever_end_point():
    r = beam_analysis("cantilever_end_point", 0.5, 200, 68.9, 10, 20)
    assert r["max_moment_Nm"] == pytest.approx(100)
    # delta = P L^3 / (3 E I), I = 0.01*0.02^3/12
    I = 0.01 * 0.02**3 / 12
    assert r["max_deflection_mm"] == pytest.approx(200 * 0.5**3 / (3 * 68.9e9 * I) * 1000, rel=1e-6)


def test_beam_invalid_input():
    with pytest.raises(ValueError):
        beam_analysis("nonsense", 1, 1, 1, 1, 1)


def test_toolbox_plan_and_errors(tmp_path):
    tb = ToolBox(NoteMemory(str(tmp_path / "n.json")))
    out, err = tb.run("create_plan", {"steps": ["a", "b"]})
    assert not err and len(tb.plan) == 2
    tb.run("mark_step_done", {"index": 1, "result": "ok"})
    assert tb.plan[0]["done"] is True
    _, err = tb.run("mark_step_done", {"index": 9, "result": "x"})
    assert err
    _, err = tb.run("no_such_tool", {})
    assert err
    _, err = tb.run("calculator", {"expression": "1/0"})
    assert err


def test_memory_persists(tmp_path):
    path = str(tmp_path / "n.json")
    tb = ToolBox(NoteMemory(path))
    tb.run("save_note", {"text": "shaft diameter 25 mm", "tag": "design"})
    tb2 = ToolBox(NoteMemory(path))          # new session, same file
    out, _ = tb2.run("recall_notes", {"query": "shaft"})
    assert "25 mm" in json.loads(out)["notes"][0]["text"]
