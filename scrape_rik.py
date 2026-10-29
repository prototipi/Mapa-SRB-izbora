"""Scrape polling-station results from the RIK results page (rik.parlament.gov.rs/542645/sr/rezultati/sr/).

Writes the same column layout as the RIK xlsx export, for elections where the export is not available.

Usage:  py scrape_rik.py [--round 341140] [--type 2] [--out rezultati_2023] [--workers 4]
Round ids: 341140 = Парламентарни 2023, 680072 = Парламентарни 2026 (election type 2 = parliamentary).
Raw responses go to cache/<round>.jsonl, so an interrupted run continues where it stopped.
Only the Python standard library is needed.
"""
import argparse, csv, glob, html, http.cookiejar, json, os, re, sys, time, urllib.parse, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://www.rik.parlament.gov.rs'
PAGE = BASE + '/542645/sr/rezultati/sr/'

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
HEADERS = {'User-Agent': 'Mozilla/5.0 (election-results research)', 'X-Requested-With': 'XMLHttpRequest', 'Referer': PAGE}


def post(path, data, tries=5):
    body = urllib.parse.urlencode(data).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(BASE + path, data=body, headers=HEADERS)
            with opener.open(req, timeout=60) as r:
                return r.read().decode('utf-8')
        except Exception as e:
            if attempt == tries - 1:
                raise
            wait = 2 ** attempt * 3
            print(f'  retry {path} {data} after error: {e} (waiting {wait}s)', file=sys.stderr)
            time.sleep(wait)


def num(s):
    """'1.783.701' -> 1783701 (RIK uses dots as thousands separators)."""
    return int(str(s).replace('.', '').replace(',', '').strip() or 0)


def parse_documents(fragment):
    """Return [(label, url)] from the minute_from_election_station HTML fragment."""
    docs = []
    for label, href in re.findall(r"<span>([^<]+)</span></div>\s*<div class='table-file[^']*'><a href='([^']+)'", fragment or ''):
        docs.append((html.unescape(label).strip(), BASE + html.unescape(href)))
    return docs


