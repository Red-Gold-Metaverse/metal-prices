# Red Gold Metaverse: market prices of industrial metals for the website charts.
# Monthly history: International Monetary Fund series published by FRED
# (Federal Reserve Bank of St. Louis), in US dollars per metric ton.
# This script converts them to US dollars per pound and writes data/prices.json.
import csv, io, json, os, sys, time, urllib.request

SERIES = {
    'copper':   'PCOPPUSDM',
    'aluminum': 'PALUMUSDM',
    'nickel':   'PNICKUSDM',
    'zinc':     'PZINCUSDM',
    'tin':      'PTINUSDM',
}
LB_PER_TONNE = 2204.62262
START = '2016-01-01'
OUT = os.path.join('data', 'prices.json')


def fetch(series):
    url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s&cosd=%s' % (series, START)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (rgm-metal-prices)'})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode('utf-8')
            rows = list(csv.reader(io.StringIO(text)))
            out = []
            for row in rows[1:]:
                if len(row) < 2:
                    continue
                try:
                    v = float(row[1])
                except ValueError:
                    continue
                out.append([row[0][:7], round(v, 2), round(v / LB_PER_TONNE, 4)])
            if len(out) < 12:
                raise ValueError('too few rows for %s: %d' % (series, len(out)))
            return out
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
    for name, series in SERIES.items():
        try:
            rows = fetch(series)
            metals[name] = {
                'series': series,
                'source': 'International Monetary Fund, by way of FRED (Federal Reserve Bank of St. Louis)',
                'columns': ['month', 'usd_per_metric_ton', 'usd_per_pound'],
                'monthly': rows,
            }
        except Exception as e:
            failed.append('%s (%s): %s' % (name, series, e))
    if not metals:
        print('No series could be read:', failed)
        sys.exit(1)
    new = {'metals': metals}
    if new.get('metals') != old.get('metals'):
        new['updated'] = time.strftime('%Y-%m-%d', time.gmtime())
        os.makedirs('data', exist_ok=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(new, f, separators=(',', ':'))
        print('prices.json written')
    else:
        print('no change')
    for name, m in metals.items():
        print(name, m['monthly'][-1])
    if failed:
        print('FAILED:', failed)
        sys.exit(1)


if __name__ == '__main__':
    main()
