"""Long-term memory: a tiny JSON-backed notebook the agent can write to and search."""
import json
import time
from pathlib import Path


class NoteMemory:
    def __init__(self, path: str = "memory/notes.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.notes = json.loads(self.path.read_text()) if self.path.exists() else []

    def save(self, text: str, tag: str = "general") -> dict:
        note = {
            "id": len(self.notes) + 1,
            "tag": tag,
            "text": text,
            "time": time.strftime("%Y-%m-%d %H:%M"),
        }
        self.notes.append(note)
        self.path.write_text(json.dumps(self.notes, indent=2))
        return note

    def search(self, query: str = "") -> list:
        q = query.lower().strip()
        return [n for n in self.notes if not q or q in n["text"].lower() or q in n["tag"].lower()]
