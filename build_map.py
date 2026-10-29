"""Build mapa_izbora.html: an interactive map of parliamentary election results by municipality,
for every election in ELECTIONS, with a view that compares the first and the last of them.

Usage:  py build_map.py
Input files, short list names and the compared pair of lists for each election are set in ELECTIONS below.
Only the Python standard library is needed.
"""
import csv, glob, json, math, os, re, sys, unicodedata, zipfile
from datetime import datetime
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'map_template.html')
# Output pages: one per language, from the same template. Texts: i18n_sr-latn.json (English -> Serbian Latin).
LANGS = {  # in the order of the language menu
    'sr-Latn': {'out': 'mapa_izbora_sr-latn.html', 'html': 'sr-Latn', 'locale': 'sr-Latn-RS', 'label': 'Srpski (latinica)'},
    'sr-Cyrl': {'out': 'mapa_izbora_sr-cyrl.html', 'html': 'sr-Cyrl', 'locale': 'sr-Cyrl-RS', 'label': 'Српски (ћирилица)'},
    'en': {'out': 'mapa_izbora.html', 'html': 'en', 'locale': 'en-US', 'label': 'English'},
}
I18N = os.path.join(HERE, 'i18n_sr-latn.json')
D3_JS = os.path.join(HERE, 'vendor', 'd3.v7.8.5.min.js')
GEO = [os.path.join(HERE, 'geo', 'gadm41_SRB_2.json'), os.path.join(HERE, 'geo', 'gadm41_XKO_2.json')]
PDF_PREFIX = 'https://www.rik.parlament.gov.rs/extfile/sr/election_results/'
PDF_PREFIX_RE = re.compile(r'^https://(www\.)?rik\.parlament\.gov\.rs/extfile/sr/election_results/')
# Polling stations abroad: city and coordinates per election and station number; outlines of their countries.
ABROAD_CSV = os.path.join(HERE, 'geo', 'abroad_stations.csv')
COUNTRIES_JSON = os.path.join(HERE, 'geo', 'countries_abroad.json')
# Region map: Serbia with the neighbouring countries (and Slovenia); context = outline only, no polling stations
REGION_COUNTRIES = ['HU', 'RO', 'BG', 'MK', 'ME', 'BA', 'HR', 'SI']
REGION_CONTEXT = ['AL']
# Polling stations in prisons: address and coordinates per station number (same institutions in every election)
PRISONS_CSV = os.path.join(HERE, 'geo', 'prison_stations.csv')

# Short display names for the lists, in English (full names come from the lists file, in Serbian Latin).
SHORT_2026 = {
    1: 'Aleksandar Vučić – United Serbia', 2: 'Ivica Dačić – SPS', 3: 'Student List',
    4: 'Rasim Ljajić – Ljudski', 5: 'Alliance of Vojvodina Hungarians', 6: 'Usame Zukorlić – SPP',
    7: 'Russian Party', 8: 'Authentic Right', 9: 'European Serbia', 10: 'SDA of Sandžak',
    11: 'Bogoljub Karić – BK', 12: 'Liberal Green Party', 13: 'I Choose Justice – Bulić',
    14: 'Russian-Serbian Unity Party', 15: 'Ćale ovo je za tebe', 16: 'Alternative for Serbia',
    17: 'Albanian Coalition', 18: 'Mother Serbia – Gruda',
}
SHORT_2023 = {
    1: 'Aleksandar Vučić – Serbia Must Not Stop', 2: 'Ivica Dačić – Prime Minister of Serbia', 3: 'Vojislav Šešelj – SRS',
    4: 'National Gathering', 5: 'Miloš Jovanović – Hope for Serbia', 6: 'Alliance of Vojvodina Hungarians',
    7: 'Serbia Against Violence', 8: 'Usame Zukorlić – United for Justice', 9: 'SDA of Sandžak – Ugljanin',
    10: 'Together for Future and Development', 11: "People's Party – Vuk Jeremić", 12: 'Radulović – Tadić – Pejić',
    13: 'Albanian Political Struggle – Kamberi', 14: 'We – Voice of the People', 15: 'Serbia in the West',
    16: 'Russian Party', 17: 'Čedomir Jovanović – Must Be Different', 18: 'Albanian Democratic Alternative',
}

