#!/usr/bin/env python3
import argparse, json, os, re, html, subprocess
from datetime import datetime, timezone, timedelta

def load_state(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"shared": []}

def save_state(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_trending_daily():
    res = subprocess.run([
        'curl','-s','-H','Accept: text/html','https://github.com/trending?since=daily'
    ], capture_output=True, text=True, timeout=30)
    page = res.stdout
    arts = page.split('<article class="Box-row">')[1:]
    out = []
    for a in arts:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', a, re.DOTALL)
        if not m:
            continue
        name = m.group(1).strip().replace(' ','').replace('\n','')
        if name.count('/') != 1:
            continue
        d = re.search(r'<p class="col-9[^"]*">\s*(.*?)\s*</p>', a, re.DOTALL)
        desc = html.unescape(d.group(1).strip()) if d else ''
        l = re.search(r'itemprop="programmingLanguage">(.*?)</span>', a)
        lang = l.group(1).strip() if l else 'N/A'
        s = re.search(r'Link--muted d-inline-block mr-3">\s*.*?([\d,]+)\s*</a>', a, re.DOTALL)
        stars = int(s.group(1).replace(',','')) if s else 0
        t = re.search(r'([\d,]+)\s*stars today', a)
        stars_today = int(t.group(1).replace(',','')) if t else 0
        out.append({
            'name': name,
            'url': f'https://github.com/{name}',
            'stars': stars,
            'stars_today': stars_today,
            'language': lang,
            'description': desc[:160]
        })
    return out

def fetch_new_7d(limit=50):
    cutoff = (datetime.now(timezone.utc)-timedelta(days=7)).strftime('%Y-%m-%d')
    url = f'https://api.github.com/search/repositories?q=created:>={cutoff}&sort=stars&order=desc&per_page={limit}'
    res = subprocess.run(['curl','-s',url], capture_output=True, text=True, timeout=30)
    data = json.loads(res.stdout or '{}')
    out = []
    for r in data.get('items',[]):
        out.append({
            'name': r['full_name'],
            'url': r['html_url'],
            'stars': r.get('stargazers_count',0),
            'stars_today': 0,
            'language': r.get('language') or 'N/A',
            'description': (r.get('description') or '')[:160]
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state-file', required=True)
    ap.add_argument('--max-trending', type=int, default=10)
    ap.add_argument('--max-new', type=int, default=10)
    args = ap.parse_args()

    state = load_state(args.state_file)
    seen = {x.get('repo') for x in state.get('shared', [])}

    tr = fetch_trending_daily()
    tr_new = [x for x in tr if x['name'] not in seen][:args.max_trending]
    tr_names = {x['name'] for x in tr_new}

    nw = fetch_new_7d(limit=80)
    nw_new = [x for x in nw if x['name'] not in seen and x['name'] not in tr_names][:args.max_new]

    now = datetime.now(timezone.utc).isoformat()
    state.setdefault('shared', [])
    for x in tr_new + nw_new:
        state['shared'].append({'repo': x['name'], 'ts': now})

    cutoff = (datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
    state['shared'] = [x for x in state['shared'] if x.get('ts','') > cutoff]
    save_state(args.state_file, state)

    print(json.dumps({
        'trending': {'count': len(tr_new), 'repos': tr_new},
        'new': {'count': len(nw_new), 'repos': nw_new}
    }, ensure_ascii=False))

if __name__ == '__main__':
    main()
