"""Tools the agent can call. Every tool is a plain Python function + a JSON schema."""
import ast
import json
import math
import operator

from .memory import NoteMemory

# ----------------------------------------------------------------- calculator
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {n: getattr(math, n) for n in (
    "sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "log", "log10", "exp", "radians", "degrees", "fabs")}
_FUNCS.update(abs=abs, round=round, min=min, max=max)
_CONSTS = {"pi": math.pi, "e": math.e}


def safe_eval(expr: str) -> float:
    """Evaluate a math expression without eval(): only whitelisted AST nodes run."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            left, right = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](left, right)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UNARY:
            return _UNARY[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Name) and n.id in _CONSTS:
            return _CONSTS[n.id]
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in _FUNCS and not n.keywords):
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise ValueError("unsupported element in expression")
    return ev(ast.parse(expr.strip(), mode="eval"))


def calculator(expression: str) -> dict:
    return {"expression": expression, "result": safe_eval(expression)}


# ------------------------------------------------------------ unit conversion
_UNITS = {
    "length": {"m": 1, "mm": 1e-3, "cm": 1e-2, "km": 1e3, "in": 0.0254, "ft": 0.3048},
    "mass": {"kg": 1, "g": 1e-3, "lb": 0.45359237, "tonne": 1000},
    "force": {"N": 1, "kN": 1e3, "lbf": 4.4482216152605, "kgf": 9.80665},
    "pressure": {"Pa": 1, "kPa": 1e3, "MPa": 1e6, "GPa": 1e9, "bar": 1e5,
                 "psi": 6894.757293168, "atm": 101325},
    "energy": {"J": 1, "kJ": 1e3, "Wh": 3600, "kWh": 3.6e6, "cal": 4.184, "BTU": 1055.056},
    "power": {"W": 1, "kW": 1e3, "hp": 745.6998715823, "PS": 735.49875},
    "speed": {"m/s": 1, "km/h": 1 / 3.6, "mph": 0.44704},
}


def _to_kelvin(v, u):
    return {"C": v + 273.15, "K": v, "F": (v - 32) * 5 / 9 + 273.15}[u]


def _from_kelvin(k, u):
    return {"C": k - 273.15, "K": k, "F": (k - 273.15) * 9 / 5 + 32}[u]


def unit_convert(value: float, from_unit: str, to_unit: str) -> dict:
    if from_unit in ("C", "F", "K") and to_unit in ("C", "F", "K"):
        out = _from_kelvin(_to_kelvin(value, from_unit), to_unit)
        return {"value": value, "from": from_unit, "to": to_unit, "result": out}
    for category, table in _UNITS.items():
        if from_unit in table and to_unit in table:
            out = value * table[from_unit] / table[to_unit]
            return {"category": category, "value": value, "from": from_unit,
                    "to": to_unit, "result": out}
    raise ValueError(f"cannot convert {from_unit} to {to_unit} (unknown or mixed units)")


# ------------------------------------------------------------- material data
# Typical room-temperature handbook values; always verify against a datasheet.
MATERIALS = {
    "AISI 1018 (cold drawn)":  {"density_kg_m3": 7870, "E_GPa": 205.0, "yield_MPa": 370, "uts_MPa": 440},
    "AISI 4140 (annealed)":    {"density_kg_m3": 7850, "E_GPa": 205.0, "yield_MPa": 415, "uts_MPa": 655},
    "Stainless 304 (annealed)": {"density_kg_m3": 8000, "E_GPa": 193.0, "yield_MPa": 215, "uts_MPa": 505},
    "Aluminium 6061-T6":       {"density_kg_m3": 2700, "E_GPa": 68.9, "yield_MPa": 276, "uts_MPa": 310},
    "Aluminium 7075-T6":       {"density_kg_m3": 2810, "E_GPa": 71.7, "yield_MPa": 503, "uts_MPa": 572},
    "Titanium Ti-6Al-4V":      {"density_kg_m3": 4430, "E_GPa": 113.8, "yield_MPa": 880, "uts_MPa": 950},
}


def material_lookup(query: str) -> dict:
    q = query.lower().strip()
    hits = {name: props for name, props in MATERIALS.items()
            if q in name.lower() or any(tok in name.lower() for tok in q.split())}
    if not hits:
        return {"matches": {}, "available": list(MATERIALS)}
    return {"matches": hits, "note": "typical handbook values; verify with a datasheet"}


# ------------------------------------------------------------ beam analysis
_BEAM_CASES = {
    # case: (max moment, max deflection) as functions of (load, L, EI)
    "simply_supported_center_point": (lambda w, L: w * L / 4, lambda w, L, EI: w * L**3 / (48 * EI)),
    "cantilever_end_point":          (lambda w, L: w * L,     lambda w, L, EI: w * L**3 / (3 * EI)),
    "simply_supported_udl":          (lambda w, L: w * L**2 / 8, lambda w, L, EI: 5 * w * L**4 / (384 * EI)),
    "cantilever_udl":                (lambda w, L: w * L**2 / 2, lambda w, L, EI: w * L**4 / (8 * EI)),
}


def beam_analysis(case: str, length_m: float, load: float, E_GPa: float,
                  width_mm: float, height_mm: float) -> dict:
    """Rectangular-section beam. `load` is N for point loads, N/m for UDL cases."""
    if case not in _BEAM_CASES:
        raise ValueError(f"case must be one of {list(_BEAM_CASES)}")
    if min(length_m, E_GPa, width_mm, height_mm) <= 0:
        raise ValueError("length, E and section dimensions must be positive")
    b, h = width_mm / 1000, height_mm / 1000
    I = b * h**3 / 12                      # m^4
    EI = E_GPa * 1e9 * I                   # N*m^2
    moment_fn, defl_fn = _BEAM_CASES[case]
    M = moment_fn(load, length_m)
    return {
        "case": case,
        "I_m4": I,
        "max_moment_Nm": M,
        "max_deflection_mm": defl_fn(load, length_m, EI) * 1000,
        "max_bending_stress_MPa": M * (h / 2) / I / 1e6,
    }


# ------------------------------------------------------------------- toolbox
SCHEMAS = [
    {"name": "create_plan",
     "description": "Record a short numbered plan (2-6 steps) BEFORE doing multi-step work.",
     "input_schema": {"type": "object", "properties": {
         "steps": {"type": "array", "items": {"type": "string"}}}, "required": ["steps"]}},
    {"name": "mark_step_done",
     "description": "Mark a plan step (1-based index) as completed, with a one-line result.",
     "input_schema": {"type": "object", "properties": {
         "index": {"type": "integer"}, "result": {"type": "string"}}, "required": ["index", "result"]}},
    {"name": "calculator",
     "description": "Evaluate a math expression. Supports + - * / ** %, sqrt, sin, cos, tan, log, exp, pi, e.",
     "input_schema": {"type": "object", "properties": {
         "expression": {"type": "string"}}, "required": ["expression"]}},
    {"name": "unit_convert",
     "description": "Convert between units: length, mass, force, pressure, energy, power, speed, temperature (C/F/K).",
     "input_schema": {"type": "object", "properties": {
         "value": {"type": "number"}, "from_unit": {"type": "string"}, "to_unit": {"type": "string"}},
         "required": ["value", "from_unit", "to_unit"]}},
    {"name": "material_lookup",
     "description": "Look up density, Young's modulus, yield and ultimate strength of common engineering materials.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "e.g. 'aluminium', '4140', 'titanium'"}}, "required": ["query"]}},
    {"name": "beam_analysis",
     "description": ("Max bending moment, max deflection and max bending stress of a rectangular-section beam. "
                     "SI inputs; load is N (point cases) or N/m (UDL cases)."),
     "input_schema": {"type": "object", "properties": {
         "case": {"type": "string", "enum": list(_BEAM_CASES)},
         "length_m": {"type": "number"}, "load": {"type": "number"}, "E_GPa": {"type": "number"},
         "width_mm": {"type": "number"}, "height_mm": {"type": "number"}},
         "required": ["case", "length_m", "load", "E_GPa", "width_mm", "height_mm"]}},
    {"name": "save_note",
     "description": "Save a fact or result to long-term memory so it can be recalled in later sessions.",
     "input_schema": {"type": "object", "properties": {
         "text": {"type": "string"}, "tag": {"type": "string"}}, "required": ["text"]}},
    {"name": "recall_notes",
     "description": "Search long-term memory notes. Empty query returns everything.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
]


class ToolBox:
    """Holds per-agent state (plan, memory) and dispatches tool calls safely."""

    def __init__(self, memory: NoteMemory):
        self.memory = memory
        self.plan: list = []
        self.schemas = SCHEMAS
        self._handlers = {
            "create_plan": self.create_plan,
            "mark_step_done": self.mark_step_done,
            "calculator": calculator,
            "unit_convert": unit_convert,
            "material_lookup": material_lookup,
            "beam_analysis": beam_analysis,
            "save_note": lambda text, tag="general": self.memory.save(text, tag),
            "recall_notes": lambda query="": {"notes": self.memory.search(query)},
        }

    def create_plan(self, steps: list) -> dict:
        self.plan = [{"step": s, "done": False, "result": ""} for s in steps]
        return {"plan": self.plan}

    def mark_step_done(self, index: int, result: str) -> dict:
        if not 1 <= index <= len(self.plan):
            raise ValueError(f"no step {index}; plan has {len(self.plan)} steps")
        self.plan[index - 1].update(done=True, result=result)
        return {"plan": self.plan}

    def run(self, name: str, args: dict):
        """Returns (json_text, is_error). Never raises: errors go back to the model."""
        handler = self._handlers.get(name)
        if handler is None:
            return json.dumps({"error": f"unknown tool '{name}'"}), True
        try:
            return json.dumps(handler(**args), default=str), False
        except Exception as exc:  # the model can read the error and retry
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}), True