# Parties for the "Other parties" view: name and color (close to the party's own color, and not used elsewhere in the page).
# Lists without a party key are shown as "Other".
PARTIES = {
    'SPS': ('SPS – Ivica Dačić', '#c2185b'),
    'SVM': ('SVM – Alliance of Vojvodina Hungarians', '#2e7d32'),
    'SDA': ('SDA of Sandžak', '#00897b'),
    'SPP': ('SPP – Usame Zukorlić', '#0288d1'),
    'ALB': ('Albanian lists', '#212121'),
    'NDSS': ('Miloš Jovanović – Hope for Serbia (2023), Authentic Right (2026)', '#795548'),
    'MI': ('MI – Voice of the People (Nestorović)', '#f9a825'),
    'NO': ('National Gathering (Dveri, Zavetnici)', '#827717'),
    'SRS': ('SRS – Vojislav Šešelj', '#455a64'),
    'RUS': ('Russian Party', '#8e24aa'),
    'SDPS': ('Rasim Ljajić – Ljudski (SDPS)', '#c0ca33'),
    'EU': ('European Serbia (Tepić, Ponoš)', '#ffb300'),
    'other': ('Other', '#9e9e9e'),
}

# Short list names in Serbian (Cyrillic; the Latin version is made from them)
SHORT_SR_2026 = {
    1: 'Александар Вучић – Уједињена Србија', 2: 'Ивица Дачић – СПС', 3: 'Студентска листа',
    4: 'Расим Љајић – Људски', 5: 'Савез војвођанских Мађара', 6: 'Усаме Зукорлић – СПП',
    7: 'Руска странка', 8: 'Аутентична десница', 9: 'Европска Србија', 10: 'СДА Санџака',
    11: 'Богољуб Карић – БК', 12: 'Либерално зелена странка', 13: 'Бирам правду – Булић',
    14: 'Странка руско-српског јединства', 15: 'Ћале ово је за тебе', 16: 'Алтернатива за Србију',
    17: 'Албанска коалиција', 18: 'Мајка Србија – Груда',
}
SHORT_SR_2023 = {
    1: 'Александар Вучић – Србија не сме да стане', 2: 'Ивица Дачић – Премијер Србије', 3: 'Војислав Шешељ – СРС',
    4: 'Национално окупљање', 5: 'Милош Јовановић – Нада за Србију', 6: 'Савез војвођанских Мађара',
    7: 'Србија против насиља', 8: 'Усаме Зукорлић – Уједињени за правду', 9: 'СДА Санџака – Угљанин',
    10: 'Заједно за будућност и развој', 11: 'Народна странка – Вук Јеремић', 12: 'Радуловић – Тадић – Пејић',
    13: 'Политичка борба Албанаца – Камбери', 14: 'МИ – Глас из народа', 15: 'Србија на западу',
    16: 'Руска странка', 17: 'Чедомир Јовановић – Мора другачије', 18: 'Албанска демократска алтернатива',
}
# Party names in Serbian Latin, for the "Other parties" view (Cyrillic is made from them)
PARTIES_SR = {
    'SPS': 'SPS – Ivica Dačić', 'SVM': 'SVM – Savez vojvođanskih Mađara', 'SDA': 'SDA Sandžaka', 'SPP': 'SPP – Usame Zukorlić',
    'ALB': 'Albanske liste', 'NDSS': 'Miloš Jovanović – Nada za Srbiju (2023), Autentična desnica (2026)',
    'MI': 'MI – Glas iz naroda (Nestorović)', 'NO': 'Nacionalno okupljanje (Dveri, Zavetnici)', 'SRS': 'SRS – Vojislav Šešelj',
    'RUS': 'Ruska stranka', 'SDPS': 'Rasim Ljajić – Ljudski (SDPS)', 'EU': 'Evropska Srbija (Tepić, Ponoš)', 'other': 'Ostale',
}

