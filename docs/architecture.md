# EngiAgent - Architecture & Schema

```mermaid
flowchart TD
    U([User]) -->|question| CLI[main.py CLI]
    CLI --> A[EngiAgent loop<br/>agent.py]
    A -->|system prompt + tools + history| LLM[(Claude API<br/>tool use)]
    LLM -->|text: thought| A
    LLM -->|tool_use: action| A
    A -->|dispatch| TB[ToolBox<br/>tools.py]
    TB --> T1[calculator<br/>AST-safe]
    TB --> T2[unit_convert]
    TB --> T3[material_lookup]
    TB --> T4[beam_analysis]
    TB --> T5[create_plan /<br/>mark_step_done]
    TB --> T6[save_note /<br/>recall_notes]
    T6 <--> M[(memory/notes.json<br/>long-term memory)]
    TB -->|tool_result: observation| A
    A -->|history list<br/>short-term memory| A
    A -->|optional| R[Reflection pass<br/>reviews draft]
    R --> A
    A -->|final answer| CLI --> U
```

## Agentic loop (ReAct-style)

1. **Plan** - the model calls `create_plan` for multi-step tasks.
2. **Act** - the model emits `tool_use` blocks; `ToolBox.run` executes them.
3. **Observe** - results (or errors, flagged `is_error`) are returned as `tool_result` blocks.
4. **Repeat** until the model stops calling tools, or `max_steps` is hit.
5. **Reflect** (optional `--reflect`) - a second call reviews the draft answer.

## Guardrails

- Step limit (`max_steps`, default 12) prevents infinite loops.
- Calculator uses a whitelisted AST evaluator - no `eval()`, no imports, bounded exponents.
- Tool errors never crash the agent; they are returned to the model so it can retry.
- API key lives in `.env` (git-ignored), never in code.

Tool JSON schemas: [`tool_schema.json`](tool_schema.json).
