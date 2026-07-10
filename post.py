#!/usr/bin/env python3
"""
post.py — günlük paylaşım zinciri (Instagram Login / graph.instagram.com).

Akış:
  1) Bankadan sıradaki ONAYLI alıntıyı seç (kaynak_dogrulandi == true)
  2) Kartı render et (rotasyon teması + otomatik font)
  3) PNG'yi repoya commit+push et  -> public raw URL (Instagram bunu çekecek)
  4) Container oluştur -> yayınla (media_publish)
  5) State'i ilerlet (pointer + posted), commit+push

Ortam değişkenleri (GitHub Actions secrets):
  IG_USER_ID, IG_TOKEN            (zorunlu)
  GITHUB_REPOSITORY, GITHUB_REF_NAME  (Actions otomatik verir)

Yerel test:
  python post.py --dry-run        # her şeyi yapar ama git push + yayın YOK
"""
import argparse, json, os, subprocess, sys, time, datetime as dt
from pathlib import Path
import requests
from render import build_html, build_card, render, theme_for   # render.py'den

ROOT = Path(__file__).parent
STATE = ROOT / "state" / "state.json"
PUBDIR = ROOT / "published"
GRAPH = "https://graph.instagram.com"
VERSION = "v22.0"        # graph.instagram.com yayın uçları; sorun olursa VERSION="" yap

# ---------- yardımcılar ------------------------------------------------------
def sh(*args, check=True):
    return subprocess.run(args, cwd=ROOT, check=check,
                          capture_output=True, text=True)

def load_bank():
    return json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"pointer": 0, "posted": []}

def save_state(s):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

def approved(bank):
    """Sadece yayına hazır girişler: kaynağı doğrulanmış + metni dolu."""
    return [g for g in bank["girisler"]
            if g.get("kaynak_dogrulandi") is True and g.get("metin_tr", "").strip()]

def pick(bank, state):
    items = approved(bank)
    if not items:
        return None, None
    posted_ids = {p.get("id") for p in state.get("posted", [])}
    fresh = [g for g in items if g["id"] not in posted_ids]
    pool = fresh if fresh else items          # hepsi paylaşıldıysa baştan döner
    idx = state["pointer"] % len(pool)
    return pool[idx], idx

def build_caption(entry, bank):
    if entry.get("bolum"):
        kisa = entry.get("bolum_kisa", "").strip()
        arama = f'"Muhteşem 13. Yüzyıl {kisa}"' if kisa else '"Muhteşem 13. Yüzyıl"'
        parts = [entry["metin_tr"], "",
                 "🎧 Bu konuyu podcast bölümümüzde konuştuk.",
                 f"Spotify, Apple Podcasts ya da YouTube'da {arama} diye arat, karşına çıkarız.",
                 "", "🔗 Tüm bölümler profildeki linkte."]
        return "\n".join(parts)
    if entry.get("tip") == "bilgi":
        parts = [entry["metin_tr"]]
        src = entry.get("kaynak_tanim") or entry.get("kaynak")
        if src:
            parts += ["", f"Kaynak: {src}"]
        parts += ["", "Bizi Spotify'da takip etmeyi unutmayın 🧡",
                  "", "🔗 Tüm bölümler için bağlantı profilde."]
        return "\n".join(parts)
    attr = entry["sahis"]
    if entry.get("eser"):     attr += f" · {entry['eser']}"
    if entry.get("mutercim"): attr += f" · çev. {entry['mutercim']}"
    parts = [
        f"\u201c{entry['metin_tr']}\u201d",
        attr,
        "",
        "Bizi Spotify'da takip etmeyi unutmayın 🧡",
        "",
        "🔗 Tüm bölümler için bağlantı profilde.",
    ]
    return "\n".join(parts)

def raw_url(path_rel):
    repo = os.environ["GITHUB_REPOSITORY"]              # owner/repo
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path_rel}"

def wait_until_live(url, tries=20, delay=3):
    for _ in range(tries):
        if requests.head(url, timeout=15).status_code == 200:
            return True
        time.sleep(delay)
    return False

# ---------- Instagram --------------------------------------------------------
def ig_publish(user_id, token, image_url, caption):
    base = f"{GRAPH}/{VERSION}/{user_id}" if VERSION else f"{GRAPH}/{user_id}"
    # 1) container
    r = requests.post(f"{base}/media",
                      data={"image_url": image_url, "caption": caption,
                            "access_token": token}, timeout=60)
    r.raise_for_status()
    cid = r.json()["id"]
    # 2) hazır olana kadar bekle (görsellerde genelde anında)
    for _ in range(15):
        s = requests.get(f"{GRAPH}/{VERSION}/{cid}" if VERSION else f"{GRAPH}/{cid}",
                         params={"fields": "status_code", "access_token": token},
                         timeout=30).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Container hata: {s}")
        time.sleep(3)
    # 3) yayınla
    r = requests.post(f"{base}/media_publish",
                      data={"creation_id": cid, "access_token": token}, timeout=60)
    r.raise_for_status()
    return r.json().get("id")

# ---------- ana akış ---------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="render + caption üret, git/yayın YOK")
    ap.add_argument("--id", help="belirli bir alıntıyı yayınla (boşsa sıradaki)")
    a = ap.parse_args()

    bank = load_bank()
    state = load_state()

    if a.id:
        entry = next((g for g in approved(bank) if g["id"] == a.id), None)
        if not entry:
            if a.dry_run:
                entry = (approved(bank) or bank["girisler"])[0]
            else:
                sys.exit(f"'{a.id}' onaylı girişlerde bulunamadı (kaynak_dogrulandi=true mu?).")
    elif a.dry_run:
        entry = (approved(bank) or bank["girisler"])[0]
    else:
        entry, _ = pick(bank, state)
        if not entry:
            print("Onaylı alıntı yok (kaynak_dogrulandi=true olan giriş gerekiyor). "
                  "Paylaşacak bir şey olmadan çıkılıyor."); return

    theme = theme_for(entry, state["pointer"])
    PUBDIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    img_rel = f"published/{today}_{entry['id']}.png"
    img_path = ROOT / img_rel
    render(build_card(entry, theme), img_path)
    caption = build_caption(entry, bank)
    print(f"Seçilen: {entry['id']} | tema-arkaplan: {theme}\n--- CAPTION ---\n{caption}\n---")

    if a.dry_run:
        print(f"[dry-run] kart: {img_path} — yayın yapılmadı."); return

    # görseli repoya koy (public raw URL için)
    sh("git", "add", img_rel)
    sh("git", "commit", "-m", f"kart: {entry['id']} {today}")
    sh("git", "push")
    url = raw_url(img_rel)
    if not wait_until_live(url):
        sys.exit(f"Görsel public URL'de görünmedi: {url}")

    media_id = ig_publish(os.environ["IG_USER_ID"], os.environ["IG_TOKEN"], url, caption)
    print(f"YAYINLANDI ✓ media_id={media_id}")

    # state güncelle
    if not a.id:
        state["pointer"] = state["pointer"] + 1     # rotasyon sadece sıradaki yayında ilerler
    state.setdefault("posted", []).append(
        {"id": entry["id"], "date": today, "media_id": media_id})
    save_state(state)
    sh("git", "add", "state/state.json")
    sh("git", "commit", "-m", f"state: {entry['id']} yayınlandı")
    sh("git", "push")

if __name__ == "__main__":
    main()