# English names for districts, regions and the two special units (keys: Serbian Cyrillic, as in the RIK export)
EN_PLACE = {
    'Град Београд': 'City of Belgrade', 'Севернобачки управни округ': 'North Bačka District',
    'Средњобанатски управни округ': 'Central Banat District', 'Севернобанатски управни округ': 'North Banat District',
    'Јужнобанатски управни округ': 'South Banat District', 'Западнобачки управни округ': 'West Bačka District',
    'Јужнобачки управни округ': 'South Bačka District', 'Сремски управни округ': 'Srem District',
    'Мачвански управни округ': 'Mačva District', 'Колубарски управни округ': 'Kolubara District',
    'Подунавски управни округ': 'Podunavlje District', 'Браничевски управни округ': 'Braničevo District',
    'Шумадијски управни округ': 'Šumadija District', 'Поморавски управни округ': 'Pomoravlje District',
    'Борски управни округ': 'Bor District', 'Зајечарски управни округ': 'Zaječar District',
    'Златиборски управни округ': 'Zlatibor District', 'Моравички управни округ': 'Moravica District',
    'Рашки управни округ': 'Raška District', 'Расински управни округ': 'Rasina District',
    'Нишавски управни округ': 'Nišava District', 'Топлички управни округ': 'Toplica District',
    'Пиротски управни округ': 'Pirot District', 'Јабланички управни округ': 'Jablanica District',
    'Пчињски управни округ': 'Pčinja District', 'Косовски управни округ': 'Kosovo District',
    'Пећки управни округ': 'Peć District', 'Призренски управни округ': 'Prizren District',
    'Косовскомитровачки управни округ': 'Kosovska Mitrovica District',
    'Косовскопоморавски управни округ': 'Kosovo-Pomoravlje District',
    'Београдски регион': 'Belgrade Region', 'Регион Војводине': 'Vojvodina Region',
    'Регион Шумадије и Западне Србије': 'Šumadija and Western Serbia Region',
    'Регион Јужне и Источне Србије': 'Southern and Eastern Serbia Region',
    'Регион Косово и Метохија': 'Kosovo and Metohija Region',
    'Иностранство': 'Abroad', 'Заводи за извршење кривичних санкција': 'Prisons',
}
# English names of cities abroad (the station file has Serbian Latin names); other cities keep their name
CITY_EN = {
    'Beč': 'Vienna', 'Salcburg': 'Salzburg', 'Linc': 'Linz', 'Brisel': 'Brussels', 'Sofija': 'Sofia',
    'Kopenhagen': 'Copenhagen', 'Rim': 'Rome', 'Milano': 'Milan', 'Trst': 'Trieste', 'Vićenca': 'Vicenza',
    'Valdanjo': 'Valdagno', 'Otava': 'Ottawa', 'Vankuver': 'Vancouver', 'Nikozija': 'Nicosia',
    'Ebel es Saki': 'Ebel es Saqi', 'Luksemburg': 'Luxembourg', 'Valeta': 'Valletta', 'Florijana': 'Floriana',
    'Budimpešta': 'Budapest', 'Diseldorf': 'Düsseldorf', 'Minhen': 'Munich', 'Štutgart': 'Stuttgart',
    'Okland': 'Auckland', 'Lisabon': 'Lisbon', 'Bukurešt': 'Bucharest', 'Moskva': 'Moscow', 'Soči': 'Sochi',
    'Skoplje': 'Skopje', 'Vašington': 'Washington', 'Čikago': 'Chicago', 'Njujork': 'New York',
    'Los Anđeles': 'Los Angeles', 'Abu Dabi': 'Abu Dhabi', 'Pariz': 'Paris', 'Strazbur': 'Strasbourg',
    'Hag': 'The Hague', 'Prag': 'Prague', 'Cirih': 'Zürich', 'Ženeva': 'Geneva', 'Stokholm': 'Stockholm',
    'Malme': 'Malmö', 'Melburn': 'Melbourne', 'Sidnej': 'Sydney', 'Brazilija': 'Brasília', 'Atina': 'Athens',
    'Džakarta': 'Jakarta', 'Dablin': 'Dublin', 'Tokio': 'Tokyo', 'Pretorija': 'Pretoria', 'Peking': 'Beijing',
    'Varšava': 'Warsaw', 'Beograd': 'Belgrade',
}

# results: newest file matching the pattern. pair: (main list, main challenger), compared by the "Lead" views.
# abbr: short party acronyms used in the page labels instead of "list N".
# party: list number -> party key in PARTIES, for the "Other parties" view (one color per party in both elections).
ELECTIONS = {
    '2023': {'results': 'rezultati_2023.xlsx', 'lists': 'rezultati_2023_liste.csv', 'short': SHORT_2023,
             'short_sr': SHORT_SR_2023, 'pair': (1, 7), 'abbr': {1: 'SNS', 7: 'SPN'}, 'origin': 'scraped from the RIK results page',
             'party': {2: 'SPS', 3: 'SRS', 4: 'NO', 5: 'NDSS', 6: 'SVM', 8: 'SPP', 9: 'SDA', 13: 'ALB', 14: 'MI', 16: 'RUS', 18: 'ALB'}},
    '2026': {'results': '[0-9][0-9]_[0-9][0-9]_[0-9][0-9]_*.2026.xlsx', 'lists': 'liste.ods', 'short': SHORT_2026,
             'short_sr': SHORT_SR_2026, 'pair': (1, 3), 'abbr': {1: 'SNS', 3: 'SL'}, 'origin': 'RIK polling-station export',
             'party': {2: 'SPS', 4: 'SDPS', 5: 'SVM', 6: 'SPP', 7: 'RUS', 8: 'NDSS', 9: 'EU', 10: 'SDA', 17: 'ALB'}},
}

