import base64, json, subprocess, sys, urllib.error, urllib.request

CMD = 'printf "protocol=https\\nhost=github.com\\n\\n" | git credential fill'
TOKEN = subprocess.check_output(CMD, shell=True, text=True).split('password=')[1].split('\n')[0].strip()
REPO = '1164118805/beforeglow-daily'
path = sys.argv[1]
msg = sys.argv[2] if len(sys.argv) > 2 else 'chore: update ' + path


def api(method, body=None):
    req = urllib.request.Request(
        'https://api.github.com/repos/%s/contents/%s' % (REPO, path), method=method,
        data=json.dumps(body).encode() if body else None,
        headers={'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json',
                 'Content-Type': 'application/json', 'User-Agent': 'bg'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


data = base64.b64encode(open(path, 'rb').read()).decode()
sha = None
try:
    cur = api('GET')
    sha = cur.get('sha')
    if cur.get('content', '').replace('\n', '') == data:
        print('same')
        raise SystemExit
except urllib.error.HTTPError as e:
    if e.code != 404:
        raise
    print('new file')

body = {'message': msg, 'content': data, 'branch': 'main'}
if sha:
    body['sha'] = sha
out = api('PUT', body)
print('updated', out['commit']['sha'][:7])
