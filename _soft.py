import io

# 1) 候选端点收窄：优先用户配置的 LLM_BASE_URL，其次 GitHub Models
p = 'scripts/enrich_topics.py'
s = io.open(p, encoding='utf-8').read()
start = s.index('CANDIDATES = [')
end = s.index(']\n', start) + 2
new = '''_BASE = (os.environ.get("LLM_BASE_URL") or "").strip()
CANDIDATES = []
if _BASE:
    CANDIDATES.append((_BASE, AI_MODEL))
CANDIDATES.append(("https://models.github.ai/inference/chat/completions", AI_MODEL))
'''
s = s[:start] + new + s[end:]

# 2) AI 不可用不要红、也不要挡住每日更新：只打 warning，正常退出
s = s.replace('''    if not picked:
        print("::error title=AI 不可用::所有候选端点都失败，看上面的 RAW 行")
        sys.exit(1)''',
'''    if not picked:
        print("::warning title=AI 不可用::所有候选端点都失败，本次跳过 AI 补全（站点仍用手写内容）")
        return''')
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('enrich patched')

import ast
ast.parse(io.open(p, encoding='utf-8').read())
print('py ok')
