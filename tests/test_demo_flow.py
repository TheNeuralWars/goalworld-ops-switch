from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.runner import build_stack, route


def test_approval_roundtrip(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    # use real policy but isolate approval store via monkeypatch of evidence path
    _, scout, gate, scribe, store = build_stack(root)
    outs = route("draft submission text for the hackathon", scout, gate, scribe)
    assert any("APPROVAL REQUIRED" in o for o in outs)
    pending = store.pending()
    assert pending
    aid = pending[0].approval_id
    outs2 = route(f"approve {aid}", scout, gate, scribe)
    assert any("approved" in o.lower() for o in outs2)
