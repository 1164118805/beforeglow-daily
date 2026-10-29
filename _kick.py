import base64, io, json, subprocess, urllib.request

TOKEN = subprocess.check_output(
    'printf "protocol=https\\nhost=github.com\\n\\n" | git credential fill',
    shell=True, text=True).split('password=')[1].split('\n')[0].strip()
REPO = '1164118805/beforeglow-daily'


def api(method, path, body=None):
    req = urllib.request.Request(
        'https://api.github.com/repos/%s/contents/%s' % (REPO, path), method=method,
        data=json.dumps(body).encode() if body else None,
        headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'bg'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


# 1) 给工作流加 push 触发（只在脚本本身变动时跑）
p = '.github/workflows/enrich-topics.yml'
s = io.open(p, encoding='utf-8').read()
if "  push:" in s:
    print('push trigger already there')
else:
    old = "on:\n  workflow_dispatch:\n"
    new = "on:\n  workflow_dispatch:\n  push:\n    paths:\n      - 'scripts/enrich_topics.py'\n"
    assert s.count(old) == 1, s.count(old)
    io.open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new))
    cur = api('GET', p)
    data = base64.b64encode(io.open(p, 'rb').read()).decode()
    out = api('PUT', p, {'message': 'ci: 允许 push 触发 AI 补全', 'content': data,
                         'sha': cur['sha'], 'branch': 'main'})
    print('yml updated', out['commit']['sha'][:7])

# 2) 碰一下脚本，触发一次真跑
p2 = 'scripts/enrich_topics.py'
cur2 = api('GET', p2)
src = base64.b64decode(cur2['content']).decode('utf-8')
if 'KICK' not in src:
    src = src.replace('"""\nimport json', '"""\n# KICK: 触发一次云端补全\nimport json', 1)
    if 'KICK' not in src:
        src = src.rstrip('\n') + '\n# KICK\n'
    out2 = api('PUT', p2, {'message': 'chore: 触发一次 AI 补全', 'content': base64.b64encode(src.encode()).decode(),
                           'sha': cur2['sha'], 'branch': 'main'})
    print('kicked', out2['commit']['sha'][:7])
else:
    print('already kicked')
