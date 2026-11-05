"""Full-series candidate audio segmentation must preserve every source word."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "full_audio_candidate", ROOT / "scripts/generate_all_audio_candidates.py"
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_segments_respect_paragraph_order_and_text_integrity(tmp_path):
    from sys import path as syspath
    syspath.insert(0, str(ROOT / "scripts"))
    from prepare_narration import compile_narration
    compiled = compile_narration(ROOT, tmp_path / "narration")
    assert len(compiled["essays"]) == 6
    for essay in compiled["essays"]:
        text = (tmp_path / "narration" / f"{essay['slug']}.txt").read_text(encoding="utf-8")
        parts = module.segments_for(text, 850)
        assert all(0 < len(t) <= 850 for t, _ in parts)
        assert " ".join(p for p, _ in parts) == " ".join(text.split())
        assert sum(end for _, end in parts) == len(text.strip().split("\n\n"))
        assert len(parts) >= 1
