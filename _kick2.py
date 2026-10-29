import base64, json, subprocess, urllib.request

CMD = 'printf "protocol=https\\nhost=github.com\\n\\n" | git credential fill'
TOKEN = subprocess.check_output(CMD, shell=True, text=True).split('password=')[1].split('\n')[0].strip()
REPO = '1164118805/beforeglow-daily'
PATH = 'scripts/enrich_topics.py'


def api(method, body=None):
    req = urllib.request.Request(
        'https://api.github.com/repos/%s/contents/%s' % (REPO, PATH), method=method,
        data=json.dumps(body).encode() if body else None,
        headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'bg'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


cur = api('GET')
src = base64.b64decode(cur['content']).decode('utf-8')
if '# KICK2' in src:
    print('already kicked')
else:
    src = src.rstrip('\n') + '\n# KICK2\n'
    out = api('PUT', {'message': 'chore: 触发一次（DDG 兜底）',
                      'content': base64.b64encode(src.encode()).decode(),
                      'sha': cur['sha'], 'branch': 'main'})
    print('kicked', out['commit']['sha'][:7])