# Data municipality code -> (GADM NAME_2, GADM NAME_1 or None), where name matching is not enough.
OVERRIDES = {
    '70912': ('Petrovac', None),                      # Петровац на Млави
    '80268': ('Bečej', 'Srednje-Banatski'),           # Нови Бечеј (GADM labels it "Bečej")
    '80110': ('Bečej', 'Južno-Bački'),
    '70203': ('Palilula', 'GradBeograd'),             # Палилула (Београд)
    '71331': ('Niš', None), '71323': ('Niš', None), '71315': ('Niš', None),
    '71307': ('Niš', None), '71285': ('Niš', None),   # city municipalities of Niš
    '71366': ('Užice', None),                         # Севојно
    '71340': ('Požarevac', None),                     # Костолац
    '90336': ('Dragaš', None),                        # Гора
    '71358': ('Vranje', None),                        # Врањска Бања (2023)
}
# Map units that hold several data municipalities get this display name.
MERGED_NAMES = {'Niš': 'Ниш', 'Užice': 'Ужице', 'Požarevac': 'Пожаревац', 'Vranje': 'Врање'}
SPECIAL = {'33000': 'abroad', '55001': 'prisons'}
# Kosovo shapes with no polling stations: their district (Serbian administrative districts), for the district and region views.
KOSOVO_REGION = 'Регион Косово и Метохија'
KOSOVO_EMPTY = {
    'Đakovica': 'Пећки управни округ', 'Dečani': 'Пећки управни округ',
    'Glogovac': 'Косовски управни округ', 'Podujevo': 'Косовски управни округ',
    'Kačanik': 'Косовски управни округ', 'Štimlje': 'Косовски управни округ',
    'SuvaReka': 'Призренски управни округ', 'Mališevo': 'Призренски управни округ',
}

CYR = dict(zip('абвгдђежзијклљмнњопрстћуфхцчџш',
               ['a', 'b', 'v', 'g', 'd', 'đ', 'e', 'ž', 'z', 'i', 'j', 'k', 'l', 'lj', 'm', 'n', 'nj',
                'o', 'p', 'r', 's', 't', 'ć', 'u', 'f', 'h', 'c', 'č', 'dž', 'š']))


LAT2CYR = [('Dž', 'Џ'), ('dž', 'џ'), ('Lj', 'Љ'), ('lj', 'љ'), ('Nj', 'Њ'), ('nj', 'њ')] + list(zip(
    'ABCČĆDĐEFGHIJKLMNOPRSŠTUVZŽabcčćdđefghijklmnoprsštuvzž',
    'АБЦЧЋДЂЕФГХИЈКЛМНОПРСШТУВЗЖабцчћдђефгхијклмнопрсштувзж'))


C2L = dict(zip('АБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШабвгдђежзијклљмнњопрстћуфхцчџш',
               ['A', 'B', 'V', 'G', 'D', 'Đ', 'E', 'Ž', 'Z', 'I', 'J', 'K', 'L', 'Lj', 'M', 'N', 'Nj', 'O', 'P', 'R', 'S',
                'T', 'Ć', 'U', 'F', 'H', 'C', 'Č', 'Dž', 'Š',
                'a', 'b', 'v', 'g', 'd', 'đ', 'e', 'ž', 'z', 'i', 'j', 'k', 'l', 'lj', 'm', 'n', 'nj', 'o', 'p', 'r', 's',
                't', 'ć', 'u', 'f', 'h', 'c', 'č', 'dž', 'š']))


def cyr2lat(s):
    """Serbian Cyrillic to Serbian Latin. Љ, Њ, Џ become LJ, NJ, DŽ inside upper-case words."""
    if not s:
        return s
    out = []
    for i, ch in enumerate(s):
        t = C2L.get(ch, ch)
        if len(t) == 2 and ch.isupper():
            nxt = s[i + 1] if i + 1 < len(s) else ''
            prv = s[i - 1] if i else ''
            if nxt.isupper() or (not nxt.isalpha() and prv.isupper()):
                t = t.upper()
        out.append(t)
    return ''.join(out)


def en_place(name):
    if name not in EN_PLACE:
        raise SystemExit(f'No English name for "{name}"; add it to EN_PLACE')
    return EN_PLACE[name]


def lat2cyr(s):
    for a, b in LAT2CYR:
        s = s.replace(a, b)
    return s


def norm(s):
    s = ''.join(CYR.get(ch, ch) for ch in s.lower()).replace('đ', 'd')
    s = unicodedata.normalize('NFKD', s)
    return re.sub(r'[^a-z]', '', ''.join(ch for ch in s if not unicodedata.combining(ch)))


def strip_prefix(name):
    name = re.sub(r'^(Градска општина|Град)\s+', '', name)
    return re.sub(r'\s*\(.*\)$', '', name)


