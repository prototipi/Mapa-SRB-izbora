"""Make geo/abroad_stations.csv: city and coordinates for every polling station abroad, 2023 and 2026.
2026: station numbers, cities and addresses from dijaspora-glasanje.vercel.app (transcribed from the RIK decision).
2023: cities from the MFA list (mfa.gov.rs, 14.12.2023) in station order, matched with the station names.
Coordinates: OpenStreetMap Nominatim, city level."""
import csv, json, sys, time, urllib.parse, urllib.request

st26_path, out_path = sys.argv[1], sys.argv[2]

# City key -> (Nominatim query, ISO country code, Serbian Latin city name)
CITIES = {
    'vienna': ('Vienna', 'at', 'Beč'), 'salzburg': ('Salzburg', 'at', 'Salcburg'), 'linz': ('Linz', 'at', 'Linc'),
    'brussels': ('Brussels', 'be', 'Brisel'), 'sarajevo': ('Sarajevo', 'ba', 'Sarajevo'),
    'banjaluka': ('Banja Luka', 'ba', 'Banja Luka'), 'mostar': ('Mostar', 'ba', 'Mostar'), 'drvar': ('Drvar', 'ba', 'Drvar'),
    'trebinje': ('Trebinje', 'ba', 'Trebinje'), 'bijeljina': ('Bijeljina', 'ba', 'Bijeljina'), 'bratunac': ('Bratunac', 'ba', 'Bratunac'),
    'visegrad': ('Višegrad', 'ba', 'Višegrad'), 'doboj': ('Doboj', 'ba', 'Doboj'), 'zvornik': ('Zvornik', 'ba', 'Zvornik'),
    'branjevo': ('Branjevo, Zvornik', 'ba', 'Branjevo'), 'lopare': ('Lopare', 'ba', 'Lopare'), 'prijedor': ('Prijedor', 'ba', 'Prijedor'),
    'rudo': ('Rudo', 'ba', 'Rudo'), 'mrkonjic': ('Mrkonjić Grad', 'ba', 'Mrkonjić Grad'), 'pale': ('Pale', 'ba', 'Pale'),
    'novogorazde': ('Novo Goražde', 'ba', 'Novo Goražde'), 'vlasenica': ('Vlasenica', 'ba', 'Vlasenica'),
    'sokolac': ('Sokolac', 'ba', 'Sokolac'), 'foca': ('Foča', 'ba', 'Foča'), 'rogatica': ('Rogatica', 'ba', 'Rogatica'),
    'modrica': ('Modriča', 'ba', 'Modriča'), 'gradiska': ('Gradiška', 'ba', 'Gradiška'), 'ugljevik': ('Ugljevik', 'ba', 'Ugljevik'),
    'brcko': ('Brčko', 'ba', 'Brčko'), 'sofia': ('Sofia', 'bg', 'Sofija'), 'copenhagen': ('Copenhagen', 'dk', 'Kopenhagen'),
    'rome': ('Rome', 'it', 'Rim'), 'milan': ('Milan', 'it', 'Milano'), 'trieste': ('Trieste', 'it', 'Trst'),
    'vicenza': ('Vicenza', 'it', 'Vićenca'), 'valdagno': ('Valdagno', 'it', 'Valdanjo'), 'ottawa': ('Ottawa', 'ca', 'Otava'),
    'vancouver': ('Vancouver', 'ca', 'Vankuver'), 'toronto': ('Toronto', 'ca', 'Toronto'), 'nicosia': ('Nicosia', 'cy', 'Nikozija'),
    'ebel': ('Ebel es Saqi', 'lb', 'Ebel es Saki'), 'luxembourg': ('Luxembourg', 'lu', 'Luksemburg'),
    'valletta': ('Valletta', 'mt', 'Valeta'), 'floriana': ('Floriana', 'mt', 'Florijana'), 'budapest': ('Budapest', 'hu', 'Budimpešta'),
    'berlin': ('Berlin', 'de', 'Berlin'), 'dusseldorf': ('Düsseldorf', 'de', 'Diseldorf'), 'munich': ('Munich', 'de', 'Minhen'),
    'stuttgart': ('Stuttgart', 'de', 'Štutgart'), 'frankfurt': ('Frankfurt am Main', 'de', 'Frankfurt'), 'hamburg': ('Hamburg', 'de', 'Hamburg'),
    'auckland': ('Auckland', 'nz', 'Okland'), 'oslo': ('Oslo', 'no', 'Oslo'), 'lisbon': ('Lisbon', 'pt', 'Lisabon'),
    'bucharest': ('Bucharest', 'ro', 'Bukurešt'), 'moscow': ('Moscow', 'ru', 'Moskva'), 'sochi': ('Sochi', 'ru', 'Soči'),
    'skopje': ('Skopje', 'mk', 'Skoplje'), 'kumanovo': ('Kumanovo', 'mk', 'Kumanovo'), 'washington': ('Washington, D.C.', 'us', 'Vašington'),
    'chicago': ('Chicago', 'us', 'Čikago'), 'newyork': ('New York City', 'us', 'Njujork'), 'losangeles': ('Santa Monica', 'us', 'Los Anđeles'),
    'bratislava': ('Bratislava', 'sk', 'Bratislava'), 'ljubljana': ('Ljubljana', 'si', 'Ljubljana'), 'istanbul': ('Istanbul', 'tr', 'Istanbul'),
    'abudhabi': ('Abu Dhabi', 'ae', 'Abu Dabi'), 'london': ('London', 'gb', 'London'), 'helsinki': ('Helsinki', 'fi', 'Helsinki'),
    'paris': ('Paris', 'fr', 'Pariz'), 'strasbourg': ('Strasbourg', 'fr', 'Strazbur'), 'hague': ('The Hague', 'nl', 'Hag'),
    'zagreb': ('Zagreb', 'hr', 'Zagreb'), 'vukovar': ('Vukovar', 'hr', 'Vukovar'), 'bangui': ('Bangui', 'cf', 'Bangui'),
    'podgorica': ('Podgorica', 'me', 'Podgorica'), 'hercegnovi': ('Herceg Novi', 'me', 'Herceg Novi'), 'berane': ('Berane', 'me', 'Berane'),
    'sutomore': ('Sutomore', 'me', 'Sutomore'), 'prague': ('Prague', 'cz', 'Prag'), 'bern': ('Bern', 'ch', 'Bern'),
    'zurich': ('Zürich', 'ch', 'Cirih'), 'geneva': ('Geneva', 'ch', 'Ženeva'), 'lugano': ('Lugano', 'ch', 'Lugano'),
    'stockholm': ('Stockholm', 'se', 'Stokholm'), 'malmo': ('Malmö', 'se', 'Malme'), 'madrid': ('Madrid', 'es', 'Madrid'),
    'melbourne': ('Melbourne', 'au', 'Melburn'), 'sydney': ('Sydney', 'au', 'Sidnej'), 'brasilia': ('Brasília', 'br', 'Brazilija'),
    'athens': ('Athens', 'gr', 'Atina'), 'jakarta': ('Jakarta', 'id', 'Džakarta'), 'dublin': ('Blanchardstown, Dublin', 'ie', 'Dablin'),
    'tokyo': ('Tokyo', 'jp', 'Tokio'), 'pretoria': ('Pretoria', 'za', 'Pretorija'), 'beijing': ('Beijing', 'cn', 'Peking'),
    'warsaw': ('Warsaw', 'pl', 'Varšava'),
}

