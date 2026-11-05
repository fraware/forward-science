#!/usr/bin/env python3
"""Prepare exact-text narration scripts and bounded TTS segments.

This command produces *text only*. It never manufactures an audio file or
marks a narrated edition as reviewed. Audio publication is separately gated
by content/audio.json and requires editorial listening/quality control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
FOOTER = 'https://mateopetel.substack.com/subscribe?'


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compile_narration(root: Path, output: Path, *, max_chars: int = 2400) -> dict:
    if max_chars < 2000:
        raise ValueError('max_chars must allow complete source paragraphs')
    manifest = json.loads((root/'content/essays.json').read_text(encoding='utf-8'))
    provenance = json.loads((root/'content/import-provenance.json').read_text(encoding='utf-8'))
    if len(manifest) != 6 or len(provenance) != 6:
        raise ValueError('Expected six verified author manuscripts')
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for essay, record in zip(manifest, provenance, strict=True):
        path = root/'content/essays'/f'{essay["slug"]}.html'
        raw = path.read_text(encoding='utf-8').strip()
        if essay['slug'] != record['slug'] or checksum(raw.encode()) != record['rendered_sha256']:
            raise ValueError(f'Imported author source mismatch: {essay["slug"]}')
        soup = BeautifulSoup(raw,'html.parser')
        paragraphs = soup.find_all('p',recursive=False)
        if paragraphs and paragraphs[-1].find('a',href=FOOTER):
            paragraphs.pop()
        text_paragraphs = [p.get_text(' ', strip=True) for p in paragraphs]
        if not text_paragraphs or any(not p for p in text_paragraphs):
            raise ValueError(f'Empty narration paragraph: {essay["slug"]}')
        if any(len(p)>max_chars for p in text_paragraphs):
            raise ValueError(f'An original paragraph exceeds maximum segment length: {essay["slug"]}')
        body='\n\n'.join(text_paragraphs)+'\n'
        slug=essay['slug']
        (output/f'{slug}.txt').write_text(body,encoding='utf-8')
        segments=[]
        pending=[]
        for p in text_paragraphs:
            if pending and len('\n\n'.join(pending))+2+len(p)>max_chars:
                segments.append('\n\n'.join(pending)+'\n')
                pending=[]
            pending.append(p)
        if pending:
            segments.append('\n\n'.join(pending)+'\n')
        (output/'segments').mkdir(exist_ok=True)
        files=[]
        for number,segment in enumerate(segments, start=1):
            filename=f'segments/{slug}-{number:02d}.txt'
            (output/filename).write_text(segment,encoding='utf-8')
            files.append({'path':filename,'sha256':checksum(segment.encode()),'characters':len(segment)})
        if '\n\n'.join(x.rstrip('\n') for x in segments)+'\n' != body:
            raise ValueError('Narration segments failed exact-text reconstruction')
        records.append({'slug':slug,'title':essay['title'],'subtitle':essay['subtitle'],
                        'original_url':essay['original_url'],'source_sha256':record['rendered_sha256'],
                        'spoken_body_sha256':checksum(body.encode()), 'paragraphs':len(text_paragraphs),
                        'word_count':sum(len(p.split()) for p in text_paragraphs), 'segments':files})
    report={'series':'Forward Science','author':'Mateo H. Petel','status':'text prepared; recordings unproduced',
            'format':'UTF-8 source text preserving original paragraph wording and inline link labels',
            'essays':records}
    (output/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output/'NARRATION_NOTES.md').write_text('''# Forward Science — Narration production notes

The six supplied text editions reproduce the verified article bodies, excluding the original Substack subscription footer. The chapter title and subtitle are available in `manifest.json` for a spoken introduction. Link labels are present in the spoken text; link destinations remain in the source HTML and downloadable publications. Segments are bounded at paragraph boundaries so no original sentence is divided.

Do not publish an audio file from this package without listening review. Check complete wording against the original, pronunciation of scientific terminology and names, normal volume, silence duration, acoustic artifacts, punctuation, and end-of-file truncation. Review each chapter from beginning to end, with special attention to transitions across segments. Confirm that any title/introduction added during narration is explicitly recorded as an addition. Record the chosen narrator or synthetic-voice provider in public metadata.

Encode approved audio as a compatible MP3, provide its SHA-256 in `content/audio.json`, and test playback/scrubbing/seek/resume on representative browsers and mobile devices. The site intentionally hides its player until a verified media file exists.
''', encoding='utf-8')
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path,default=ROOT/'narration-work')
    parser.add_argument('--max-chars',type=int,default=2400)
    args=parser.parse_args()
    result=compile_narration(args.root,args.out,max_chars=args.max_chars)
    print('Prepared',len(result['essays']),'narration manuscripts and',
          sum(len(x['segments']) for x in result['essays']),'source-faithful segments')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