# ---------- spreadsheet readers (stdlib only) ----------
XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def read_xlsx(path):
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(XNS + 'si'):
            shared.append(''.join(t.text or '' for t in si.iter(XNS + 't')))
    rows = []
    for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter(XNS + 'row'):
        vals = {}
        for c in row.findall(XNS + 'c'):
            col = 0
            for ch in re.match(r'[A-Z]+', c.get('r')).group(0):
                col = col * 26 + ord(ch) - 64
            v = c.find(XNS + 'v')
            if c.get('t') == 's':
                val = shared[int(v.text)]
            elif c.get('t') == 'inlineStr':
                val = ''.join(t.text or '' for t in c.iter(XNS + 't'))
            else:
                val = v.text if v is not None else None
            vals[col - 1] = val
        rows.append([vals.get(i) for i in range(max(vals) + 1)] if vals else [])
    width = max(map(len, rows), default=0)  # empty trailing cells are not stored; pad to full width
    return [r + [None] * (width - len(r)) for r in rows]


def read_ods(path):
    T = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
    TX = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
    OF = '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'
    table = next(ET.fromstring(zipfile.ZipFile(path).read('content.xml')).iter(T + 'table'))
    rows = []
    for row in table.iter(T + 'table-row'):
        cells = []
        for c in row:
            n = min(int(c.get(T + 'number-columns-repeated', '1')), 20)
            text = '\n'.join(''.join(p.itertext()) for p in c.findall(TX + 'p'))
            cells.extend([c.get(OF + 'value') or text] * n)
        rows.append(cells)
    return rows


def read_lists(path):
    if path.lower().endswith('.csv'):
        return list(csv.reader(open(path, encoding='utf-8-sig')))
    return read_ods(path)


def parse_time(t):
    for f in ('%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M:%S'):
        try:
            return datetime.strptime(t, f)
        except (TypeError, ValueError):
            pass
    return None


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def group_borders(geo, levels, delta=0.002):
    """Borders of groups of municipality shapes (districts, regions), as lines per group.
    A segment shared exactly by two shapes is a border when the two shapes are in different groups.
    Neighbouring GADM shapes do not always share their points, so for any other segment the points
    `delta` degrees to each side of its middle are tested: it is a border unless both are in the same group."""
    rings = []
    for f in geo:
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        rings.append([[tuple(p) for p in r] for poly in polys for r in poly])
    boxes = [(min(p[0] for r in rs for p in r), min(p[1] for r in rs for p in r),
              max(p[0] for r in rs for p in r), max(p[1] for r in rs for p in r)) for rs in rings]

    def shape_at(x, y):
        for i, (x0, y0, x1, y1) in enumerate(boxes):
            if x0 <= x <= x1 and y0 <= y <= y1:
                inside = False
                for r in rings[i]:
                    for (ax, ay), (bx, by) in zip(r, r[1:]):
                        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                            inside = not inside
                if inside:
                    return i
        return None

    owners = {}
    for i, rs in enumerate(rings):
        for r in rs:
            for a, b in zip(r, r[1:]):
                if a != b:
                    owners.setdefault((min(a, b), max(a, b)), []).append(i)
    segs = {lv: {} for lv in levels}
    for (a, b), fs in owners.items():
        if len(fs) >= 2:
            sides = (fs[0], fs[1])
        else:
            mx, my, dx, dy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            nx, ny = -dy / L * delta, dx / L * delta
            sides = (shape_at(mx + nx, my + ny), shape_at(mx - nx, my - ny))
        for lv, prop in levels.items():
            keys = [geo[i]['properties'][prop] if i is not None else None for i in sides]
            own = [geo[i]['properties'][prop] for i in fs]
            if len(fs) >= 2:
                if keys[0] != keys[1]:
                    for k in keys:
                        segs[lv].setdefault(k, []).append((a, b))
            elif not (keys[0] == keys[1] == own[0]):
                segs[lv].setdefault(own[0], []).append((a, b))
    return {lv: {k: chain(s) for k, s in groups.items()} for lv, groups in segs.items()}


def chain(segments):
    """Join segments into as few lines as possible."""
    adj = {}
    for a, b in segments:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    used, lines = set(), []
    for start in sorted(adj, key=lambda p: len(adj[p]) % 2 == 0):  # line ends first
        for nxt in adj[start]:
            if (start, nxt) in used:
                continue
            line, cur = [start], start
            while True:
                step = next((q for q in adj[cur] if (cur, q) not in used), None)
                if step is None:
                    break
                used.add((cur, step)); used.add((step, cur))
                line.append(step)
                cur = step
            lines.append([list(p) for p in line])
    return lines


