"""Generates docs/EngiAgent_schema.pdf (one-page architecture diagram). Run: python docs/make_schema_pdf.py"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor, black
from reportlab.pdfgen import canvas

OUT = "docs/EngiAgent_schema.pdf"
W, H = landscape(A4)
c = canvas.Canvas(OUT, pagesize=(W, H))
c.setTitle("EngiAgent - Architecture and Schema")


def box(x, y, w, h, lines, fill="#EAF2FB", stroke="#2F5D8A", size=8.5, bold_first=True):
    c.setFillColor(HexColor(fill)); c.setStrokeColor(HexColor(stroke)); c.setLineWidth(1)
    c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
    c.setFillColor(black)
    line_h = size + 3
    top = y + h / 2 + (len(lines) - 1) * line_h / 2 - size / 3
    for i, text in enumerate(lines):
        c.setFont("Helvetica-Bold" if (i == 0 and bold_first) else "Helvetica", size)
        c.drawCentredString(x + w / 2, top - i * line_h, text)


def arrow(x1, y1, x2, y2, label=None, lx=0, ly=4, color="#444444", dash=False):
    import math
    c.setStrokeColor(HexColor(color)); c.setFillColor(HexColor(color)); c.setLineWidth(1.2)
    c.setDash(3, 2) if dash else c.setDash()
    c.line(x1, y1, x2, y2); c.setDash()
    ang = math.atan2(y2 - y1, x2 - x1); s = 6
    p = c.beginPath(); p.moveTo(x2, y2)
    p.lineTo(x2 - s * math.cos(ang - 0.4), y2 - s * math.sin(ang - 0.4))
    p.lineTo(x2 - s * math.cos(ang + 0.4), y2 - s * math.sin(ang + 0.4)); p.close()
    c.drawPath(p, fill=1, stroke=0)
    if label:
        c.setFont("Helvetica-Oblique", 7.5); c.setFillColor(black)
        c.drawCentredString((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label)


# title
c.setFont("Helvetica-Bold", 16); c.setFillColor(HexColor("#1B3A57"))
c.drawString(30, H - 38, "EngiAgent - Agentic AI for Engineering Problem Solving")
c.setFont("Helvetica", 9.5); c.setFillColor(HexColor("#555555"))
c.drawString(30, H - 54, "Architecture and schema: ReAct-style loop (plan - act - observe - reflect) with tools and memory")

# left column
box(30, 470, 120, 40, ["User", "terminal question"], fill="#FFF4D6", stroke="#B8860B")
box(30, 390, 120, 40, ["main.py (CLI)", "interactive / one-shot"])
arrow(90, 470, 90, 430)

# agent
box(210, 380, 220, 130, ["EngiAgent loop (agent.py)", "1. Plan  2. Act  3. Observe", "4. Repeat until no tool call",
                         "(guardrail: max_steps = 12)", "5. Reflect (optional)", "",
                         "Short-term memory:", "running message history"], fill="#DDEBFA")
arrow(150, 422, 210, 422, "question", ly=4)
arrow(210, 398, 150, 398, "answer", ly=-11)

# LLM
box(570, 420, 230, 90, ["Claude API (tool use)", "input: system prompt + tool schemas",
                        "+ conversation history", "output: thought text + tool_use blocks"],
    fill="#F3E5F5", stroke="#7B3F8C")
arrow(430, 485, 570, 485, "messages + tools", ly=4)
arrow(570, 445, 430, 445, "thought / tool_use", ly=-11)

# reflection
box(470, 300, 160, 50, ["Reflection pass (--reflect)", "reviews units, logic, sanity"], fill="#FDEBD0", stroke="#B9770E")
arrow(400, 380, 500, 350, "draft answer", lx=-8, ly=6, dash=True)

# toolbox
c.setFillColor(HexColor("#F4F9F1")); c.setStrokeColor(HexColor("#3B7A3B")); c.roundRect(210, 55, 400, 195, 6, fill=1, stroke=1)
c.setFillColor(black); c.setFont("Helvetica-Bold", 9)
c.drawString(220, 233, "ToolBox (tools.py): dispatch, JSON schemas, errors returned as is_error")
tools = [("calculator", "AST-whitelisted, no eval()"), ("unit_convert", "length, mass, force, pressure,..."),
         ("material_lookup", "6 common alloys"), ("beam_analysis", "4 load cases, rect. section"),
         ("create_plan / mark_step_done", "planning state"), ("save_note / recall_notes", "long-term memory")]
for i, (name, sub) in enumerate(tools):
    col, row = i % 2, i // 2
    box(220 + col * 195, 175 - row * 52, 185, 42, [name, sub], fill="#E3F1DC", stroke="#3B7A3B", size=8)
arrow(290, 380, 290, 250, "tool call (action)", lx=-52, ly=0)
arrow(380, 250, 380, 380, "tool_result (observation)", lx=62, ly=-30)

# memory
box(660, 75, 140, 60, ["memory/notes.json", "long-term memory", "(persists across sessions)"], fill="#E8F8F5", stroke="#16A085", size=8)
arrow(605, 105, 660, 105)
arrow(660, 120, 605, 120)

# guardrails
box(30, 80, 160, 190, ["Guardrails", "", "- step limit stops loops", "- calculator uses AST", "  whitelist, bounded powers",
                       "- tool errors go back to", "  the model, no crash", "- API key in .env",
                       "  (git-ignored)", "- optional self-review"], fill="#FDEDEC", stroke="#C0392B", size=8)

# footer
c.setFont("Helvetica", 7.5); c.setFillColor(HexColor("#666666"))
c.drawString(30, 30, "Tool schemas: docs/tool_schema.json   |   Code: GitHub repository   |   Tests: pytest (16 passing, scripted fake LLM)")
c.save()
print("wrote", OUT)
