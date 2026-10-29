"""Test mapa_izbora.html in headless Chromium: script errors, main views, interaction, phone width, dark mode.

Setup (once):  py -m venv .venv
               .venv\\Scripts\\python -m pip install -r requirements-dev.txt
               .venv\\Scripts\\python -m playwright install chromium
Run:           .venv\\Scripts\\python tools\\check_page.py [--out test_output] [--headed]
Screenshots go to the --out folder. The exit code is 1 when a check fails.
"""
import argparse, itertools, json, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = (ROOT / 'mapa_izbora.html').as_uri()

failures = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        failures.append(what)


def click(page, sel):
    page.click(sel)
    page.wait_for_timeout(250)


def state(page):
    """Counts that show whether the visible view is drawn."""
    return page.evaluate("""() => {
      const q = s => document.querySelectorAll(s);
      const fills = [...q('#map path.unit')].map(p => p.getAttribute('fill'));
      return {
        shapes: fills.length,
        colored: fills.filter(f => f && !f.startsWith('url')).length,
        legend: (document.querySelector('.abroad:not([hidden]) .legend') || document.getElementById('legend')).innerText.trim().length,
        panelTitle: (document.querySelector('#panel h2') || {}).innerText || '',
        labels: [...q('#map text.lbl')].filter(t => t.getAttribute('display') !== 'none').length,
        borders: (document.querySelector('#map path.gborder').getAttribute('d') || '').length,
        prisonDots: q('#map circle.prison').length,
        cards: q('.abroad:not([hidden]) .card').length,
        dots: q('.abroad:not([hidden]) circle.dot').length,
        abroadShown: !document.getElementById('abroad').hidden,
        regionLand: q('#map path.rland').length,
        regionColored: [...q('#map path.rland')].filter(p => !(p.getAttribute('fill') || '').startsWith('var(')).length,
        serbiaColors: new Set(fills).size,
        regionDots: q('#map circle.rdot').length,
        overflowX: document.documentElement.scrollWidth - window.innerWidth,
      };
    }""")


def saved_states():
    """Every combination the page can save, plus an empty and an incomplete one."""
    states = [{}, {'view': '2026', 'ymode': 'turnout'}, {'view': 'change', 'cmode': 'voters'}]  # incomplete or older
    for view, cat, level in itertools.product(['2023', '2026', 'change'], ['serbia', 'region', 'abroad'], ['municipality', 'district', 'region']):
        for mode in (['flip', 'swing', 'others', 'shareA', 'turnout'] if view == 'change' else ['winner', 'margin', 'others', 'share', 'turnout']):
            for tunit in (['abs', 'pct'] if mode == 'turnout' and view == 'change' else ['pct']):
                st = {'view': view, 'cat': cat, 'level': level, 'showNums': True, 'showPrisons': True, 'listK': {'2023': 6, '2026': 2}, 'tunit': tunit}
                st['cmode' if view == 'change' else 'ymode'] = mode
                states.append(st)
    return states