def load_lists(path, short_en, short_sr, abbr, party):
    """Lists with their names in Serbian Cyrillic (as in the RIK data); localize() makes the names for each language."""
    lists = []
    for r in read_lists(path)[1:]:
        if len(r) >= 3 and r[0].strip().isdigit():
            n = int(r[0])
            full = re.sub(r'^\d+\.\s*ИЗБОРНА ЛИСТА\s*[-–]?\s*', '', r[1]).strip()
            lists.append({'n': n, 'short_en': short_en.get(n, cyr2lat(full)[:40]), 'short_sr': short_sr.get(n, full[:40]),
                          'abbr': abbr.get(n), 'party': party.get(n, 'other'), 'full': full,
                          'odsVotes': num(r[2]), 'odsPct': float(r[3]) if len(r) > 3 and r[3] else None})
    return sorted(lists, key=lambda l: l['n'])


def latin_to(lang, s):
    """Serbian Latin text in the script of `lang`. {placeholders} and 'PDF' stay as they are."""
    if lang != 'sr-Cyrl' or not s:
        return s
    parts = re.split(r'(\{[a-z0-9_]+\}|PDF)', s)
    return ''.join(p if re.fullmatch(r'\{[a-z0-9_]+\}|PDF', p) else lat2cyr(p) for p in parts)


def localize(raw, lang, tr):
    """Copy of the page data with all names and texts in `lang` (en, sr-Latn or sr-Cyrl)."""
    en = lang == 'en'
    name = lambda s: s if lang == 'sr-Cyrl' else cyr2lat(s)        # Serbian names, source in Cyrillic
    place = lambda s: en_place(s) if en else name(s)               # districts, regions, Abroad, Prisons
    abroad_city = lambda s: CITY_EN.get(s, s) if en else latin_to(lang, s)   # source in Serbian Latin
    prison_city = lambda s: CITY_EN.get(cyr2lat(s), cyr2lat(s)) if en else name(s)
    elections = {}
    for y, E in raw['E'].items():
        elections[y] = dict(E,
            lists=[{'n': l['n'], 'short': l['short_en'] if en else name(l['short_sr']),
                    'abbr': latin_to(lang, l['abbr']) if l['abbr'] else None, 'party': l['party'], 'full': name(l['full']),
                    'odsVotes': l['odsVotes'], 'odsPct': l['odsPct']} for l in E['lists']],
            munis=[place(m) if m in EN_PLACE else name(m) for m in E['munis']],
            stations=[s[:3] + [name(s[3])] + s[4:] for s in E['stations']],
            loc={i: [cc, abroad_city(c), lon, lat] for i, (cc, c, lon, lat) in E['loc'].items()},
            ploc={i: [prison_city(c), cyr2lat(a) if en else name(a), lon, lat] for i, (c, a, lon, lat) in E['ploc'].items()})
    geo = []
    for f in raw['geo']:
        p = dict(f['properties'], d=place(f['properties']['d']), r=place(f['properties']['r']))
        if 'name' in p:
            p['name'] = latin_to(lang, p['name'])
        geo.append({'type': 'Feature', 'properties': p, 'geometry': f['geometry']})
    return {
        'lang': lang, 'locale': LANGS[lang]['locale'],
        'i18n': {} if en else {k: latin_to(lang, v) for k, v in tr.items()},
        'E': elections,
        'pdfPrefix': PDF_PREFIX,
        'parties': {k: {'name': n if en else latin_to(lang, PARTIES_SR[k]), 'color': c} for k, (n, c) in PARTIES.items()},
        'units': [{'key': u['key'], 'name': place(u['name']) if u['name'] in EN_PLACE else name(u['name']),
                   'district': place(u['district']), 'region': place(u['region']),
                   'munis': [place(m) if m in EN_PLACE else name(strip_prefix(m)) for m in u['munis']], 'city': u.get('city', False)}
                  for u in raw['units']],
        'geo': {'type': 'FeatureCollection', 'features': geo},
        'borders': {lv: {(k if lv == 'country' else place(k)): lines for k, lines in groups.items()} for lv, groups in raw['borders'].items()},
        'countries': {cc: {'en': c['en'], 'name': c['en'] if en else name(c['sr']), 'geometry': c['geometry']} for cc, c in raw['countries'].items()},
        'region': raw['region'],
    }