def write_xlsx(path, header, rows):
    """Minimal one-sheet xlsx writer (inline strings, numbers as numbers)."""
    def col(i):
        s = ''
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    def cell(ref, v):
        if isinstance(v, int):
            return f'<c r="{ref}"><v>{v}</v></c>'
        if v is None or v == '':
            return ''
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'

    lines = []
    for r, row in enumerate([header] + rows, start=1):
        lines.append(f'<row r="{r}">' + ''.join(cell(f'{col(c)}{r}', v) for c, v in enumerate(row)) + '</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             + ''.join(lines) + '</sheetData></worksheet>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '</Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                   '</Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', sheet)


def district_lookup():
    """Municipality code -> 'Region/District' from any RIK xlsx export in this folder (the results page shows only regions)."""
    sys.path.insert(0, HERE)
    from build_map import read_xlsx
    # City municipalities that existed in earlier elections but are not in the newer exports.
    out = {'71358': ('Регион Јужне и Источне Србије/Пчињски управни округ', 'RS22/24')}  # Врањска Бања
    for path in glob.glob(os.path.join(HERE, '*.xlsx')):
        try:
            rows = read_xlsx(path)
            h = {k: i for i, k in enumerate(rows[0])}
            for r in rows[1:]:
                out.setdefault(r[h['sifra_opstine']], (r[h['okrug_region']], r[h['sifra_okruga_regiona']]))
        except Exception:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--round', default='341140')
    ap.add_argument('--type', default='2')
    ap.add_argument('--out', default=None)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    out = os.path.join(HERE, a.out or f'rezultati_{a.round}')
    os.makedirs(os.path.join(HERE, 'cache'), exist_ok=True)
    cache_path = os.path.join(HERE, 'cache', f'{a.round}.jsonl')

    opener.open(urllib.request.Request(PAGE, headers={'User-Agent': HEADERS['User-Agent']}), timeout=60).read()
    rounds = json.loads(post('/get-elections/', {'election_type': a.type}))['rounds']
    title = rounds.get(a.round, a.round)
    print(f'Election: {title}')

    # 1. Regions -> municipalities -> polling stations
    regions = json.loads(post('/get-regions/', {'election_type': a.type, 'election_round': a.round}))['regions']
    stations = []
    for rid, rname in regions.items():
        opts = post('/get-municipalities/', {'election_type': a.type, 'election_round': a.round, 'election_region': rid})
        for code, mid, mname in re.findall(r'<option data-id="([^"]*)" value="(\d+)">([^<]*)</option>', opts):
            if mid == '0':
                continue
            st = json.loads(post('/get-election-stations/', {'election_type': a.type, 'election_round': a.round,
                                                             'election_region': rid, 'election_municipality': mid}))
            for sid, label in st['election_stations'].items():
                no, _, name = html.unescape(label).partition(' - ')
                stations.append({'sid': sid, 'no': no.strip(), 'name': name.strip(), 'rid': rid, 'region': rname,
                                 'mid': mid, 'code': code, 'muni': html.unescape(mname).strip()})
        print(f'  {rname}: {len(stations)} stations so far')

    # 2. Results per polling station (cached)
    done = {}
    if os.path.exists(cache_path):
        for line in open(cache_path, encoding='utf-8'):
            rec = json.loads(line)
            done[rec['sid']] = rec['data']
    todo = [s for s in stations if s['sid'] not in done]
    print(f'{len(stations)} stations, {len(done)} cached, {len(todo)} to fetch')

    def fetch(s):
        return s['sid'], json.loads(post('/get_results/', {
            'should_update_pies': 1, 'type': a.type, 'election_round': a.round, 'region': s['rid'],
            'municipality': s['mid'], 'election_station': s['sid']}))

    with open(cache_path, 'a', encoding='utf-8') as cache, ThreadPoolExecutor(a.workers) as pool:
        futures = [pool.submit(fetch, s) for s in todo]
        for i, f in enumerate(as_completed(futures), 1):
            sid, data = f.result()
            done[sid] = data
            cache.write(json.dumps({'sid': sid, 'data': data}, ensure_ascii=False) + '\n')
            if i % 250 == 0:
                cache.flush()
                print(f'  {i}/{len(todo)}')

    # 3. National totals for the check
    nat = json.loads(post('/get_results/', {'should_update_pies': 1, 'type': a.type, 'election_round': a.round,
                                            'region': 0, 'municipality': 0, 'election_station': 0}))

    # 4. Table in the layout of the RIK export
    lists = [(r['count_number'], r['list_name'].strip()) for r in nat['table_data']]
    nl = len(lists)
    districts = district_lookup()
    header = (['bm_uid', 'bm_broj', 'bm_naziv', 'opstina', 'sifra_opstine', 'okrug_region', 'sifra_okruga_regiona',
               'upisani_biraci', 'glasali_biraci', 'listici_u_kutiji', 'vazeci_glasovi', 'nevazeci_listici',
               'vreme_unosa_rezultata'] + [f'lista_{i}' for i in range(1, nl + 1)]
              + ['zapisnik_link', 'korekcija_dokument_link', 'ostali_dokumenti'])
    rows = []
    for s in stations:
        d = done[s['sid']]
        ssn = d['stat_sum_numbers']
        reported = num(ssn.get('processed_stations', 0)) > 0
        valid, invalid = (d['sum_config']['data']['datasets'][0]['data'] + [0, 0])[:2] if reported else (None, None)
        votes = {r['count_number']: num(r['won_number']) for r in d['table_data']}
        docs = parse_documents(d.get('minute_from_election_station'))
        rg2 = next((f'{l}|{u}' for l, u in docs if 'РГ-2' in l), '')
        fix = ' || '.join(f'{l}|{u}' for l, u in docs if 'исправ' in l.lower())
        other = ' || '.join(f'{l}|{u}' for l, u in docs if 'РГ-2' not in l and 'исправ' not in l.lower())
        okrug, okrug_code = districts.get(s['code'], (s['region'] + '/' + s['region'], ''))
        if s['region'] in ('Иностранство', 'Заводи за извршење кривичних санкција'):
            okrug, okrug_code = f"{s['region']}/{s['region']}", '/' + s['code']
        rows.append([int(s['sid']), int(s['no']) if s['no'].isdigit() else s['no'], s['name'], s['muni'], s['code'],
                     okrug, okrug_code, num(ssn['total_voters']),
                     num(ssn['available']) if reported else None, None, valid, invalid,
                     ssn.get('datetime') if reported else '-']
                    + [votes.get(i, 0) if reported else None for i, _ in lists] + [rg2, fix, other])

    write_xlsx(out + '.xlsx', header, rows)
    with open(out + '.csv', 'w', encoding='utf-8-sig', newline='') as f:
        csv.writer(f).writerows([header] + rows)
    with open(out + '_liste.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Br.', 'Naziv liste/kandidata', 'Broj osvojenih glasova', 'Procenat osvojenih glasova (%)'])
        valid_total = nat['sum_config']['data']['datasets'][0]['data'][0]
        for r in nat['table_data']:
            w.writerow([r['count_number'], r['list_name'].strip(), num(r['won_number']), round(num(r['won_number']) / valid_total * 100, 2)])

    # 5. Check against the national totals on the site
    H = {k: i for i, k in enumerate(header)}
    S = lambda k: sum(r[H[k]] or 0 for r in rows)
    nss = nat['stat_sum_numbers']
    checks = [('stations', len(rows), num(nss['number_of_stations'])),
              ('registered', S('upisani_biraci'), num(nss['total_voters'])),
              ('voted', S('glasali_biraci'), num(nss['available'])),
              ('valid', S('vazeci_glasovi'), nat['sum_config']['data']['datasets'][0]['data'][0]),
              ('invalid', S('nevazeci_listici'), nat['sum_config']['data']['datasets'][0]['data'][1])]
    checks += [(f'list {i}', S(f'lista_{i}'), num(r['won_number'])) for i, r in ((r['count_number'], r) for r in nat['table_data'])]
    bad = [c for c in checks if c[1] != c[2]]
    print(f'Wrote {out}.xlsx, {out}.csv, {out}_liste.csv ({len(rows)} stations, data as of {nss["datetime"]})')
    print('All totals match the national page.' if not bad else 'MISMATCHES (name, scraped, site): ' + str(bad))


if __name__ == '__main__':
    main()
