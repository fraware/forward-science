"""Narration manuscript integrity and safe segmentation checks."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fs_narration', ROOT/'scripts/prepare_narration.py')
assert SPEC and SPEC.loader
narration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(narration)


def test_narration_compiles_exact_sources_into_bounded_segments(tmp_path: Path) -> None:
    """Six manuscripts reconstruct exactly from whole-paragraph speech segments."""
    report=narration.compile_narration(ROOT,tmp_path)
    assert len(report['essays']) == 6
    assert all(0 < len(e['segments']) < 20 for e in report['essays'])
    assert all(e['word_count'] >= 300 for e in report['essays'])
    for essay in report['essays']:
        body = (tmp_path / f'{essay["slug"]}.txt').read_text(encoding='utf-8')
        assert hashlib.sha256(body.encode()).hexdigest()==essay['spoken_body_sha256']
        parts=[(tmp_path/item['path']).read_text(encoding='utf-8') for item in essay['segments']]
        assert '\n\n'.join(x.rstrip('\n') for x in parts)+'\n'==body
        assert all(len(x) <= 2400 for x in parts)
        assert 'Subscribe now' not in body
    assert report['status']=='text prepared; recordings unproduced'


def test_narration_rejects_unverified_article_modifications(tmp_path: Path) -> None:
    """An altered article fails before narration source files are created."""
    root=tmp_path/'source'
    shutil.copytree(ROOT/'content',root/'content')
    target=root/'content/essays/forward-science.html'
    target.write_text(target.read_text(encoding='utf-8')+'<p>tampered</p>',encoding='utf-8')
    with pytest.raises(ValueError,match='source mismatch'):
        narration.compile_narration(root,tmp_path/'output')
    assert not (tmp_path/'output'/'forward-science.txt').exists()
