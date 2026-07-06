#!/usr/bin/env python3
"""render.py — alıntı bankası girişi -> Instagram kartı (1080x1350 PNG).
Arka plan rotasyonu + mobil için otomatik font + gömülü logo."""
import argparse, base64, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
TEMPLATE = (ROOT/"templates"/"card.html").read_text(encoding="utf-8")
LOGO_GOLD = ROOT/"assets"/"logo"/"logo_gold.png"
LOGO_DARK = ROOT/"assets"/"logo"/"logo_dark.png"

THEMES = {
    "gece": {"bg":"radial-gradient(120% 90% at 50% 12%, #232F45 0%, #1B2436 60%)",
        "ink":"#ECE3D0","accent":"#C9A24B","muted":"#8791A6","girih":"#C9A24B","girih_op":.05,
        "frame":"rgba(201,162,75,.28)","frame_inner":"rgba(236,227,208,.06)","logo":"gold","logo_filter":"none"},
    "kahve": {"bg":"radial-gradient(120% 90% at 50% 14%, #33241A 0%, #241A12 62%)",
        "ink":"#F0E6D2","accent":"#D9A24E","muted":"#A98F76","girih":"#D9A24E","girih_op":.055,
        "frame":"rgba(217,162,78,.30)","frame_inner":"rgba(240,230,210,.06)","logo":"gold","logo_filter":"none"},
    "koz": {"bg":"radial-gradient(115% 80% at 50% 20%, #6B3410 0%, #34190A 55%, #2A1408 75%)",
        "ink":"#F8EBD4","accent":"#E6912F","muted":"#C08E5E","girih":"#E6912F","girih_op":.05,
        "frame":"rgba(230,145,47,.30)","frame_inner":"rgba(248,235,212,.06)","logo":"gold","logo_filter":"none"},
    "is": {"bg":"radial-gradient(120% 90% at 50% 12%, #221B12 0%, #14110D 62%)",
        "ink":"#EFE7D6","accent":"#C9A24B","muted":"#8C8272","girih":"#C9A24B","girih_op":.06,
        "frame":"rgba(201,162,75,.26)","frame_inner":"rgba(239,231,214,.05)","logo":"gold","logo_filter":"none"},
    "parsomen": {"bg":"radial-gradient(120% 90% at 50% 12%, #F3ECDA 0%, #E8DEC6 65%)",
        "ink":"#2A1E16","accent":"#9B6B27","muted":"#7A6A54","girih":"#5A4326","girih_op":.06,
        "frame":"rgba(90,67,38,.30)","frame_inner":"rgba(42,30,22,.05)","logo":"gold","logo_filter":"none"},
}
ROTATION = ["gece","kahve","koz","is","parsomen"]
# Podcast/bölüm kartları için SABİT zeminler (rotasyona girmez, kendi aralarında döner)
THEMES["podcast"] = {"bg":"radial-gradient(120% 90% at 50% 12%, #16403F 0%, #0E2C2B 62%)",
    "ink":"#ECE3D0","accent":"#D9A24E","muted":"#8FA7A4","girih":"#D9A24E","girih_op":.05,
    "frame":"rgba(217,162,78,.30)","frame_inner":"rgba(236,227,208,.06)","logo":"gold","logo_filter":"none","solid":"#0E2C2B"}
THEMES["podcast-murdum"] = {"bg":"radial-gradient(120% 90% at 50% 12%, #3E2544 0%, #241528 62%)",
    "ink":"#ECE3D0","accent":"#D9A24E","muted":"#A38BA6","girih":"#D9A24E","girih_op":.05,
    "frame":"rgba(217,162,78,.30)","frame_inner":"rgba(236,227,208,.06)","logo":"gold","logo_filter":"none","solid":"#241528"}
THEMES["podcast-bordo"] = {"bg":"radial-gradient(120% 90% at 50% 12%, #4C1F29 0%, #2A1016 62%)",
    "ink":"#ECE3D0","accent":"#D9A24E","muted":"#B58A8F","girih":"#D9A24E","girih_op":.05,
    "frame":"rgba(217,162,78,.30)","frame_inner":"rgba(236,227,208,.06)","logo":"gold","logo_filter":"none","solid":"#2A1016"}
