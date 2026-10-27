#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_hotmusic_build.py — 抓抖音热歌榜并生成站点同源的 hotmusic.json

用法：
  python3 _hotmusic_build.py            # 联网抓榜单（api.xcvts.cn）
  python3 _hotmusic_build.py --local    # 用本地 _api.json（离线/调试）

输出：_dist/hotmusic.json
  {"date":"YYYY-MM-DD","updated":"ISO","source":"抖音热歌榜",
   "cats":[...], "songs":[{"t":歌名,"a":歌手,"g":分类}, ...]}

分类（主播使用场景）：暖场 / 互动 / 情绪 / 卡点 / 纯音 / 下播
- 今日 66 首用 CURATED 人工校准；
- 榜单换了之后没校准到的新歌，用启发式兜底（关键词）。
"""
import sys, os, json, re, datetime, urllib.request

API = 'https://api.xcvts.cn/api/hotlist/dy/music'
HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.join(HERE, '_api.json')
OUT = os.path.join(os.getcwd(), 'hotmusic.json')
CATS = ['暖场', '互动', '情绪', '卡点', '纯音', '下播']

# 人工校准（按「歌名」匹配，忽略歌手）
CURATED = {
    'Peach': '暖场', '99（主歌段）': '卡点', '何必相逢（泪要第几颗才算浓）': '情绪',
    '思念像一场重感冒（副歌）': '情绪', 'Starlight (氛围纯享版)': '纯音',
    'ICEMAN X Timeless（5757E Remix）（剪辑版）': '卡点', '失眠了': '情绪',
    '幻昼3.0 (纯音版)': '纯音', 'Atatata - Radio Edit': '卡点',
    '如果我一颗心被你俘虏': '情绪', '她（你的名字）': '情绪',
    '我和你要去闻闻新鲜的春天': '暖场', '马年进行曲': '互动',
    'City In Slow time': '暖场', '来不及爱你-降速版': '情绪',
    '传奇(Remix)': '卡点', '咏春 (氛围版)（Cover 七朵组合）': '暖场',
    '心绪(我想要的只是你在我身边)': '情绪', 'You And Me': '暖场', '花间': '纯音',
    '忘了算了（Cover 范怡文）（主歌）': '情绪', '别辜负眼前季节 (咏春DJ)': '卡点',
    'ditto(氛围感)': '暖场', '拿下拿下（Cover 王者阿水 & 阿水）（剪辑版）': '互动',
    'Someone In The Crowd(纯音乐)': '纯音', '春风吹': '暖场', '你不必是一朵花（剪辑版）': '情绪',
    '几分之几（氛围r&b）（Cover 卢广仲）（剪辑版）': '情绪', '你说我们星座不相配 (Remix)': '互动',
    '读心术（束一个马尾束起所有伤悲）': '情绪', '爱要拐几个弯才来': '情绪', '也不是谁的错': '情绪',
    'here with me (Tove Ball Remix)': '暖场', '光头强小曲 (DJ版)': '互动', '假心话': '情绪',
    '只愿与你长相守': '情绪', '你很哇塞(女神节版)': '互动',
    'Scared 2 be lonely beat（当真爱降临）（剪辑版）': '卡点', '幸福降临（剪辑版）': '暖场',
    '想看你笑想和你闹': '暖场', '天下第一好': '暖场', 'The Clouds in Camarillo': '下播',
    '第一天（R&B律动版）（Cover 孙燕姿）（剪辑版）': '暖场', 'Memories': '暖场',
    '比比拉布 我的刀盾': '互动', '一切都在变好（生命力BGM）': '暖场',
    '删照片 (你删了我的照片 也删了我的微信)': '情绪', 'Heroes 3': '卡点',
    '左转灯 (1000 Times+1)': '情绪', '你知道天空有多藍': '暖场', '鼠牛功夫高': '卡点',
    '太聪明R&B版（剪辑版）': '情绪', 'ぎのようなときめき（兔子般的心动） 変速 ver.（剪辑版）': '卡点',
    '他只是经过': '情绪', '雨过后的风景（某年某月某个星期几）': '情绪', '咏春（副歌）': '暖场',
    '雨日思绪（雨の日の想い）（剪辑版2）': '纯音', 'Proof(Slowed)': '下播',
    '我欲成冰再也无退路（剪辑版）': '卡点', '4 AM Humming': '纯音', '够爱 (R&B版)（Cover 东城卫）（剪辑版）': '情绪',
    '远去的列车': '下播', '无尽幸福': '暖场',
    'りんごなんてつまらなくないもん！（苹果才不无聊呢！）': '互动',
    '我就爱这乱七八糟的生活': '暖场', 'Autumn Leaf': '下播',
}


def guess(title, artist):
    s = (title or '') + ' ' + (artist or '')
    if re.search(r'纯音|纯音乐|演奏|instrumental|humming|氛围纯享|beat', s, re.I):
        return '纯音'
    if re.search(r'remix|dj|进行曲|变速|变装|卡点|剪辑版.*DJ|刀盾|功夫', s, re.I):
        return '卡点'
    if re.search(r'泪|别|想|爱|心|遗憾|孤独|失眠|雨|照片|错|经过|远|冰|退路|何必|思念', s):
        return '情绪'
    if re.search(r'幸福|春天|笑|闹|好|暖|相遇|新鲜|生活|变好|降临', s):
        return '暖场'
    return '暖场'


def main():
    use_local = '--local' in sys.argv
    if use_local and os.path.exists(LOCAL):
        d = json.load(open(LOCAL, encoding='utf-8'))
        src = 'local'
    else:
        req = urllib.request.Request(API, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode('utf-8'))
        src = 'api'
    arr = d.get('data') or []
    songs = []
    for x in arr:
        t = (x.get('title') or '').strip()
        a = (x.get('artist') or '').strip()
        if not t:
            continue
        g = CURATED.get(t) or guess(t, a)
        songs.append({'t': t, 'a': a, 'g': g})
    now = datetime.datetime.now()
    out = {
        'date': now.strftime('%Y-%m-%d'),
        'updated': d.get('updateTime') or now.isoformat(timespec='seconds'),
        'source': '抖音热歌榜',
        'cats': CATS,
        'songs': songs,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    from collections import Counter
    c = Counter(s['g'] for s in songs)
    print('source=%s items=%d date=%s' % (src, len(songs), out['date']))
    print('分类分布：', dict(c))
    print('written', OUT, os.path.getsize(OUT), 'bytes')


if __name__ == '__main__':
    main()
