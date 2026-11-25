#!/usr/bin/env python3
"""公開サイトのトップページ(ダウンロード一覧)を作る。
使い方: make_index.py <サイトのフォルダ>   (サイトのフォルダに slides/ と subtitles/ がある前提)"""
import json, pathlib, re, sys, html
ROOT = pathlib.Path(__file__).resolve().parent.parent
site = pathlib.Path(sys.argv[1])

def title_of(stem):
    s = re.sub(r'^_+', '', stem); s = re.sub(r'^Arch1001_', '', s)
    return s.replace('_', ' ')

chapters = {}
for kind, ext, sub in (('pptx', '.ja.pdf', 'slides'), ('srt', '.ja.srt', 'subtitles')):
    for p in sorted((ROOT / 'data' / kind).glob('*.json')):
        d = json.loads(p.read_text(encoding='utf-8')); src = pathlib.Path(d['source'])
        f = site / sub / src.parent / (src.stem + ext)
        if not f.exists(): continue
        ch = src.parent.as_posix()
        stem = title_of(src.stem)
        chapters.setdefault(ch, {}).setdefault((stem if kind == 'srt' else stem), {})[kind] = f.relative_to(site).as_posix()

rows = []
for ch in sorted(chapters):
    rows.append(f'<h2>{html.escape(re.sub(r"^\d+_", "", ch).replace("_", " "))}</h2><ul>')
    for name, d in sorted(chapters[ch].items()):
        links = []
        if 'pptx' in d: links.append(f'<a href="{html.escape(d["pptx"])}">スライド（PDF）</a>')
        if 'srt' in d: links.append(f'<a href="{html.escape(d["srt"])}" download>字幕（.srt）</a>')
        rows.append(f'<li>{html.escape(name)} — {" / ".join(links)}</li>')
    rows.append('</ul>')

page = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Architecture 1001: x86-64 Assembly（日本語訳）</title>
<style>
body{{font:16px/1.8 Roboto,"Noto Sans JP",system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#000}}
h1{{font-size:2rem}} h2{{margin-top:2rem;font-size:1.3rem;border-bottom:1px solid #e2e2e2}}
.notice{{background:#f4f4f4;border:1px solid #e2e2e2;border-radius:8px;padding:12px 16px;font-size:14px}}
a{{color:#000}} li{{margin:.2rem 0}}
</style></head><body>
<h1>Architecture 1001: x86-64 Assembly（日本語訳）</h1>
<div class="notice">
<p>これは、Xeno Kovah の講義 <a href="https://ost2.fyi/Arch1001">Architecture 1001: x86-64 Assembly</a>（OpenSecurityTraining2）の<strong>非公式の日本語訳</strong>です。原著者・OpenSecurityTraining2 とは関係がありません。</p>
<p>ライセンス: <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ja">CC BY-SA 4.0</a>。翻訳も同じライセンスで公開します。</p>
<p><em>This material is derived from Xeno Kovah's "Architecture 1001: x86-64 Assembly" class, available at https://ost2.fyi/Arch1001</em></p>
<p>原文の資料: <a href="https://gitlab.com/opensecuritytraining/arch1001_x86-64_asm_slides_and_subtitles">スライドと字幕（公式の GitLab）</a> ／ 訳のソース: <a href="https://github.com/0xFF-MinusOne/ost2-arch1001-ja">0xFF-MinusOne/ost2-arch1001-ja</a>（誤訳は issue で）</p>
<p>動画は <a href="https://ost2.fyi/Arch1001">コースのページ</a>で見られます。字幕（.srt）は、動画プレーヤーに読み込ませて使えます。</p>
</div>
{"".join(rows)}
</body></html>'''
(site / 'index.html').write_text(page, encoding='utf-8')
print('index.html:', sum(len(v) for v in chapters.values()), '項目')
