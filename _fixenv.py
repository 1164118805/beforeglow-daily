import io

for p in ('scripts/enrich_topics.py', 'scripts/refresh_hot_topics.py'):
    s = io.open(p, encoding='utf-8').read()
    a = 'AI_URL = os.environ.get("LLM_BASE_URL", "https://models.github.ai/inference/chat/completions")'
    b = 'AI_URL = os.environ.get("LLM_BASE_URL") or "https://models.github.ai/inference/chat/completions"'
    c = 'AI_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")'
    d = 'AI_MODEL = os.environ.get("LLM_MODEL") or "openai/gpt-4o-mini"'
    changed = False
    if a in s:
        s = s.replace(a, b)
        changed = True
    if c in s:
        s = s.replace(c, d)
        changed = True
    # 空的 LLM_API_KEY 也不该盖掉 GITHUB_TOKEN
    e = 'TOKEN = os.environ.get("LLM_API_KEY") or os.environ.get("GITHUB_TOKEN")'
    if e in s:
        s = s.replace(e, 'TOKEN = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")')
        changed = True
    f = 'token = os.environ.get("LLM_API_KEY") or os.environ.get("GITHUB_TOKEN")'
    if f in s:
        s = s.replace(f, 'token = (os.environ.get("LLM_API_KEY") or "").strip() or os.environ.get("GITHUB_TOKEN")')
        changed = True
    io.open(p, 'w', encoding='utf-8', newline='').write(s)
    print(p, 'changed' if changed else 'unchanged')

import ast
for p in ('scripts/enrich_topics.py', 'scripts/refresh_hot_topics.py'):
    ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
