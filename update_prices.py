# Red Gold Metaverse: market prices of industrial metals for the website charts.
# Monthly history: International Monetary Fund, Primary Commodity Price System (PCPS),
# read from the IMF's own data service, in US dollars per metric ton.
# This script converts them to US dollars per pound and writes data/prices.json.
import json, os, re, sys, time, urllib.request

SERIES = {
    'copper':   'PCOPP',
    'aluminum': 'PALUM',
    'nickel':   'PNICK',
    'zinc':     'PZINC',
    'tin':      'PTIN',
}
LB_PER_TONNE = 2204.62262
START = '2016-01'
OUT = os.path.join('data', 'prices.json')
URL = 'https://api.imf.org/external/sdmx/2.1/data/IMF.RES,PCPS/G001.%s.USD.M?startPeriod=%s'


def fetch(code):
    req = urllib.request.Request(URL % (code, START), headers={'User-Agent': 'Mozilla/5.0 (rgm-metal-prices)'})
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
    if metals != old.get('metals'):
        new = {'updated': time.strftime('%Y-%m-%d', time.gmtime()), 'metals': metals}
        os.makedirs('data', exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(new, f, separators=(',', ':'))
        print('prices.json written')
    else:
        print('no change')
    for name, m in metals.items():
        print(name, len(m['monthly']), 'months', m['monthly'][0], m['monthly'][-13], m['monthly'][-1])
    if failed:
        print('FAILED:', failed)
        sys.exit(1)


if __name__ == '__main__':
    main()
