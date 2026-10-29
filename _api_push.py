import base64, json, os, subprocess, sys, urllib.request

TOKEN = subprocess.check_output(
    'printf "protocol=https\\nhost=github.com\\n\\n" | git credential fill',
    shell=True, text=True).split('password=')[1].split('\n')[0].strip()

REPO = '1164118805/beforeglow-daily'
FILES = [
    ('scripts/refresh_hot_topics.py', 'feat: 五段口述版 prompt + 时效判定 + 保留上一版 AI 字段'),
    ('scripts/enrich_topics.py', 'feat: 话题库 AI 用五段框架 + 时效判定'),
    ('.github/workflows/refresh-hotmusic.yml', 'ci: 每日任务加 AI 补全步骤'),
]


def api(method, path, body=None):
    req = urllib.request.Request(
        'https://api.github.com/repos/%s/contents/%s' % (REPO, path),
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            'Authorization': 'Bearer ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'beforeglow-bot',
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


for path, msg in FILES:
    cur = api('GET', path)
    data = base64.b64encode(open(path, 'rb').read()).decode()
    if cur.get('content', '').replace('\n', '') == data:
        print('same', path)
        continue
    out = api('PUT', path, {'message': msg, 'content': data, 'sha': cur['sha'], 'branch': 'main'})
    print('updated', path, out['commit']['sha'][:7])