def run(out, headed):
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        for scheme in ('light', 'dark'):
            print(f'\n== Desktop, {scheme} theme')
            ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            page = ctx.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
            page.goto(PAGE)
            page.wait_for_selector('#map path.unit')
            page.wait_for_timeout(500)
            if errors:  # the page did not start; nothing else can be tested
                check(False, 'page starts without script errors: ' + ' | '.join(errors[:5]))
                return
            legend = page.inner_text('#legend')
            want = ['SNS (2023) → SNS (2026)', 'SPN (2023) → SNS (2026)', 'SNS (2023) → SL (2026)', 'SPN (2023) → SL (2026)']
            check(all(w in legend for w in want), 'Winner change legend uses SNS, SPN and SL' + ('' if all(w in legend for w in want) else ': ' + legend.replace('\n', ' | ')))
            check(state(page)['prisonDots'] == 0, 'prison dots are hidden by default')
            # Change → Turnout: one tab with a 123 | % switch
            click(page, '#m-turnout')
            check(page.is_visible('#u-abs') and page.is_visible('#u-pct'), 'Change → Turnout shows the 123 | % switch')
            click(page, '#u-abs')
            t_abs = page.inner_text('#legend').split(chr(10))[0]
            n_abs = state(page)['labels']
            click(page, '#u-pct')
            t_pct = page.inner_text('#legend').split(chr(10))[0]
            check('VOTERS' in t_abs.upper() and 'POINTS' in t_pct.upper() and n_abs > 0 and state(page)['labels'] > 0,
                  f'123 shows voters ({t_abs}), % shows turnout points ({t_pct}), with numbers on the map')
            click(page, '#m-flip')
            check(not page.is_visible('#u-abs'), 'the # | % buttons are only in Turnout tabs')
            # 2026 Turnout: # | % choose the numbers on the map, the eye shows or hides them
            click(page, '#y-2026'); click(page, '#m-turnout')
            check(page.is_visible('#u-abs') and page.is_visible('#u-pct') and page.is_visible('#znum'), '2026 Turnout shows #, % and the eye under the zoom buttons')
            click(page, '#u-pct')
            nums = page.eval_on_selector_all('#map text.lbl', 'ts => ts.filter(t => t.getAttribute("display") !== "none").map(t => t.textContent)')
            check(nums and all(t.endswith('%') for t in nums), f'% shows turnout per unit on the map ({len(nums)} numbers, e.g. {nums[:3]})')
            click(page, '#u-abs')
            nums = page.eval_on_selector_all('#map text.lbl', 'ts => ts.filter(t => t.getAttribute("display") !== "none").map(t => t.textContent)')
            check(nums and not any(t.endswith('%') for t in nums), f'# shows voters in thousands ({nums[:3]})')
            click(page, '#znum')
            check(state(page)['labels'] == 0, 'the eye hides the numbers')
            click(page, '#znum')
            check(state(page)['labels'] > 0, 'the eye shows the numbers again')
            page.screenshot(path=str(out / f'{scheme}_2026_turnout_numbers.png'))
            # Abroad, Change → Turnout: # | % above the country blocks
            click(page, '#y-change'); click(page, '#m-turnout'); click(page, '#cat-abroad')
            check(page.locator('.abroad .aunits button').count() == 2, 'Abroad Change → Turnout shows # and % above the blocks')
            page.locator('.abroad .aunits [data-unit="abs"]').click(); page.wait_for_timeout(250)
            check('VOTERS' in page.inner_text('.abroad .legend').upper(), 'Abroad # switches to voters')
            page.locator('.abroad .aunits [data-unit="pct"]').click(); page.wait_for_timeout(250)
            click(page, '#cat-serbia'); click(page, '#m-flip')
            # List names: SNS, SPN and SL instead of the long names
            click(page, '#y-2023'); click(page, '#m-winner')
            legend = page.inner_text('#legend')
            check('SNS' in legend and 'SPN' in legend and 'Aleksandar' not in legend and 'Serbia Against' not in legend,
                  'Winner legend uses SNS and SPN, without the long names')
            check(page.inner_text('#m-margin') == 'SNS vs SPN', f'2023 lead tab: {page.inner_text("#m-margin")}')
            click(page, '#y-2026')
            check(page.inner_text('#m-margin') == 'SNS vs SL', f'2026 lead tab: {page.inner_text("#m-margin")}')
            click(page, '#m-others')
            legend = page.inner_text('#legend')
            check('STRONGEST OTHER PARTY' in legend.upper() and 'SPS' in legend, 'Other parties legend lists the parties: ' + legend.replace(chr(10), ' | ')[:120])
            click(page, '#y-change')
            check('Prisons' in page.inner_text('#offmap') and 'Abroad' not in page.inner_text('#offmap'), 'map options show "Show: Prisons" only')
            click(page, '#showPrisons')

            for view in ('2023', '2026', 'change'):
                click(page, f'#y-{view}')
                click(page, '#cat-serbia')
                for level in ('municipality', 'district', 'region'):
                    click(page, f'#lv-{level}')
                    modes = page.eval_on_selector_all('#modes button', 'bs => bs.map(b => b.id)')
                    for m in modes:
                        click(page, f'#{m}')
                        s = state(page)
                        name = f'{scheme}_{view}_{level}_{m[2:]}'
                        check(s['colored'] > 0 and s['legend'] > 0, f'{name}: map colored ({s["colored"]}/{s["shapes"]}) and legend drawn')
                        check(level == 'municipality' or s['borders'] > 0, f'{name}: group borders drawn')
                        check(s['prisonDots'] > 0, f'{name}: prison dots drawn ({s["prisonDots"]})')
                        if level == 'municipality' or m in ('m-winner', 'm-flip', 'm-turnout', 'm-voters'):
                            page.screenshot(path=str(out / f'{name}.png'))
                click(page, '#lv-municipality'); click(page, '#cat-region')
                for m in page.eval_on_selector_all('#modes button', 'bs => bs.map(b => b.id)'):
                    click(page, f'#{m}')
                    s = state(page)
                    name = f'{scheme}_{view}_regionmap_{m[2:]}'
                    check(s['regionLand'] == 9 and s['regionDots'] == 0 and s['colored'] > 0,
                          f'{name}: Serbia colored, {s["regionLand"]} neighbouring countries, no polling station dots ({s["regionDots"]})')
                    check(s['serbiaColors'] == 1 and s['regionColored'] == 8 and s['prisonDots'] == 0 and s['labels'] == 0,
                          f'{name}: Serbia one color ({s["serbiaColors"]}), {s["regionColored"]} of 8 countries colored, no prison dots or labels')
                    if m in ('m-winner', 'm-flip', 'm-swing', 'm-margin'):
                        page.screenshot(path=str(out / f'{name}.png'))
                click(page, '#cat-serbia')
                click(page, '#cat-abroad')
                for m in page.eval_on_selector_all('#modes button', 'bs => bs.map(b => b.id)'):
                    click(page, f'#{m}')
                    s = state(page)
                    name = f'{scheme}_{view}_abroad_{m[2:]}'
                    check(s['abroadShown'] and s['cards'] > 0 and s['dots'] > 0, f'{name}: {s["cards"]} country blocks, {s["dots"]} dots')
                    page.screenshot(path=str(out / f'{name}.png'), full_page=False)
                    if m in ('m-winner', 'm-flip'):
                        # Zoom into the first block that has more than one polling station
                        click(page, '.abroad .card [data-zoom] >> nth=0')
                        z = page.evaluate("""() => ({ shown: !document.getElementById('azoom').hidden,
                          dots: document.querySelectorAll('#zsvg circle.dot').length, title: (document.querySelector('#azoom h3') || {}).innerText })""")
                        check(z['shown'] and z['dots'] > 1, f'{name}: zoom view of {z["title"]} with {z["dots"]} dots')
                        click(page, '#zzin'); click(page, '#zzin'); page.wait_for_timeout(400)
                        r = page.evaluate("() => +document.querySelector('#zsvg circle.dot').getAttribute('r')")
                        check(r < 4.6, f'{name}: zoom in keeps dots small on screen (r {r:.2f} in map units)')
                        page.screenshot(path=str(out / f'{name}_zoom.png'))
                        click(page, '#zback')
                        check(page.evaluate("() => document.getElementById('azoom').hidden"), f'{name}: back to all countries')
                click(page, '#cat-serbia')

            # Interaction: hover and click a municipality, a prison dot, and a country block
            click(page, '#y-2026'); click(page, '#lv-municipality'); click(page, '#m-winner')
            box = page.locator('#map').bounding_box()
            page.mouse.move(box['x'] + box['width'] * .45, box['y'] + box['height'] * .45)
            page.wait_for_timeout(200)
            check(page.is_visible('#tip'), 'hover on a municipality shows the tooltip')
            page.mouse.click(box['x'] + box['width'] * .45, box['y'] + box['height'] * .45)
            page.wait_for_timeout(300)
            title = state(page)['panelTitle']
            check(title not in ('', 'Serbia'), f'click on a municipality opens it in the panel ({title})')
            page.screenshot(path=str(out / f'{scheme}_selected_municipality.png'))
            if page.locator('#map circle.prison').count():
                page.locator('#map circle.prison').first.hover(force=True); page.wait_for_timeout(200)
                text = page.inner_text('#tip') if page.is_visible('#tip') else '(no tooltip)'
                check('Prison polling station' in text, 'hover on a prison dot shows the station: ' + text.splitlines()[0])
            else:
                check(False, 'hover on a prison dot shows the station (no prison dots)')
            click(page, '#lv-region')
            page.mouse.click(box['x'] + box['width'] * .5, box['y'] + box['height'] * .3)
            page.wait_for_timeout(300)
            check('Region' in state(page)['panelTitle'], f'click at region level opens a region ({state(page)["panelTitle"]})')
            page.screenshot(path=str(out / f'{scheme}_selected_region.png'))
            click(page, '#cat-abroad')
            page.click('.abroad .card >> nth=0'); page.wait_for_timeout(300)
            check(state(page)['panelTitle'] not in ('', 'Abroad'), f'click on a country block opens the country ({state(page)["panelTitle"]})')
            page.screenshot(path=str(out / f'{scheme}_selected_country.png'))
            # Region map: hover a neighbouring country and Serbia, click a neighbouring country
            click(page, '#cat-region'); click(page, '#y-2026'); click(page, '#m-winner')
            page.locator('#map path.rland >> nth=0').hover(force=True); page.wait_for_timeout(200)
            text = page.inner_text('#tip') if page.is_visible('#tip') else '(no tooltip)'
            check(text.startswith('Hungary'), 'Region: hover on a neighbouring country shows it: ' + text.splitlines()[0])
            box = page.locator('#map').bounding_box()
            page.mouse.move(box['x'] + box['width'] * .45, box['y'] + box['height'] * .5); page.wait_for_timeout(200)
            check('without abroad' in (page.inner_text('#tip') if page.is_visible('#tip') else ''), 'Region: Serbia is one unit (tooltip: Serbia without abroad)')
            page.locator('#map path.rland >> nth=0').click(force=True); page.wait_for_timeout(300)
            check(state(page)['panelTitle'] == 'Hungary', f'Region: click on a neighbouring country opens it ({state(page)["panelTitle"]})')
            page.screenshot(path=str(out / f'{scheme}_region_selected.png'))
            click(page, '#cat-serbia')
            click(page, '#showPrisons')
            check(state(page)['prisonDots'] == 0, 'unticking Prisons hides the prison dots')
            # Sources dialog: opens from the header, lists every source with links, closes with × and with Escape
            page.click('#srcBtn'); page.wait_for_timeout(200)
            src = page.evaluate("""() => { const d = document.getElementById('sources');
              return { open: d.open, rows: d.querySelectorAll('dt').length, text: d.innerText,
                       links: [...d.querySelectorAll('a')].filter(a => a.target === '_blank' && a.href.startsWith('https://')).length }; }""")
            need = ['29.10.2026 14:25', '9.01.2024 20:21', 'GADM 4.1', 'Natural Earth', 'Nominatim', 'OpenStreetMap', 'DECISIONS.md']
            check(src['open'] and src['rows'] == 9 and src['links'] >= 11 and all(n in src['text'] for n in need),
                  f'Sources dialog: {src["rows"]} rows, {src["links"]} links' + ''.join(f', missing "{n}"' for n in need if n not in src['text']))
            page.screenshot(path=str(out / f'{scheme}_sources.png'))
            page.click('#srcClose'); page.wait_for_timeout(100)
            closed_x = not page.evaluate("document.getElementById('sources').open")
            page.click('#srcBtn'); page.keyboard.press('Escape'); page.wait_for_timeout(100)
            check(closed_x and not page.evaluate("document.getElementById('sources').open"), 'Sources dialog closes with × and with Escape')

            check(not errors, 'no script errors' + ('' if not errors else ': ' + ' | '.join(errors[:5])))
            ctx.close()

        # The page restores the last view from localStorage, so it must start from every saved state.
        print('\n== Start from every saved view')
        bad = []
        for st in saved_states():
            ctx = browser.new_context(viewport={'width': 1200, 'height': 800})
            ctx.add_init_script(f"localStorage.setItem('izbori-map-v2', {json.dumps(json.dumps(st))});")
            page = ctx.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(PAGE)
            page.wait_for_selector('#map path.unit')
            page.wait_for_timeout(300)
            drawn = page.evaluate("() => document.querySelectorAll('#map path.unit[fill]').length + document.querySelectorAll('.card').length")
            if errors or not drawn:
                bad.append(f'{st} → {errors[:1] or "nothing drawn"}')
            ctx.close()
        check(not bad, f'page starts from all {len(saved_states())} saved views' + ('' if not bad else f'; {len(bad)} fail, first: {bad[0]}'))

        print('\n== Phone width (400 px)')
        ctx = browser.new_context(viewport={'width': 400, 'height': 820}, device_scale_factor=2)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(PAGE)
        page.wait_for_selector('#map path.unit')
        page.wait_for_timeout(500)
        s = state(page)
        check(s['overflowX'] <= 0, f'no sideways scrolling (overflow {s["overflowX"]} px)')
        page.screenshot(path=str(out / 'phone_top.png'))
        page.screenshot(path=str(out / 'phone_full.png'), full_page=True)
        click(page, '#cat-abroad')
        check(state(page)['overflowX'] <= 0, 'no sideways scrolling in the Abroad view')
        page.screenshot(path=str(out / 'phone_abroad.png'))
        page.click('#srcBtn'); page.wait_for_timeout(200)
        r = page.evaluate("(() => { const b = document.getElementById('sources').getBoundingClientRect(); return [b.left, b.right, innerWidth]; })()")
        check(r[0] >= 0 and r[1] <= r[2], f'Sources dialog fits the phone width ({r[0]:.0f}–{r[1]:.0f} of {r[2]} px)')
        page.screenshot(path=str(out / 'phone_sources.png'))
        page.keyboard.press('Escape')
        check(not errors, 'no script errors on the phone' + ('' if not errors else ': ' + ' | '.join(errors[:5])))
        ctx.close()
        browser.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'test_output'))
    ap.add_argument('--headed', action='store_true')
    a = ap.parse_args()
    run(pathlib.Path(a.out), a.headed)
    print(f'\n{len(failures)} failed check(s)' if failures else '\nAll checks passed')
    sys.exit(1 if failures else 0)