PODCAST_THEMES = ["podcast","podcast-murdum","podcast-bordo"]

def podcast_theme(entry):
    ta = entry.get("tema_arkaplan") if entry else None
    if ta in PODCAST_THEMES:
        return ta
    key = entry.get("id","x") if entry else "x"
    return PODCAST_THEMES[sum(ord(c) for c in key) % len(PODCAST_THEMES)]

GIRIH = ("<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'>"
    "<g fill='none' stroke='STROKE' stroke-width='1.2'>"
    "<rect x='45' y='45' width='60' height='60'/>"
    "<rect x='45' y='45' width='60' height='60' transform='rotate(45 75 75)'/></g></svg>")

def data_uri(p,mime): return f"data:{mime};base64,"+base64.b64encode(p.read_bytes()).decode()
def girih_uri(c): return "data:image/svg+xml;base64,"+base64.b64encode(GIRIH.replace("STROKE",c).encode()).decode()

def quote_size(t):
    n=len(t)
    return 96 if n<=55 else 82 if n<=95 else 70 if n<=150 else 60 if n<=210 else 52

def theme_css(t):
    return (f"--bg:{t['bg']};--ink:{t['ink']};--accent:{t['accent']};--muted:{t['muted']};"
            f"--girih-op:{t['girih_op']};--frame:{t['frame']};--frame-inner:{t['frame_inner']};"
            f"--logo-filter:{t['logo_filter']};")

def build_html(*,tema,quote,author,work,theme_name):
    t=THEMES[theme_name]; logo=LOGO_DARK if t["logo"]=="dark" else LOGO_GOLD
    h=TEMPLATE.replace("/*THEME*/",theme_css(t)).replace("GIRIH_TILE",girih_uri(t["girih"]))
    h=h.replace("QUOTE_SIZE",str(quote_size(quote))).replace("LOGO_SRC",data_uri(logo,"image/png"))
    for k,v in {"TEMA":tema,"QUOTE":quote,"AUTHOR":author,"WORK":work}.items():
        h=h.replace("{{"+k+"}}",str(v))
    return h

FACT_TEMPLATE=(ROOT/"templates"/"card_fact.html").read_text(encoding="utf-8")

def build_html_fact(*,etiket,metin,theme_name):
    t=THEMES[theme_name]; logo=LOGO_DARK if t["logo"]=="dark" else LOGO_GOLD
    h=FACT_TEMPLATE.replace("/*THEME*/",theme_css(t)).replace("GIRIH_TILE",girih_uri(t["girih"]))
    # bilgi metni genelde daha uzun -> biraz daha küçük başlat (fit zaten ayarlar)
    h=h.replace("QUOTE_SIZE",str(min(quote_size(metin),72))).replace("LOGO_SRC",data_uri(logo,"image/png"))
    for k,v in {"ETIKET":etiket,"METIN":metin}.items():
        h=h.replace("{{"+k+"}}",str(v))
    return h

PODCAST_TEMPLATE=(ROOT/"templates"/"card_podcast.html").read_text(encoding="utf-8")

def build_html_podcast(*,metin,bolum,entry=None):
    t=THEMES[podcast_theme(entry)]; logo=LOGO_GOLD
    h=PODCAST_TEMPLATE.replace("/*THEME*/",theme_css(t)+f"--solid:{t['solid']};")
    h=h.replace("GIRIH_TILE",girih_uri(t["girih"]))
    h=h.replace("QUOTE_SIZE",str(min(quote_size(metin),70))).replace("LOGO_SRC",data_uri(logo,"image/png"))
    for k,v in {"METIN":metin,"BOLUM":bolum}.items():
        h=h.replace("{{"+k+"}}",str(v))
    return h

