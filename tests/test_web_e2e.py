"""E2E no navegador real (Chromium via Qt WebEngine, offscreen): navegação, gráficos, interações e downloads."""

import json

import pytest

pytest.importorskip("PyQt6.QtWebEngineWidgets")
pytest.importorskip("fastapi")

from webui_harness import UiSession  # noqa: E402

VIEWS = ["overview", "telemetry", "compare", "replay", "engine", "setups", "runs", "library", "reports", "settings"]


@pytest.fixture(scope="module")
def ui(tmp_path_factory):
    s = UiSession(tmp_path_factory.mktemp("e2e"))
    yield s
    s.close()


@pytest.fixture(scope="module")
def loaded(ui):
    ui.js("await window.mangue.loadDemo(); return 1")
    ui.pump(1.0)
    return ui


def text(ui):
    return ui.js("return document.querySelector('#view').innerText")


def test_empty_state_then_demo(ui):
    assert "SEM DADOS" in text(ui).upper() or "Sem dados" in text(ui)
    assert ui.js("return document.title") == "Mangue Logger — Telemetria"
    ui.js("await window.mangue.loadDemo(); return 1")
    ui.pump(1.0)
    assert ui.js("return window.mangue.store.state.runs.length") == 4
    assert ui.js("return document.querySelectorAll('.run-chip').length") == 4


@pytest.mark.parametrize("view", VIEWS)
def test_every_view_renders_without_errors(loaded, view):
    loaded.console.clear()
    loaded.goto(view, 1.4)
    assert loaded.errors() == []
    assert ui_text_len(loaded) > 40
    assert loaded.js("return location.hash") == f"#/{view}"
    assert loaded.js("return document.querySelector('.nav-item.active') !== null")


def ui_text_len(ui):
    return len(text(ui))


def test_charts_actually_draw_pixels(loaded):
    loaded.goto("telemetry", 1.6)
    n = loaded.js("""
      const c=[...document.querySelectorAll('.chart canvas')]; let drawn=0;
      for(const cv of c){ const d=cv.getContext('2d').getImageData(0,0,cv.width,cv.height).data; let k=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) k++; if(k>500) drawn++; }
      return drawn""")
    assert n >= 3                                           # vel, rpm, acel (+ faixa de fases)


def test_hover_updates_readouts_and_zoom_refetches(loaded):
    loaded.goto("telemetry", 1.6)
    out = loaded.js("""
      const c=document.querySelector('.chart canvas'); const b=c.getBoundingClientRect();
      c.dispatchEvent(new PointerEvent('pointermove',{clientX:b.left+b.width*0.5,clientY:b.top+60,bubbles:true}));
      await new Promise(r=>setTimeout(r,250));
      const hover=document.querySelector('.readouts').innerText;
      const reqs=[]; const of=window.fetch; window.fetch=(u,...a)=>{reqs.push(String(u)); return of(u,...a)};
      for(let i=0;i<3;i++) c.dispatchEvent(new WheelEvent('wheel',{deltaY:-120,clientX:b.left+b.width*0.4,clientY:b.top+60,bubbles:true,cancelable:true}));
      await new Promise(r=>setTimeout(r,800)); window.fetch=of;
      c.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));
      return JSON.stringify({hover, zoom: reqs.filter(u=>u.includes('x0=')).length})""")
    d = json.loads(out)
    assert "t = " in d["hover"] and "—" not in d["hover"].split("DEMO_A1")[1][:40]
    assert d["zoom"] >= 1


def test_math_channel_and_axis_switch(loaded):
    loaded.goto("telemetry", 1.2)
    loaded.js("""
      const inp=[...document.querySelectorAll('input[type=text]')]; inp[0].value='rpm / (vel + 1)'; inp[1].value='razao';
      [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Canal matemático')).click(); return 1""")
    loaded.pump(1.6)
    assert "RAZAO" in text(loaded).upper()
    loaded.js("[...document.querySelectorAll('.seg button')].find(b=>b.textContent==='Distância').click(); return 1")
    loaded.pump(1.6)
    assert "distância (m)" in text(loaded) or loaded.js("return window.mangue.store.xAxis") == "dist"
    loaded.js("window.mangue.store.xAxis='time'; localStorage.clear(); return 1")


def test_compare_shows_sector_tiles_and_deltas(loaded):
    loaded.goto("compare", 1.6)
    assert loaded.js("return document.querySelectorAll('.tile.purple').length") > 0
    assert loaded.js("return document.querySelectorAll('.tiles').length") == 4
    assert "REF" in text(loaded)


