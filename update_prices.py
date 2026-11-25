# Red Gold Metaverse: market prices of industrial metals for the website charts.
# Monthly history: International Monetary Fund, Primary Commodity Price System (PCPS),
# read from the IMF's own data service, in US dollars per metric ton.
# Latest daily price: MetalCharts (free plan, one request a day), in US dollars per pound.
# This script writes data/prices.json. The MetalCharts key is read from the environment
# and is never printed.
import json, os, re, sys, time, urllib.error, urllib.request

SERIES = {
    'copper':   'PCOPP',
    'aluminum': 'PALUM',
    'nickel':   'PNICK',
    'zinc':     'PZINC',
    'tin':      'PTIN',
}
DAILY = {'HG': 'copper', 'ALI': 'aluminum', 'NI': 'nickel', 'ZN': 'zinc', 'SN': 'tin'}
LB_PER_TONNE = 2204.62262
START = '2016-01'
OUT = os.path.join('data', 'prices.json')
URL = 'https://api.imf.org/external/sdmx/2.1/data/IMF.RES,PCPS/G001.%s.USD.M?startPeriod=%s'
MC = 'https://api.metalcharts.org/v1/prices?symbols=%s&unit=lb'
UA = 'Mozilla/5.0 (rgm-metal-prices)'


def fetch(code):
    req = urllib.request.Request(URL % (code, START), headers={'User-Agent': UA})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                text = r.read().decode('utf-8')
            out = {}
            for tag in re.findall(r'<(?:\w+:)?Obs\b[^>]*>', text):
                p = re.search(r'TIME_PERIOD="([^"]+)"', tag)
                v = re.search(r'OBS_VALUE="([^"]+)"', tag)
                if not p or not v:
                    continue
                m = re.match(r'(\d{4})-M?(\d{1,2})$', p.group(1))
                if not m:
                    continue
                try:
                    val = float(v.group(1))
                except ValueError:
                    continue
                out['%s-%02d' % (m.group(1), int(m.group(2)))] = val
            rows = [[k, round(out[k], 2), round(out[k] / LB_PER_TONNE, 4)] for k in sorted(out)]
            if len(rows) < 12:
                raise ValueError('too few rows for %s: %d; start of reply: %s' % (code, len(rows), text[:400]))
            return rows
        except Exception as e:  # try again, then give up on this series
            last = e
            time.sleep(5)
    raise last


def mc_call(symbols, key):
    req = urllib.request.Request(MC % ','.join(symbols), headers={'User-Agent': UA, 'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.getcode(), json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:300]
        return e.code, {'error_body': body}


def fetch_daily():
    key = os.environ.get('METALCHARTS_KEY', '').strip()
    if not key:
        print('daily: no key in the environment, skipped')
        return {}
    symbols = list(DAILY)
    code, reply = mc_call(symbols, key)
    if code != 200 or not isinstance(reply.get('data'), dict):
        print('daily: first call status', code, str(reply)[:300].replace(key, '***'))
        symbols = [s for s in symbols if s != 'SN']
        code, reply = mc_call(symbols, key)
    if code != 200 or not isinstance(reply.get('data'), dict):
        print('daily: second call status', code, str(reply)[:300].replace(key, '***'))
        return {}
    out = {}
    for sym, q in reply['data'].items():
        name = DAILY.get(sym)
        if not name or not isinstance(q, dict):
            continue
        price, unit, cur = q.get('price'), q.get('unit'), q.get('currency')
        print('daily:', sym, name, price, cur, unit, q.get('timestamp'), 'stale' if q.get('stale') else '')
        if not isinstance(price, (int, float)) or unit != 'lb' or cur != 'USD' or price <= 0:
            print('daily: not used (needs a positive price in USD per lb)')
            continue
        out[name] = {'usd_per_pound': round(float(price), 4), 'time': str(q.get('timestamp') or ''), 'symbol': sym}
    missing = [n for n in DAILY.values() if n not in out]
    if missing:
        print('daily: no figure for', missing)
    return out


def main():
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            old = json.load(f)
    metals = dict(old.get('metals', {}))
    failed = []
    for name, code in SERIES.items():
        try:
            rows = fetch(code)
            metals[name] = {
                'series': code,
                'source': 'International Monetary Fund, Primary Commodity Price System',
                'columns': ['month', 'usd_per_metric_ton', 'usd_per_pound'],
                'monthly': rows,
            }
        except Exception as e:
            failed.append('%s (%s): %s' % (name, code, e))
    if not metals:
        print('No series could be read:', failed)
        sys.exit(1)
    daily = dict(old.get('daily', {}))
    history = {k: list(v) for k, v in old.get('daily_history', {}).items()}
    try:
        fresh = fetch_daily()
    except Exception as e:
        print('daily: failed,', type(e).__name__)
        fresh = {}
    today = time.strftime('%Y-%m-%d', time.gmtime())
    for name, q in fresh.items():
        daily[name] = q
        rows = [r for r in history.get(name, []) if r[0] != today]
        rows.append([today, q['usd_per_pound']])
        history[name] = rows[-800:]
    new = {'metals': metals, 'daily': daily, 'daily_history': history,
           'daily_source': 'MetalCharts', 'daily_credit': 'https://metalcharts.org'}
    same = all(new.get(k) == old.get(k) for k in ('metals', 'daily', 'daily_history'))
    if not same:
        new['updated'] = today
        os.makedirs('data', exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(new, f, separators=(',', ':'))
        print('prices.json written')
    else:
        print('no change')
    for name, m in metals.items():
        print(name, len(m['monthly']), 'months', m['monthly'][0], m['monthly'][-1], 'daily', daily.get(name))
    if failed:
        print('FAILED:', failed)
        sys.exit(1)


if __name__ == '__main__':
    main()