# 2023: station number -> city key (MFA list order, station names; BiH schools matched to the 2026 addresses)
S23 = ['vienna'] * 3 + ['salzburg', 'linz', 'brussels', 'sarajevo', 'banjaluka', 'banjaluka', 'mostar', 'drvar', 'trebinje',
       'bijeljina', 'bijeljina', 'bratunac', 'visegrad', 'doboj', 'zvornik', 'branjevo', 'lopare', 'prijedor', 'rudo', 'mrkonjic',
       'pale', 'novogorazde', 'sofia', 'copenhagen', 'rome', 'milan', 'trieste', 'vicenza', 'valdagno', 'ottawa', 'vancouver',
       'toronto', 'nicosia', 'ebel', 'luxembourg', 'valletta', 'budapest', 'berlin', 'dusseldorf', 'munich', 'stuttgart',
       'frankfurt', 'hamburg', 'auckland', 'oslo', 'lisbon', 'bucharest', 'moscow', 'sochi', 'skopje', 'kumanovo', 'washington',
       'chicago', 'newyork', 'bratislava', 'ljubljana', 'istanbul', 'abudhabi', 'london', 'helsinki', 'paris', 'strasbourg',
       'hague', 'zagreb', 'vukovar', 'bangui', 'podgorica', 'hercegnovi', 'sutomore', 'berane', 'prague', 'bern', 'zurich',
       'geneva', 'lugano', 'stockholm', 'malmo', 'madrid']
assert len(S23) == 81, len(S23)

# 2026: city names in the vercel data (Serbian Latin) -> city key
BY_SR = {v[2]: k for k, v in CITIES.items()}
BY_SR.update({'Banja Luka': 'banjaluka', 'Mrkonjić Grad': 'mrkonjic', 'Los Anđeles': 'losangeles'})
st26 = json.load(open(st26_path, encoding='utf-8'))
S26 = {}
for no, cc, _, city, name, address, _ in st26:
    key = BY_SR[city]
    assert CITIES[key][1] == cc.lower(), (no, city, cc)
    S26[no] = (key, address)

# Set by hand: not found, or Nominatim returned a region or country centre instead of the city.
MANUAL = {'ebel': (33.3667, 35.6167),       # UNIFIL base 7-2 near Ebel es Saqi (Ibl al-Saqi), south Lebanon
          'moscow': (55.7558, 37.6173), 'luxembourg': (49.6117, 6.13)}
coords = dict(MANUAL)
for key, (q, cc, _) in CITIES.items():
    if key in MANUAL:
        continue
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({'q': q, 'countrycodes': cc, 'format': 'json', 'limit': 1})
    req = urllib.request.Request(url, headers={'User-Agent': 'analiza_izbora election map (research)'})
    res = json.loads(urllib.request.urlopen(req, timeout=30).read())
    coords[key] = (round(float(res[0]['lat']), 4), round(float(res[0]['lon']), 4)) if res else None
    print(key, coords[key], res[0]['display_name'][:70] if res else 'NOT FOUND', flush=True)
    time.sleep(1.1)

with open(out_path, 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f)
    w.writerow(['year', 'bm_broj', 'city', 'country_code', 'lat', 'lon', 'address'])
    for i, key in enumerate(S23, start=1):
        w.writerow(['2023', i, CITIES[key][2], CITIES[key][1].upper(), *coords[key], ''])
    for no in sorted(S26):
        key, address = S26[no]
        w.writerow(['2026', no, CITIES[key][2], CITIES[key][1].upper(), *coords[key], address])
print('missing:', [k for k, v in coords.items() if v is None])