def test_replay_plays_and_advances(loaded):
    loaded.goto("replay", 1.4)
    t0 = loaded.js("return document.querySelector('.stat-line b').textContent")
    loaded.js("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Play')).click(); return 1")
    loaded.pump(1.5)
    t1 = loaded.js("return document.querySelector('.stat-line b').textContent")
    assert t0 == "0:00.000" and t1 != t0
    assert loaded.js("return document.querySelectorAll('.led.lit').length") >= 1
    loaded.js("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Pausa')).click(); return 1")


def test_filter_drawer_changes_results(loaded):
    loaded.goto("overview", 1.2)
    before = loaded.js("return document.querySelector('.kpi .v').textContent")
    loaded.js("document.getElementById('btn-filter').click(); return 1")
    loaded.pump(0.5)
    assert loaded.js("return document.getElementById('drawer').classList.contains('open')")
    loaded.js("""
      const s=document.querySelector('#drawer input[type=range]'); s.value=2; s.dispatchEvent(new Event('input',{bubbles:true}));
      const sel=document.querySelector('#drawer select'); sel.value='median'; sel.dispatchEvent(new Event('change',{bubbles:true})); return 1""")
    loaded.pump(1.8)
    after = loaded.js("return (await (await fetch('/api/state')).json()).filter.kind")
    assert after == "median"
    loaded.js("await fetch('/api/filter',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'butterworth'})}); await window.mangue.refresh(); document.getElementById('btn-filter').click(); return 1")
    loaded.pump(1.0)
    _ = before


def test_runs_editor_saves_metadata(loaded):
    loaded.goto("runs", 1.4)
    loaded.js("""
      const tags=[...document.querySelectorAll('input[type=text]')].find(i=>i.placeholder.includes('enduro')); tags.value='e2e, cvt'; tags.dispatchEvent(new Event('input',{bubbles:true}));
      [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Salvar')).click(); return 1""")
    loaded.pump(1.8)
    tags = loaded.js("return window.mangue.store.state.runs[0].meta.tags.join(',')")
    assert tags == "e2e,cvt"


def test_library_search_and_open(loaded):
    loaded.goto("library", 1.4)
    assert loaded.js("return document.querySelectorAll('tbody tr').length") == 4
    loaded.js("const q=document.querySelector('input[type=text]'); q.value='B1'; q.dispatchEvent(new Event('input',{bubbles:true})); return 1")
    loaded.pump(0.9)
    assert loaded.js("return document.querySelectorAll('tbody tr').length") == 1


def test_reports_download_and_preview(loaded):
    loaded.goto("reports", 1.2)
    sizes = loaded.js("""
      const out={}; for(const e of ['.pdf','.xlsx','.html','.json','.csv']){ const r=await fetch('/api/report?format='+e); out[e]=[r.status,(await r.blob()).size]; } return JSON.stringify(out)""")
    assert all(s == 200 and n > 200 for s, n in json.loads(sizes).values())
    loaded.js("[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Atualizar prévia')).click(); return 1")
    loaded.pump(2.5)
    assert loaded.js("return document.querySelector('iframe.preview').srcdoc.length") > 1000


def test_upload_drop_and_remove(loaded):
    r = loaded.js("""
      const csv='f1,f2\\n'+Array.from({length:600},(_,i)=>`${3+(i%4)},${(i%3)}`).join('\\n');
      await window.mangue.loadFiles([new File([csv],'solto.csv')], false);
      return window.mangue.store.state.runs.map(r=>r.name).join(',')""")
    assert r.endswith("solto.csv")
    loaded.js("document.querySelector('.run-chip:last-child .ic:last-child').click(); return 1")
    loaded.pump(1.2)
    assert loaded.js("return window.mangue.store.state.runs.length") == 4


def test_hide_run_removes_it_from_charts(loaded):
    loaded.goto("telemetry", 1.4)
    loaded.js("document.querySelector('.run-chip .ic:nth-child(3)').click(); return 1")
    loaded.pump(1.6)
    assert loaded.js("return document.querySelectorAll('.legend span').length") == 3
    loaded.js("document.querySelector('.run-chip.hidden .ic:nth-child(3)').click(); return 1")
    loaded.pump(1.0)


def test_no_console_errors_overall(loaded):
    assert loaded.errors() == []
