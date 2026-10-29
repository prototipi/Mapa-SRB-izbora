"""Download the GADM 4.1 municipality boundaries (level 2) for Serbia and Kosovo into geo/.

The GADM license allows non-commercial use but not redistribution, so the files are not in the repository.
Run:  python tools/fetch_gadm.py
"""
import io, os, urllib.request, zipfile

GEO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'geo')
URL = 'https://geodata.ucdavis.edu/gadm/gadm4.1/json/{name}.json.zip'

for name in ('gadm41_SRB_2', 'gadm41_XKO_2'):
    out = os.path.join(GEO_DIR, name + '.json')
    if os.path.exists(out):
        print('exists ', out)
        continue
    req = urllib.request.Request(URL.format(name=name), headers={'User-Agent': 'analiza_izbora election map (research)'})
    with zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req, timeout=120).read())) as z:
        with open(out, 'wb') as f:
            f.write(z.read(name + '.json'))
    print('saved  ', out)
