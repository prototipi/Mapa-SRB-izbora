"""Make geo/prison_stations.csv: address and coordinates of the 29 polling stations in prisons.
Names and addresses: RIK decision on voting places in prisons for the referendum of 16.01.2022
(https://www.rik.parlament.gov.rs/extfile/sr/13692/Resenje%20o%20odredjivanju%20glasackih%20mesta%20u%20zavodima%20c.doc).
The station numbers and institution types in 2023 and 2026 follow the same order, so the stations are matched by number.
Coordinates: OpenStreetMap Nominatim, by address where it is found, otherwise by place. Run: py tools/locate_prisons.py"""
import csv, json, pathlib, time, urllib.parse, urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / 'geo' / 'prison_stations.csv'

# Station number: (name in the 2022 decision, city, address, Nominatim street query or None)
PRISONS = {
    1: ('Окружни затвор', 'Београд', 'Бачванска 14', 'Bačvanska 14, Beograd'),
    2: ('Специјална затворска болница', 'Београд', 'Бачванска 14', 'Bačvanska 14, Beograd'),
    3: ('Казнено-поправни завод - Београд', 'Београд', 'Зрењанински пут бб', None),
    4: ('Казнено-поправни завод - Падинска Скела', 'Београд', 'Зрењанински пут бб', None),
    5: ('Окружни затвор', 'Суботица', 'Лењинов парк 1', 'Lenjinov park 1, Subotica'),
    6: ('Окружни затвор', 'Зрењанин', 'Гундулићева 1', 'Gundulićeva 1, Zrenjanin'),
    7: ('Казнено-поправни завод', 'Панчево', 'Баваништански пут бб', None),
    8: ('Казнено-поправни завод', 'Сомбор', 'Стапарски пут 1', None),
    9: ('Окружни затвор', 'Нови Сад', 'Пролетерска 16а', 'Proleterska 16, Novi Sad'),
    10: ('Казнено-поправни завод', 'Сремска Митровица', 'Фрушкогорска бб', None),
    11: ('Казнено-поправни завод', 'Шабац', 'Стевана Првовенчаног бб', None),
    12: ('Казнено-поправни завод за малолетнике', 'Ваљево', 'Лознички пут бб', None),
    13: ('Окружни затвор', 'Смедерево', 'Трг Републике 4', 'Trg Republike 4, Smederevo'),
    14: ('Казнено-поправни завод за жене', 'Пожаревац', 'Моше Пијаде бб', None),
    15: ('Казнено-поправни завод Забела', 'Пожаревац', 'Забелски пут бб', None),
    16: ('Окружни затвор (2023, 2026: казнено-поправни завод)', 'Крагујевац', 'Млавска бб', None),
    17: ('Казнено-поправни завод', 'Ћуприја', 'Данила Димитријевића 7а', None),
    18: ('Окружни затвор', 'Неготин', 'Бранка Перића 9', 'Branka Perića 9, Negotin'),
    19: ('Окружни затвор', 'Зајечар', 'Изворски пут бб', None),
    20: ('Окружни затвор', 'Ужице', 'Наде Матић 4', 'Nade Matić 4, Užice'),
    21: ('Окружни затвор', 'Чачак', 'Цара Душана 3/1', 'Cara Dušana 3, Čačak'),
    22: ('Окружни затвор', 'Краљево', 'Војводе Путника 3', 'Vojvode Putnika 3, Kraljevo'),
    23: ('Окружни затвор', 'Нови Пазар', 'Ослобођења 39а', None),
    24: ('Васпитно-поправни дом', 'Крушевац', 'Благоја Паровића бб', None),
    25: ('Окружни затвор', 'Крушевац', 'Немањина бб', None),
    26: ('Казнено-поправни завод', 'Ниш', 'Насеље Милке Протић бб', None),
    27: ('Окружни затвор', 'Прокупље', 'Таткова 6', 'Tatkova 6, Prokuplje'),
    28: ('Окружни затвор (2026: казнено-поправни завод)', 'Лесковац', 'Шестог септембра 2', None),
    29: ('Окружни затвор', 'Врање', 'Цара Душана 1', 'Cara Dušana 1, Vranje'),
}
# Places for addresses without a house number (bb), as Nominatim queries
PLACE = {3: 'Padinska Skela', 4: 'Padinska Skela', 7: 'Kazneno-popravni zavod Pančevo', 8: 'Kazneno-popravni zavod Sombor',
         10: 'Kazneno-popravni zavod Sremska Mitrovica', 11: 'Kazneno-popravni zavod Šabac', 12: 'Valjevo',
         14: 'Kazneno-popravni zavod za žene Požarevac', 15: 'Zabela, Požarevac', 16: 'Mlavska, Kragujevac',
         17: 'Danila Dimitrijevića, Ćuprija', 19: 'Izvorski put, Zaječar', 23: 'Oslobođenja, Novi Pazar',
         24: 'Blagoja Parovića, Kruševac', 25: 'Nemanjina, Kruševac', 26: 'Kazneno-popravni zavod Niš',
         28: 'Šestog septembra, Leskovac'}
CITY_LAT = {'Београд': 'Beograd', 'Суботица': 'Subotica', 'Зрењанин': 'Zrenjanin', 'Панчево': 'Pančevo', 'Сомбор': 'Sombor',
            'Нови Сад': 'Novi Sad', 'Сремска Митровица': 'Sremska Mitrovica', 'Шабац': 'Šabac', 'Ваљево': 'Valjevo',
            'Смедерево': 'Smederevo', 'Пожаревац': 'Požarevac', 'Крагујевац': 'Kragujevac', 'Ћуприја': 'Ćuprija',
            'Неготин': 'Negotin', 'Зајечар': 'Zaječar', 'Ужице': 'Užice', 'Чачак': 'Čačak', 'Краљево': 'Kraljevo',
            'Нови Пазар': 'Novi Pazar', 'Крушевац': 'Kruševac', 'Ниш': 'Niš', 'Прокупље': 'Prokuplje', 'Лесковац': 'Leskovac',
            'Врање': 'Vranje'}


def nominatim(q):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode({'q': q, 'countrycodes': 'rs', 'format': 'json', 'limit': 1})
    req = urllib.request.Request(url, headers={'User-Agent': 'analiza_izbora election map (research)'})
    res = json.loads(urllib.request.urlopen(req, timeout=30).read())
    time.sleep(1.1)
    return res[0] if res else None


rows = []
for no, (name, city, address, street) in PRISONS.items():
    hit, how = None, ''
    for q, kind in ((street, 'address'), (PLACE.get(no), 'place'), (CITY_LAT[city], 'city')):
        if q and not hit:
            hit = nominatim(q)
            how = kind
    rows.append([no, name, city, address, round(float(hit['lat']), 5), round(float(hit['lon']), 5), how, hit['display_name'][:90]])
    print(rows[-1], flush=True)
with open(OUT, 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f)
    w.writerow(['bm_broj', 'name', 'city', 'address', 'lat', 'lon', 'located_by', 'osm_match'])
    w.writerows(rows)
