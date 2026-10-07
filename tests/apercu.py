"""Rendu local du site avec de fausses données, pour vérifier l'affichage.
Usage : python3 tests/apercu.py dossier_sortie"""
import json, sys, pathlib
from playwright.sync_api import sync_playwright

racine = pathlib.Path(__file__).resolve().parent.parent
sortie = pathlib.Path(sys.argv[1]); sortie.mkdir(parents=True, exist_ok=True)
page_html = (racine / "site/index.html").read_text(encoding="utf-8")
floss = json.loads((racine / "data/exemple_floss.json").read_text(encoding="utf-8"))
job = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else json.loads((racine / "data/exemple_job.json").read_text(encoding="utf-8"))
store = {
  "config/main": {"floss_trigger": "trig_a", "job_trigger": "trig_b", "cibles": {"grenoble": [42, 45]}, "mots_interdits": ["motinterdit"]},
  "config/cv": {"asset_id": "abc", "nom": "CV.pdf", "envoye_le": "2026-10-08T08:00:00Z"},
  "floss/2026-10-08": floss, "jobs/job-1": job,
}
mock = """
<script>
(function(){
  const store = %s; const subs = [];
  const snapDoc = p => ({id:p.split('/').pop(), exists: p in store, data: () => store[p]});
  const notify = () => subs.forEach(f => f());
  const docRef = p => ({ id:p.split('/').pop(), path:p, get: async () => snapDoc(p),
    set: async d => { store[p] = d; notify(); }, update: async d => { store[p] = {...store[p], ...d}; notify(); },
    onSnapshot: (n) => { const f = () => n(snapDoc(p)); subs.push(f); setTimeout(f, 20); return () => {}; } });
  const q = (c, ord, lim) => ({ orderBy: (f,d) => q(c, [f,d||'asc'], lim), limit: n => q(c, ord, n), doc: id => docRef(c+'/'+id),
    onSnapshot: (n) => { const f = () => { let keys = Object.keys(store).filter(k => k.startsWith(c+'/') && k.split('/').length === c.split('/').length+1);
      if(ord) keys.sort((a,b) => String(store[a][ord[0]]||'').localeCompare(String(store[b][ord[0]]||'')) * (ord[1]==='desc'?-1:1));
      if(lim) keys = keys.slice(0, lim); n({docs: keys.map(snapDoc)}); }; subs.push(f); setTimeout(f, 20); return () => {}; } });
  const caps = { db: { doc: docRef, collection: c => q(c) },
    mcp: { callTool: async (s,t,i) => { window.__fired = (window.__fired||[]).concat([[s,t,i]]); return {payload:{}}; } },
    assets: { upload: async f => ({id:'f'.repeat(32), url:'/_blob/x', sizeBytes:f.size, contentType:'application/pdf'}) },
    downloads: { save: async () => ({status:'saved'}) } };
  window.__store = store;
  window.claude = { use: async n => (window.__absent ? null : caps[n] || null) };
})();
</script>
""" % json.dumps(store, ensure_ascii=False)
squelette = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style></head><body>' + mock + page_html + "</body></html>"
fichier = sortie / "apercu.html"; fichier.write_text(squelette, encoding="utf-8")

with sync_playwright() as p:
    b = p.chromium.launch()
    erreurs = []
    for nom, larg in (("bureau", 1180), ("mobile", 400)):
        ctx = b.new_context(viewport={"width": larg, "height": 900}, device_scale_factor=1, color_scheme="dark")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        pg.on("console", lambda m: erreurs.append(m.text) if m.type == "error" and "fonts.g" not in m.text and "ERR_" not in m.text else None)
        pg.goto(fichier.as_uri()); pg.wait_for_timeout(700)
        debord = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        print(nom, "débordement horizontal :", debord)
        pg.screenshot(path=str(sortie / f"floss-{nom}.png"), full_page=True)
        for m in (60, 250, 600, 1500):
            print(nom, m, "→", pg.evaluate("""(m)=>{const o=calcOrdre(S.floss[0],m);return JSON.stringify({l:o.lignes.map(x=>[x.cle,x.n,+x.montant.toFixed(2),x.frais]),inv:+o.investi.toFixed(2),f:o.frais,r:+o.reste.toFixed(2),e:o.ecartes.length})}""", m))
        pg.click("#tab-job"); pg.wait_for_timeout(300)
        print(nom, "emploi débordement :", pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
        pg.screenshot(path=str(sortie / f"job-{nom}.png"), full_page=True)
        pg.click("#tab-guide"); pg.wait_for_timeout(200)
        pg.screenshot(path=str(sortie / f"guide-{nom}.png"), full_page=True)
        if nom == "bureau":
            pg.click("#tab-job"); pg.fill("#ville", "Lyon"); pg.wait_for_timeout(500); pg.click("#job-go"); pg.wait_for_timeout(400)
            print("déclenché :", pg.evaluate("JSON.stringify(window.__fired)"), "| demande :", pg.evaluate("JSON.stringify(Object.entries(window.__store).filter(([k])=>k.startsWith('demandes/')).map(([k,v])=>v))"))
            pg.screenshot(path=str(sortie / "job-en-cours.png"), full_page=False)
        ctx.close()
    print("erreurs :", erreurs or "aucune")
    b.close()
