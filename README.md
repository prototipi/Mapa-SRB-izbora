# Mapa izbora u Srbiji 2023–2026

Interactive map of the parliamentary election results in Serbia, 2023 and 2026: by municipality, district and region, in prisons, and abroad, with the change between the two elections.

**Map:** https://prototipi.github.io/Mapa-SRB-izbora/ · [Srpski (latinica)](https://prototipi.github.io/Mapa-SRB-izbora/mapa_izbora_sr-latn.html) · [Српски (ћирилица)](https://prototipi.github.io/Mapa-SRB-izbora/mapa_izbora_sr-cyrl.html) · [English](https://prototipi.github.io/Mapa-SRB-izbora/mapa_izbora.html)

## Files

| File | Content |
|---|---|
| `mapa_izbora_sr-latn.html`, `mapa_izbora_sr-cyrl.html`, `mapa_izbora.html` | The map pages. Each page is standalone and works offline. |
| `14_30_09_29.10.2026.xlsx`, `liste.ods` | 2026 results by polling station, and the electoral lists (RIK) |
| `rezultati_2023.xlsx`, `rezultati_2023.csv`, `rezultati_2023_liste.csv` | 2023 results by polling station, and the national list totals, collected from the RIK results page |
| `geo/` | Locations of the polling stations abroad and in prisons, and the country outlines |
| `build_map.py`, `map_template.html`, `i18n_sr-latn.json` | The build: data, page template and Serbian translations |
| `scrape_rik.py`, `tools/` | The 2023 scraper, data preparation and page tests |
| `DECISIONS.md` | All decisions and sources |

## Build

Python 3, standard library only:

```
python tools/fetch_gadm.py
python build_map.py
```

`fetch_gadm.py` downloads the GADM boundaries, which are not in the repository (see below).

## Test

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python tools\check_page.py
.venv\Scripts\python tools\check_languages.py
```

## Sources

- **Results:** Republic Electoral Commission (RIK), https://www.rik.parlament.gov.rs/
- **Municipality boundaries:** [GADM 4.1](https://gadm.org/). Non-commercial use only. The license does not allow redistribution, so the GADM files are not in this repository.
- **Country outlines:** [Natural Earth](https://www.naturalearthdata.com/), public domain
- **Locations abroad and of prisons:** [Nominatim](https://nominatim.openstreetmap.org/), data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL)
- **Map library:** [D3](https://d3js.org/) 7.8.5 (ISC license), in `vendor/`

[DECISIONS.md](DECISIONS.md) gives every source and decision in detail.