def main():
    # Geometry
    if not all(os.path.exists(p) for p in GEO):
        sys.exit('GADM boundaries not found in geo/. Run: python tools/fetch_gadm.py')
    features = []
    for path in GEO:
        for f in json.load(open(path, encoding='utf-8'))['features']:
            p = f['properties']
            features.append({'gid': p['GID_2'], 'name2': p['NAME_2'], 'name1': p['NAME_1'],
                             'nl': p['NL_NAME_2'].split('|')[0].rstrip(')'), 'kosovo': p['GID_0'] == 'XKO',
                             'geom': f['geometry']})
    by_norm = {}
    for i, f in enumerate(features):
        by_norm.setdefault(norm(f['name2']), []).append(i)

    def find_feature(code, name):
        if code in OVERRIDES:
            n2, n1 = OVERRIDES[code]
            hits = [i for i in by_norm.get(norm(n2), []) if n1 is None or features[i]['name1'] == n1]
        else:
            hits = by_norm.get(norm(strip_prefix(name)), [])
        if len(hits) != 1:
            raise SystemExit(f'No unique map shape for {code} {name}: {hits}')
        return hits[0]

    # Map units are shared by all elections; each election has its own stations.
    units, unit_index = [], {}

    def unit_for(code, oname, okrug):
        key = SPECIAL.get(code) or features[find_feature(code, oname)]['gid']
        if key not in unit_index:
            unit_index[key] = len(units)
            units.append({'key': key, 'district': okrug.split('/')[-1], 'region': okrug.split('/')[0], 'munis': []})
        u = units[unit_index[key]]
        if oname not in u['munis']:
            u['munis'].append(oname)
        return unit_index[key]

    def short_link(cell):
        link = (cell or '').split('|')[-1].strip()
        return PDF_PREFIX_RE.sub('', link)

    # Names are kept in their source form (Serbian Cyrillic, abroad cities in Serbian Latin); localize() translates them.
    abroad_loc = {(r['year'], int(r['bm_broj'])): [r['country_code'], r['city'], float(r['lon']), float(r['lat'])]
                  for r in csv.DictReader(open(ABROAD_CSV, encoding='utf-8'))}
    countries = json.load(open(COUNTRIES_JSON, encoding='utf-8'))
    prison_loc = {int(r['bm_broj']): [r['city'], r['address'], float(r['lon']), float(r['lat'])]
                  for r in csv.DictReader(open(PRISONS_CSV, encoding='utf-8'))}

    elections, reports = {}, []
    for year, E in ELECTIONS.items():
        xlsx = max(glob.glob(os.path.join(HERE, E['results'])), key=os.path.getmtime)
        lists = load_lists(os.path.join(HERE, E['lists']), E['short'], E['short_sr'], E.get('abbr', {}), E.get('party', {}))
        nl = len(lists)
        rows = read_xlsx(xlsx)
        H = {k: i for i, k in enumerate(rows[0])}
        unit_of_code, munis, muni_index, stations, updated, loc, ploc = {}, [], {}, [], set(), {}, {}
        for r in rows[1:]:
            if not r or r[H['bm_uid']] is None:
                continue
            code, oname = r[H['sifra_opstine']], r[H['opstina']]
            if code not in unit_of_code:
                unit_of_code[code] = unit_for(code, oname, r[H['okrug_region']])
                muni_index[code] = len(munis)
                munis.append(strip_prefix(oname) if code not in SPECIAL else oname)
            if SPECIAL.get(code) == 'abroad':
                bm = num(r[H['bm_broj']])
                if (year, bm) not in abroad_loc:
                    raise SystemExit(f'{year}: no location in {ABROAD_CSV} for station abroad {bm} {r[H["bm_naziv"]]}')
                loc[len(stations)] = abroad_loc[(year, bm)]
                if abroad_loc[(year, bm)][0] not in countries:
                    raise SystemExit(f'{year}: no outline in {COUNTRIES_JSON} for country {abroad_loc[(year, bm)][0]}')
            if SPECIAL.get(code) == 'prisons':
                bm = num(r[H['bm_broj']])
                if bm not in prison_loc:
                    raise SystemExit(f'{year}: no location in {PRISONS_CSV} for prison station {bm} {r[H["bm_naziv"]]}')
                ploc[len(stations)] = prison_loc[bm]
            t = r[H['vreme_unosa_rezultata']]
            reported = bool(t) and t != '-'
            if reported and parse_time(t):
                updated.add(parse_time(t))
            stations.append([
                unit_of_code[code], muni_index[code], num(r[H['bm_broj']]), r[H['bm_naziv']],
                num(r[H['upisani_biraci']]), num(r[H['glasali_biraci']]), num(r[H['vazeci_glasovi']]),
                num(r[H['nevazeci_listici']]), 1 if reported else 0,
                [num(r[H['lista_%d' % i]]) for i in range(1, nl + 1)],
                short_link(r[H['zapisnik_link']]), short_link(r[H['korekcija_dokument_link']]),
            ])
        elections[year] = {
            'pair': [E['pair'][0] - 1, E['pair'][1] - 1],
            'source': os.path.basename(xlsx), 'origin': E['origin'],
            'updated': max(updated).strftime('%d.%m.%Y %H:%M').lstrip('0') if updated else None,
            'lists': lists, 'munis': munis, 'stations': stations,
            'loc': loc,  # station index -> [country code, city, lon, lat], stations abroad only
            'ploc': ploc,  # station index -> [city, address, lon, lat], stations in prisons only
        }
        tot = [sum(s[9][i] for s in stations) for i in range(nl)]
        diffs = [(l['n'], tot[i] - l['odsVotes']) for i, l in enumerate(lists) if tot[i] != l['odsVotes']]
        name = os.path.basename(E['lists'])
        reports.append(f'{year}: {len(stations)} stations, {sum(s[8] for s in stations)} reported, '
                       f'{len(unit_of_code)} municipalities, updated {elections[year]["updated"]}; '
                       + (f'vote totals match {name}' if not diffs else f'DIFFERENCES vs {name} (list, xlsx-lists): {diffs}'))

    # Unit names (source form)
    for u in units:
        if u['key'] in SPECIAL.values():
            u['name'] = {'abroad': 'Иностранство', 'prisons': 'Заводи за извршење кривичних санкција'}[u['key']]
            continue
        f = next(f for f in features if f['gid'] == u['key'])
        u['name'] = MERGED_NAMES.get(f['name2']) if len(u['munis']) > 1 else strip_prefix(u['munis'][0])
        u['city'] = any(m.startswith('Град ') for m in u['munis'])

    # GeoJSON with rounded coordinates
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 4), round(c[1], 4)]

    geo = []
    for f in features:
        ui = unit_index.get(f['gid'], -1)
        props = {'u': ui, 'k': 1 if f['kosovo'] else 0, 'c': 'Serbia'}  # c: one group for the whole country (Region map)
        if ui < 0:
            props['name'] = re.sub(r'(?<=[a-zčćđšž])(?=[A-ZČĆĐŠŽ])', ' ', f['name2'])  # Serbian Latin
            if f['name2'] not in KOSOVO_EMPTY:
                raise SystemExit(f'No district for the empty shape {f["name2"]}; add it to KOSOVO_EMPTY')
            props['d'], props['r'] = KOSOVO_EMPTY[f['name2']], KOSOVO_REGION
        else:
            props['d'], props['r'] = units[ui]['district'], units[ui]['region']
        for k in (props['d'], props['r']):
            en_place(k)  # every district and region needs an English name
        geo.append({'type': 'Feature', 'properties': props,
                    'geometry': {'type': f['geom']['type'], 'coordinates': rnd(f['geom']['coordinates'])}})

    # Borders of districts, regions and the whole country, made from the municipality shapes
    borders = group_borders(geo, {'district': 'd', 'region': 'r', 'country': 'c'})

    raw = {
        'E': elections, 'units': units, 'geo': geo, 'borders': borders,
        'countries': {cc: countries[cc] for cc in sorted({l[0] for e in elections.values() for l in e['loc'].values()} | set(REGION_CONTEXT))},
        'region': REGION_COUNTRIES + REGION_CONTEXT,
    }

    # Translations of the page texts: English text -> Serbian Latin (Cyrillic is made from the Latin)
    tr = json.load(open(I18N, encoding='utf-8'))
    template = open(TEMPLATE, encoding='utf-8').read()
    keys = set(re.findall(r"\bt\('((?:[^'\\]|\\.)*)'", template)) | set(re.findall(r'\{\{t:(.*?)\}\}', template))
    missing = sorted(k for k in keys if k not in tr)
    if missing:
        print('MISSING TRANSLATIONS (shown in English):\n  ' + '\n  '.join(missing))
    d3 = open(D3_JS, encoding='utf-8').read()  # included in the page, so it works offline
    print('\n'.join(reports))
    for lang, L in LANGS.items():
        data = localize(raw, lang, tr)
        blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
        links = ''.join(f'<option value="{M["out"]}" lang="{M["html"]}"{" selected" if k == lang else ""}>{M["label"]}</option>'
                        for k, M in LANGS.items())
        html = template.replace('/*__D3__*/', d3).replace('/*__DATA__*/null', blob).replace('__LANG__', L['html']).replace('<!--LANGS-->', links)
        html = re.sub(r'\{\{t:(.*?)\}\}', lambda m: m.group(1) if lang == 'en' else latin_to(lang, tr.get(m.group(1), m.group(1))), html)
        out = os.path.join(HERE, L['out'])
        open(out, 'w', encoding='utf-8').write(html)
        print(f'{lang}: wrote {out} ({os.path.getsize(out) // 1024} KB)')
    print(f'{len(units)} map units, {len(geo)} shapes')


if __name__ == '__main__':
    main()
