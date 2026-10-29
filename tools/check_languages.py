"""Test the Serbian versions (mapa_izbora_sr-latn.html, mapa_izbora_sr-cyrl.html) in headless Chromium.

For each page: no script errors, every year, category and view draws, and the visible text has no English words left.
The Cyrillic page must not show Serbian Latin text (except acronyms like PDF and RG numbers in data).
Run:  .venv\\Scripts\\python tools\\check_languages.py [--out test_output]
"""
import argparse, pathlib, re, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGES = {'sr-Latn': ROOT / 'mapa_izbora_sr-latn.html', 'sr-Cyrl': ROOT / 'mapa_izbora_sr-cyrl.html'}
# English words that must not appear in the Serbian interface
ENGLISH = re.compile(r'\b(Turnout|Winner|Voters|voters|Lead|Change|Other parties|Other lists|polling station|Polling station|'
                     r'Municipalit|District|Region map|Abroad|Prisons|Show all|No results|Registered|Valid votes|share|points|'
                     r'Whole country|All countries|Find municipality|threshold|Leading list|Challenger)\b')
failures = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        failures.append(what)


def visible_text(page):
    return page.evaluate("""() => [
      document.querySelector('header h1').innerText + ' ' + document.querySelector('header .controls').innerText,  // not the language menu
      (document.querySelector('.abroad:not([hidden]) .legend') || document.getElementById('legend')).innerText,
      document.getElementById('panel').innerText,
      [...document.querySelectorAll('#map text.lbl, #map text.rname')].map(t => t.textContent).join(' '),
      [...document.querySelectorAll('.abroad:not([hidden]) .card')].map(c => c.innerText).join(' ')].join('\\n')""")


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for lang, path in PAGES.items():
            print(f'\n== {lang}: {path.name}')
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(path.as_uri())
            page.wait_for_selector('#map path.unit')
            page.wait_for_timeout(400)
            check(not errors, 'page starts without script errors' + ('' if not errors else ': ' + errors[0]))
            if errors:
                continue
            title = page.title()
            h1 = page.inner_text('h1')
            check(('Izbori' in title and 'Srbija' in h1) if lang == 'sr-Latn' else ('Избори' in title and 'Србија' in h1), f'title and heading: {title} | {h1}')
            check(page.evaluate('document.documentElement.lang') == lang, f'<html lang> is {lang}')
            opts = page.eval_on_selector_all('#lang option', 'os => os.map(o => [o.value, o.textContent, o.selected])')
            order = [o[1] for o in opts]
            check(order == ['Srpski (latinica)', 'Српски (ћирилица)', 'English'] and all((ROOT / o[0]).exists() for o in opts)
                  and [o for o in opts if o[2]][0][0] == path.name, f'language menu: {order}, current page selected')
            english, latin = set(), set()
            n_views = 0
            for view in ('2023', '2026', 'change'):
                page.click(f'#y-{view}'); page.wait_for_timeout(150)
                for cat in ('serbia', 'region', 'abroad'):
                    page.click(f'#cat-{cat}'); page.wait_for_timeout(200)
                    for m in page.eval_on_selector_all('#modes button', 'bs => bs.map(b => b.id)'):
                        page.click(f'#{m}'); page.wait_for_timeout(180)
                        n_views += 1
                        text = visible_text(page)
                        english |= set(ENGLISH.findall(text))
                        if lang == 'sr-Cyrl':
                            # Latin words of 3+ letters, apart from acronyms in capitals and PDF links
                            latin |= {w for w in re.findall(r'\b[A-Za-zČĆŽŠĐčćžšđ]{3,}\b', text) if not w.isupper()}
                        if m in ('m-winner', 'm-flip', 'm-turnout') and cat != 'region':
                            page.screenshot(path=str(out / f'{lang}_{view}_{cat}_{m[2:]}.png'))
                page.click('#cat-serbia'); page.wait_for_timeout(150)
            check(n_views >= 30, f'{n_views} views drawn')
            check(not english, 'no English words in the interface' + ('' if not english else ': ' + ', '.join(sorted(english))))
            if lang == 'sr-Cyrl':
                check(not latin, 'no Latin text in the Cyrillic page' + ('' if not latin else ': ' + ', '.join(sorted(latin)[:25])))
            # Sources dialog: translated; in the Cyrillic page only the source and product names are Latin
            page.click('#srcBtn'); page.wait_for_timeout(200)
            src = page.inner_text('#sources')
            english_src = set(ENGLISH.findall(src)) | set(re.findall(r'\b(Sources|Results|Boundaries|Ministry|Collected|Drawn|contributors)\b', src))
            check(not english_src, 'Sources dialog in Serbian' + ('' if not english_src else ': ' + ', '.join(sorted(english_src))))
            if lang == 'sr-Cyrl':
                names = {'GADM', 'Natural', 'Earth', 'dijaspora', 'glasanje', 'vercel', 'app', 'Nominatim', 'OpenStreetMap', 'DECISIONS', 'GitHub'}
                latin_src = {w for w in re.findall(r'\b[A-Za-zČĆŽŠĐčćžšđ]{3,}\b', src) if w not in names and not w.isupper()}
                check(not latin_src, 'no Latin text in the Cyrillic Sources dialog' + ('' if not latin_src else ': ' + ', '.join(sorted(latin_src))))
            page.screenshot(path=str(out / f'{lang}_sources.png'))
            page.keyboard.press('Escape')
            # Panel with a municipality and its station table
            page.click('#y-2026'); page.click('#m-winner')
            box = page.locator('#map').bounding_box()
            page.mouse.click(box['x'] + box['width'] * .45, box['y'] + box['height'] * .45); page.wait_for_timeout(300)
            panel = page.inner_text('#panel')
            english_panel = set(ENGLISH.findall(panel))
            check(not english_panel, 'municipality panel and station table in Serbian' + ('' if not english_panel else ': ' + ', '.join(sorted(english_panel))))
            page.screenshot(path=str(out / f'{lang}_selected_municipality.png'))
            check(not errors, 'no script errors while switching views' + ('' if not errors else ': ' + errors[0]))
            page.close()
        browser.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'test_output'))
    run(pathlib.Path(ap.parse_args().out))
    print(f'\n{len(failures)} failed check(s)' if failures else '\nAll checks passed')
    sys.exit(1 if failures else 0)
