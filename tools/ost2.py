#!/usr/bin/env python3
"""OST2 Arch1001 の翻訳ハーネス(字幕 srt とスライド pptx)。リポジトリのルートで実行する。

  extract-srt  <原文のフォルダ>     字幕を、文のまとまり(単位)に直して data/srt/*.json に書く
  extract-pptx <原文のフォルダ>     スライドの段落を取り出して data/pptx/*.json に書く(python-pptx が必要)
  status                          進み具合
  next  <srt|pptx> <名前> [件数]    未訳の単位を番号つきで出す
  apply <srt|pptx> <名前> <JSON>    訳を入れる。JSON は {"番号": "訳"}。値が null なら「訳さず原文のまま」
  build-srt <出力先>               訳した字幕を、元の時刻のまま、日本語の srt にする
  build-pptx <原文のフォルダ> <出力先>  訳をスライドに書き戻す(python-pptx が必要)
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
END = re.compile(r'[.?!]["\')\]]*$')
SOFT = 300   # この長さを超えたら、カンマ・コロンなどの位置で切る
HARD = 480   # これを超えたら、どこでも切る
PAUSE = re.compile(r'[,;:\u2014-]["\')\]]*$')

# ---------------------------------------------------------------- 字幕
def parse_srt(text):
    cues = []
    for blk in re.split(r'\n\s*\n', text.strip().replace('\r\n', '\n')):
        l = blk.split('\n')
        if len(l) >= 3 and '-->' in l[1]:
            a, b = [x.strip() for x in l[1].split('-->')]
            cues.append((a, b, ' '.join(x.strip() for x in l[2:]).strip()))
    return cues

def merge_cues(cues):
    units, buf, start = [], [], None
    for a, b, t in cues:
        if not t: continue
        if start is None: start = a
        buf.append(t); end = b
        s = ' '.join(buf)
        if END.search(t) or (len(s) > SOFT and PAUSE.search(t)) or len(s) > HARD:
            units.append({'i': len(units), 'start': start, 'end': end, 'en': s, 'ja': ''}); buf, start = [], None
    if buf:
        units.append({'i': len(units), 'start': start, 'end': end, 'en': ' '.join(buf), 'ja': ''})
    return units

def extract_srt(up):
    up = pathlib.Path(up); out = DATA / 'srt'; out.mkdir(parents=True, exist_ok=True); n = 0
    for f in sorted(up.rglob('*.srt')):
        rel = f.relative_to(up).as_posix()
        units = merge_cues(parse_srt(f.read_text(encoding='utf-8', errors='replace')))
        name = rel.replace('/', '__')[:-4]
        p = out / (name + '.json')
        if p.exists():   # すでに訳した分を残す(原文が同じ単位だけ)
            old = {u['en']: u['ja'] for u in json.loads(p.read_text(encoding='utf-8'))['units']}
            for u in units: u['ja'] = old.get(u['en'], '')
        p.write_text(json.dumps({'source': rel, 'units': units}, ensure_ascii=False, indent=0), encoding='utf-8'); n += len(units)
    print('字幕の単位:', n)

def ts_ms(s):
    h, m, r = s.split(':'); sec, ms = r.replace(',', '.').split('.')
    return ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(ms.ljust(3, '0')[:3])

PIECE = 40     # 1 つの字幕に出す文字数の上限(2 行ぶん)
LINE = 22      # 1 行の文字数の目安

def split_ja(text):
    """日本語を、句読点で、字幕 1 枚ぶん(PIECE 文字以内)に区切る。"""
    parts = [x for x in re.split(r'(?<=[。！？、，])', text.strip()) if x]
    out, cur = [], ''
    for x in parts:
        while len(x) > PIECE:                 # 句読点のない長い塊は、文字数で切る
            if cur: out.append(cur); cur = ''
            out.append(x[:PIECE]); x = x[PIECE:]
        if len(cur) + len(x) > PIECE and cur: out.append(cur); cur = ''
        cur += x
    if cur: out.append(cur)
    return out or ['']

def two_lines(s):
    if len(s) <= LINE: return s
    mid = len(s) // 2; best = None
    for i, ch in enumerate(s):
        if ch in '、，。 ' and abs(i + 1 - mid) < (abs(best + 1 - mid) if best is not None else 99): best = i
    cut = (best + 1) if best is not None else mid
    return s[:cut] + '\n' + s[cut:]

def fmt_ts(ms):
    ms = max(0, int(ms)); h, r = divmod(ms, 3600000); m, r = divmod(r, 60000); sec, ms = divmod(r, 1000)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'

def build_srt(outdir):
    outdir = pathlib.Path(outdir); n = skipped = 0
    for p in sorted((DATA / 'srt').glob('*.json')):
        d = json.loads(p.read_text(encoding='utf-8'))
        if not any(u['ja'] for u in d['units']): skipped += 1; continue
        rel = pathlib.Path(d['source']); dst = outdir / rel.parent / (rel.stem + '.ja.srt'); dst.parent.mkdir(parents=True, exist_ok=True)
        cues = []   # (開始ms, 終了ms, 文)
        for u in d['units']:
            a, b = ts_ms(u['start']), ts_ms(u['end'])
            pieces = split_ja(u['ja'] if u['ja'] else u['en'])
            total = sum(len(x) for x in pieces) or 1; t = a
            for x in pieces:
                dur = (b - a) * len(x) / total
                cues.append([t, t + dur, x]); t += dur
        prev_end = 0
        for c in cues:                       # 時刻が前の字幕と重ならないようにする
            c[0] = max(c[0], prev_end); c[1] = max(c[1], c[0] + 500); prev_end = c[1]
        dst.write_text('\n'.join(f"{k}\n{fmt_ts(c[0])} --> {fmt_ts(c[1])}\n{two_lines(c[2])}\n" for k, c in enumerate(cues, 1)), encoding='utf-8'); n += 1
    print('日本語の字幕:', n, '本(まだ訳していない', skipped, '本は出さない)')

# ---------------------------------------------------------------- スライド
STOP = set('the a an is are was were to of and in for you it we this that on as with be by or at from not can will if so but'.split())
REG = re.compile(r'\b(r[a-d]x|e[a-d]x|r[sd]i|e[sd]i|r[sb]p|e[sb]p|rip|eip|r\d{1,2}[dwb]?|xmm\d+|[a-d][lh]|0x[0-9a-fA-F]+)\b')
MNEM = re.compile(r'^(mov|lea|push|pop|call|ret|jmp|je|jne|jg|jl|jge|jle|ja|jb|cmp|test|add|sub|mul|imul|div|idiv|and|or|xor|not|shl|shr|sar|sal|nop|int|leave|rep|cdq|cqo|movzx|movsx|inc|dec|neg|syscall|enter)\b', re.I)

def translatable(t):
    t = t.strip()
    if not re.search(r'[A-Za-z]{2,}', t): return False
    words = re.findall(r"[A-Za-z']+", t.lower())
    if any(w in STOP for w in words): return True
    if MNEM.match(t) or REG.search(t): return False
    if len(words) <= 8 and t[0].isupper() and not t.isupper(): return True
    return len(words) >= 3 and not re.search(r'[=;{}()\[\]]', t)

def walk_pptx(prs):
    """段落を、決まった順序で順に返す。(段落, 場所の説明)"""
    def shapes_of(shapes, where):
        for sh in shapes:
            if sh.shape_type == 6:
                yield from shapes_of(sh.shapes, where); continue
            if sh.has_text_frame:
                for para in sh.text_frame.paragraphs: yield para, where
            if getattr(sh, 'has_table', False) and sh.has_table:
                for row in sh.table.rows:
                    for c in row.cells:
                        for para in c.text_frame.paragraphs: yield para, where
    for si, s in enumerate(prs.slides, 1):
        yield from shapes_of(s.shapes, f'スライド{si}')
        if s.has_notes_slide:
            for para in s.notes_slide.notes_text_frame.paragraphs: yield para, f'ノート{si}'

def para_text(para): return ''.join(r.text for r in para.runs).strip()

def extract_pptx(up):
    from pptx import Presentation
    up = pathlib.Path(up); out = DATA / 'pptx'; out.mkdir(parents=True, exist_ok=True); tot = 0
    for f in sorted(up.rglob('*.pptx')):
        rel = f.relative_to(up).as_posix(); prs = Presentation(str(f)); units = []
        for n, (para, where) in enumerate(walk_pptx(prs)):
            t = para_text(para)
            if t and translatable(t): units.append({'i': n, 'where': where, 'en': t, 'ja': ''})
        name = rel.replace('/', '__')[:-5]; p = out / (name + '.json')
        if p.exists():
            old = {u['en']: u['ja'] for u in json.loads(p.read_text(encoding='utf-8'))['units']}
            for u in units: u['ja'] = old.get(u['en'], '')
        p.write_text(json.dumps({'source': rel, 'units': units}, ensure_ascii=False, indent=0), encoding='utf-8'); tot += len(units)
    print('スライドの段落(訳す対象):', tot)

def build_pptx(up, outdir):
    from pptx import Presentation
    up = pathlib.Path(up); outdir = pathlib.Path(outdir); n = 0
    for p in sorted((DATA / 'pptx').glob('*.json')):
        d = json.loads(p.read_text(encoding='utf-8'))
        by = {u['i']: u for u in d['units'] if u['ja']}
        if not by: continue
        prs = Presentation(str(up / d['source']))
        for k, (para, where) in enumerate(walk_pptx(prs)):
            u = by.get(k)
            if not u or para_text(para) != u['en'] or not para.runs: continue   # 原文が変わっていたら書き換えない
            para.runs[0].text = u['ja']
            for r in para.runs[1:]: r.text = ''
        dst = outdir / pathlib.Path(d['source']).parent / (pathlib.Path(d['source']).stem + '.ja.pptx'); dst.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(dst)); n += 1
    print('日本語のスライド:', n, '本')

# ---------------------------------------------------------------- 訳す作業
def load(kind, name):
    p = DATA / kind / (name + '.json'); return p, json.loads(p.read_text(encoding='utf-8'))

def status():
    for kind in ('srt', 'pptx'):
        files = sorted((DATA / kind).glob('*.json')); tot = done = 0; fin = 0
        for p in files:
            us = json.loads(p.read_text(encoding='utf-8'))['units']; t = len(us); d = sum(1 for u in us if u['ja']); tot += t; done += d; fin += (t == d)
        print(f'{kind}: {done} / {tot} 単位({done * 100 // max(tot, 1)}%)、完了 {fin} / {len(files)} ファイル')

def next_(kind, name, n=40):
    p, d = load(kind, name); todo = [u for u in d['units'] if not u['ja']]
    print(f'未訳 {len(todo)} 件(うち {min(n, len(todo))} 件を表示)')
    for u in todo[:n]:
        extra = f" [{u['where']}]" if 'where' in u else ''
        print(f"[{u['i']}]{extra} {u['en']}")

def apply_(kind, name, files):
    p, d = load(kind, name); by = {str(u['i']): u for u in d['units']}; mp = {}
    for f in files: mp.update(json.loads(pathlib.Path(f).read_text(encoding='utf-8')))
    ok = bad = 0
    for k, v in mp.items():
        u = by.get(k)
        if u is None: print('  [却下]', k, '番号がありません'); bad += 1; continue
        if v is None: v = u['en']          # 訳さず原文のまま
        if not v.strip(): print('  [却下]', k, '空の訳'); bad += 1; continue
        u['ja'] = v; ok += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding='utf-8')
    print(f'{name}: 適用 {ok} 件 / 却下 {bad} 件 / 残り {sum(1 for u in d["units"] if not u["ja"])} 件')

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    c = a[0]
    if c == 'extract-srt': extract_srt(a[1])
    elif c == 'extract-pptx': extract_pptx(a[1])
    elif c == 'status': status()
    elif c == 'next': next_(a[1], a[2], int(a[3]) if len(a) > 3 else 40)
    elif c == 'apply': apply_(a[1], a[2], a[3:])
    elif c == 'build-srt': build_srt(a[1])
    elif c == 'build-pptx': build_pptx(a[1], a[2])
    else: print(__doc__); sys.exit(1)
