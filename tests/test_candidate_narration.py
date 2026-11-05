"""Candidate TTS chunking preserves source wording without depending on a model."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "candidate_narration", ROOT / "scripts/generate_narration_candidate.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("limit", [100, 180, 330])
def test_chunking_preserves_all_words_and_order(limit):
    text = "The scientific loop advances through a question, experiment, and review. " * 50
    chunks = module.text_chunks(text, limit)
    assert len(chunks) > 2
    assert all(0 < len(p) <= limit for p in chunks)
    assert " ".join(chunks) == " ".join(text.split())


def test_chunking_fails_on_unrepresentable_input():
    with pytest.raises(ValueError):
        module.text_chunks(" ")
    with pytest.raises(ValueError):
        module.text_chunks("a" * 100, limit=80)


def test_narration_candidate_uses_verified_source_text(tmp_path):
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from prepare_narration import compile_narration
    manifest = compile_narration(ROOT, tmp_path / "manuscripts")
    original = next(e for e in manifest["essays"] if e["slug"] == "forward-science")
    assert original["segments"]
    text = (tmp_path / "manuscripts/forward-science.txt").read_text(encoding="utf-8")
    sample = " ".join(text.split("\n\n")[:2]).strip()
    chunks = module.text_chunks(sample)
    assert " ".join(chunks) == " ".join(sample.split())
