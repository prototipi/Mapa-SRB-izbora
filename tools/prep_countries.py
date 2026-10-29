"""Make geo/countries_abroad.json: simplified outlines of the countries with polling stations abroad.
Source: Natural Earth 1:10m admin 0 countries (public domain).
Per country, keep the land areas near its polling stations (no far islands or overseas territories)."""
import csv, json, math, sys

ne_path, stations_csv, out_path = sys.argv[1:4]

NAMES = {
    'AE': ('Уједињени Арапски Емирати', 'United Arab Emirates'), 'AT': ('Аустрија', 'Austria'), 'AU': ('Аустралија', 'Australia'),
    'BA': ('Босна и Херцеговина', 'Bosnia and Herzegovina'), 'BE': ('Белгија', 'Belgium'), 'BG': ('Бугарска', 'Bulgaria'),
    'BR': ('Бразил', 'Brazil'), 'CA': ('Канада', 'Canada'), 'CF': ('Централноафричка Република', 'Central African Republic'),
    'CH': ('Швајцарска', 'Switzerland'), 'CN': ('Кина', 'China'), 'CY': ('Кипар', 'Cyprus'), 'CZ': ('Чешка', 'Czechia'),
    'DE': ('Немачка', 'Germany'), 'DK': ('Данска', 'Denmark'), 'ES': ('Шпанија', 'Spain'), 'FI': ('Финска', 'Finland'),
    'FR': ('Француска', 'France'), 'GB': ('Уједињено Краљевство', 'United Kingdom'), 'GR': ('Грчка', 'Greece'),
    'HR': ('Хрватска', 'Croatia'), 'HU': ('Мађарска', 'Hungary'), 'ID': ('Индонезија', 'Indonesia'), 'IE': ('Ирска', 'Ireland'),
    'IT': ('Италија', 'Italy'), 'JP': ('Јапан', 'Japan'), 'LB': ('Либан', 'Lebanon'), 'LU': ('Луксембург', 'Luxembourg'),
    'ME': ('Црна Гора', 'Montenegro'), 'MK': ('Северна Македонија', 'North Macedonia'), 'MT': ('Малта', 'Malta'),
    'NL': ('Холандија', 'Netherlands'), 'NO': ('Норвешка', 'Norway'), 'NZ': ('Нови Зеланд', 'New Zealand'),
    'PL': ('Пољска', 'Poland'), 'PT': ('Португалија', 'Portugal'), 'RO': ('Румунија', 'Romania'), 'RU': ('Русија', 'Russia'),
    'SE': ('Шведска', 'Sweden'), 'SI': ('Словенија', 'Slovenia'), 'SK': ('Словачка', 'Slovakia'), 'TR': ('Турска', 'Türkiye'),
    'US': ('Сједињене Америчке Државе', 'United States'), 'ZA': ('Јужна Африка', 'South Africa'),
    'AL': ('Албанија', 'Albania'),
}


def hav(a, b):
    (lo1, la1), (lo2, la2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def area(ring):  # km², planar approximation
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    s = 0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2 * 111.32 ** 2 * math.cos(lat0)


def simplify(pts, tol):  # Douglas-Peucker on lon/lat (lon scaled by cos lat)
    if len(pts) < 4:
        return pts
    k = math.cos(math.radians(sum(p[1] for p in pts) / len(pts)))
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        x1 *= k; x2 *= k
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1e-12
        best, idx = -1, None
        for i in range(a + 1, b):
            px, py = pts[i][0] * k, pts[i][1]
            d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / L
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, f in zip(pts, keep) if f]


def clip(ring, x0, y0, x1, y1):  # Sutherland-Hodgman against a lon/lat box
    def cut(pts, inside, inter):
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if inside(p):
                if not inside(q):
                    out.append(inter(q, p))
                out.append(p)
            elif inside(q):
                out.append(inter(q, p))
        return out
    ix = lambda q, p, x: [x, q[1] + (p[1] - q[1]) * (x - q[0]) / (p[0] - q[0])]
    iy = lambda q, p, y: [q[0] + (p[0] - q[0]) * (y - q[1]) / (p[1] - q[1]), y]
    for inside, inter in ((lambda p: p[0] >= x0, lambda q, p: ix(q, p, x0)), (lambda p: p[0] <= x1, lambda q, p: ix(q, p, x1)),
                          (lambda p: p[1] >= y0, lambda q, p: iy(q, p, y0)), (lambda p: p[1] <= y1, lambda q, p: iy(q, p, y1))):
        ring = cut(ring, inside, inter)
        if not ring:
            return []
    return ring


stations = {}
for r in csv.DictReader(open(stations_csv, encoding='utf-8')):
    stations.setdefault(r['country_code'], set()).add((float(r['lon']), float(r['lat'])))
# Countries without polling stations that are drawn as context on the Region map (point = capital)
for cc, pt in {'AL': (19.82, 41.33)}.items():
    stations.setdefault(cc, set()).add(pt)

ne = {}  # several features can share a code (e.g. AU: Ashmore and Cartier Is.); keep the largest
for f in json.load(open(ne_path, encoding='utf-8'))['features']:
    cc = f['properties']['ISO_A2_EH']
    if cc not in ne or len(json.dumps(f['geometry'])) > len(json.dumps(ne[cc]['geometry'])):
        ne[cc] = f
out = {}
for cc, pts in sorted(stations.items()):
    g = ne[cc]['geometry']
    polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    pts = list(pts)
    span = max((hav(a, b) for a in pts for b in pts), default=0)
    reach = min(1500, max(900, 0.4 * span))
    cand = []
    for poly in polys:
        outer = poly[0]
        d = min(hav(s, v) for s in pts for v in outer[::max(1, len(outer) // 2000)])
        cand.append((d, area(outer), poly))
    near = [c for c in cand if c[0] <= reach]
    big = max(c[1] for c in near)
    kept = [c[2] for c in near if c[1] >= 0.003 * big]
    xs = [p[0] for poly in kept for p in poly[0]]
    ys = [p[1] for poly in kept for p in poly[0]]
    if max(xs) - min(xs) > 100:  # very wide country (Russia): crop around the stations
        sx, sy = [p[0] for p in pts], [p[1] for p in pts]
        box = (min(sx) - 15, min(sy) - 10, max(sx) + 15, max(sy) + 10)
        kept = [[c for c in (clip(r[:-1], *box) for r in poly) if len(c) >= 3] for poly in kept]
        kept = [p for p in kept if p]
        xs = [p[0] for poly in kept for p in poly[0]]
        ys = [p[1] for poly in kept for p in poly[0]]
    tol = max(max(xs) - min(xs), max(ys) - min(ys)) / 450
    res = []
    for poly in kept:
        rings = []
        for ring in poly:
            r = [p[:2] for p in ring[:-1]]  # closed ring: simplify the two halves
            m = len(r) // 2
            s = simplify(r[:m + 1], tol)[:-1] + simplify(r[m:] + r[:1], tol)
            if len(s) >= 4:
                r = [[round(x, 3), round(y, 3)] for x, y in s]
                r.append(r[0])
                signed = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(r, r[1:]))
                # d3-geo: exterior rings clockwise (negative planar area), holes counter-clockwise
                if (signed > 0) == (not rings):
                    r.reverse()
                rings.append(r)
        if rings:
            res.append(rings)
    out[cc] = {'sr': NAMES[cc][0], 'en': NAMES[cc][1], 'geometry': {'type': 'MultiPolygon', 'coordinates': res}}
    print(cc, NAMES[cc][1], f'{len(polys)}→{len(res)} polygons, {sum(len(r) for p in res for r in p)} points')
json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