def build_card(entry, theme_name):
    """Girişin tipine göre kart üretir: bölüm(podcast) / bilgi / alıntı."""
    if entry.get("bolum"):
        return build_html_podcast(metin=entry["metin_tr"], bolum=entry["bolum"], entry=entry)
    if entry.get("tip")=="bilgi":
        return build_html_fact(etiket=entry.get("etiket",""), metin=entry["metin_tr"],
                               theme_name=theme_name)
    return build_html(tema=entry.get("tema",""), quote=entry["metin_tr"],
                      author=entry["sahis"], work=entry.get("eser",""), theme_name=theme_name)

FIT_JS = """() => {
  const stage=document.querySelector('.stage');
  const head=document.querySelector('.head');
  const foot=document.querySelector('.foot');
  const q=document.querySelector('.quote')||document.querySelector('.info');
  const cs=getComputedStyle(stage);
  const avail=stage.clientHeight
    - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)
    - head.offsetHeight - foot.offsetHeight - 70;   // nefes payı
  const MAX=100, MIN=40;
  let lo=MIN, hi=MAX, best=MIN;
  for(let i=0;i<14;i++){
    const mid=(lo+hi)/2;
    q.style.fontSize=mid+'px';
    const fits=q.scrollHeight<=avail && q.scrollWidth<=q.clientWidth+1;
    if(fits){best=mid; lo=mid;} else {hi=mid;}
  }
  q.style.fontSize=best+'px';
  const overflow = q.scrollHeight>avail+1;   // MIN'de bile sığmadıysa uyar
  return {best:Math.round(best), avail:Math.round(avail),
          qh:q.scrollHeight, overflow};
}"""

def render(html,out):
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--no-sandbox"])
        pg=b.new_page(viewport={"width":1080,"height":1350},device_scale_factor=2)
        pg.set_content(html,wait_until="networkidle"); pg.wait_for_timeout(150)
        info=pg.evaluate(FIT_JS)                       # <-- alıntıyı boşluğa sığdır
        if info.get("overflow"):
            print(f"  UYARI: alıntı MIN fontta bile taşıyor (çok uzun) -> {out}")
        pg.wait_for_timeout(30)
        pg.screenshot(path=str(out),clip={"x":0,"y":0,"width":1080,"height":1350}); b.close()
        return info

def theme_for(entry,idx):
    return entry["tema_arkaplan"] if entry.get("tema_arkaplan") in THEMES else ROTATION[idx%len(ROTATION)]

DEMO=dict(tema="VAHDET",quote="Aradığın göz, seni gören gözün ta kendisidir.",
          author="ÖRNEK KÜNYE",work="(yer tutucu — gerçek değil)")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--id"); ap.add_argument("--demo"); ap.add_argument("--text")
    ap.add_argument("--theme",default="gece",choices=list(THEMES))
    ap.add_argument("--contact",action="store_true"); ap.add_argument("-o","--out",default="card.png")
    a=ap.parse_args()
    if a.contact:
        from PIL import Image
        tiles=[]
        for name in ROTATION:
            p=Path(f"_t_{name}.png"); render(build_html(**DEMO,theme_name=name),p); tiles.append(p)
        thumbs=[Image.open(p).resize((432,540)) for p in tiles]
        sheet=Image.new("RGB",(432*5+20*6,540+40),(24,22,20))
        for i,th in enumerate(thumbs): sheet.paste(th,(20+i*(432+20),20))
        sheet.save(a.out); print("yazıldı:",a.out); return
    if a.demo:
        d=dict(DEMO); 
        if a.text: d["quote"]=a.text
        info=render(build_html(**d,theme_name=a.theme),Path(a.demo)); print("yazıldı:",a.demo,"| font:",info["best"],"px"); return
    bank=json.loads((ROOT/"quotes.json").read_text(encoding="utf-8"))
    idx,entry=next(((i,g) for i,g in enumerate(bank["girisler"]) if g["id"]==a.id),(0,None))
    if not entry: sys.exit("id bulunamadı")
    render(build_html(tema=entry["tema"],quote=entry["metin_tr"],author=entry["sahis"],
                      work=entry["eser"],theme_name=theme_for(entry,idx)),Path(a.out))
    print("yazıldı:",a.out)

if __name__=="__main__": main()
