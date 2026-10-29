import io

p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()

# 1) 容错解析：从乱文本里捞 JSON 数组 / 单个对象
helper = '''

def _salvage(text):
    """模型偶尔会带前言、截断或加代码块，尽量把对象捞出来。"""
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        v = json.loads(t)
        if isinstance(v, dict):
            return v.get("items") or v.get("list") or [v]
        return v if isinstance(v, list) else []
    except Exception:
        pass
    m = re.search(r"\\[.*\\]", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    out = []
    for obj in re.findall(r"\\{[^{}]*\\}", t):
        try:
            out.append(json.loads(obj))
        except Exception:
            continue
    return out
'''
anchor = '\ndef _collect(arr):'
assert s.count(anchor) == 1
s = s.replace(anchor, helper + anchor, 1)

# 2) 三处 json.loads(content) 改走 _salvage
s = s.replace('''        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
        arr = json.loads(content)
        if isinstance(arr, dict):
            arr = arr.get("items") or arr.get("list") or []
        return _collect(arr)''',
'''        return _collect(_salvage(content))''')

s = s.replace('''    arr = json.loads(content)
    if isinstance(arr, dict):
        arr = arr.get("items") or arr.get("list") or []
    return _collect(arr)''',
'''    return _collect(_salvage(content))''')

# 3) DDG 批量收小（4 条/批），并且跳过 pollinations（无 key 时只回错误）
s = s.replace('CANDIDATES.append(("https://text.pollinations.ai/openai", "openai"))\n', '')
s = s.replace('CANDIDATES.append(("https://text.pollinations.ai/openai", "mistral"))\n', '')

s = s.replace('''    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]''',
'''    _bs = 4 if _KIND == "ddg" else BATCH
    for i in range(0, len(items), _bs):
        chunk = items[i:i + _bs]''')

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
