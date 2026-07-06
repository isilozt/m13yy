#!/usr/bin/env python3
"""
bot.py — ONAYLI yayın akışı (tek onay). Hiçbir şey sen onaylamadan Instagram'a gitmez.

Komutlar (GitHub Actions çalıştırır):
  python bot.py prepare   # sıradaki kartı hazırlar, görsel+caption'ı Telegram'a yollar
  python bot.py poll      # senin dokunuşlarını işler; Yayınla'da paylaşır

Telegram akışı:
  Kart gelir (görsel + caption tek mesajda) -> [Yayınla 🚀] [Atla ⏭️] [Düzelt ✏️]
  Düzelt: yeni caption'ı yazıp gönder -> kart aynı görselle, yeni caption'la döner.
  Yeni kart için 'sonraki' yaz.

Yerel test (Telegram/IG'siz):  python bot.py prepare --dry
"""
import argparse, datetime as dt, os
from pathlib import Path
import telegram as tg
from render import build_html, build_card, render, theme_for
from post import (approved, build_caption, pick, ig_publish, raw_url,
                  wait_until_live, load_bank, load_state, save_state, sh, ROOT, PUBDIR)

CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

PUB_BTNS = [[tg.btn("Yayınla 🚀", "yayinla")],
            [tg.btn("Atla ⏭️", "atla")],
            [tg.btn("Düzelt ✏️", "duzelt")]]

def safe_push():
    sh("git", "pull", "--rebase", "origin", BRANCH, check=False)
    sh("git", "push")

def commit(msg, *paths):
    for p in paths:
        sh("git", "add", p)
    r = sh("git", "commit", "-m", msg, check=False)
    if r.returncode == 0:
        safe_push()

def find(bank, _id):
    return next((g for g in bank["girisler"] if g["id"] == _id), None)

def render_and_push(entry, theme):
    PUBDIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    rel = f"published/{today}_{entry['id']}.png"
    render(build_card(entry, theme), ROOT / rel)
    commit(f"kart: {entry['id']} ({theme})", rel)
    url = raw_url(rel)
    wait_until_live(url)
    return url

def send_card(url, caption):
    """Görsel + caption'ı TEK mesajda, tek onay butonlarıyla yolla."""
    if len(caption) <= 1000:
        tg.send_photo(CHAT, url, caption=caption, buttons=PUB_BTNS)
    else:  # çok uzunsa (nadiren) görsel + ayrı metin
        tg.send_photo(CHAT, url)
        tg.send_message(CHAT, caption, buttons=PUB_BTNS)

def pick_typed(bank, state, tip=None):
    """tip: 'bilgi' | 'alinti' | 'podcast' | None(farketmez). Onaylı, paylaşılmamışı sırayla seçer."""
    items = approved(bank)
    if tip == "bilgi":
        items = [g for g in items if g.get("tip") == "bilgi" and not g.get("bolum")]
    elif tip == "alinti":
        items = [g for g in items if g.get("tip") != "bilgi" and not g.get("bolum")]
    elif tip == "podcast":
        items = [g for g in items if g.get("bolum")]
    if not items:
        return None
    posted_ids = {p.get("id") for p in state.get("posted", [])}
    fresh = [g for g in items if g["id"] not in posted_ids]
    pool = fresh if fresh else items
    return pool[state.get("pointer", 0) % len(pool)]

def queue_next(bank, state, tip=None):
    """idle ise sıradaki kartı hazırlayıp yollar. tip ile alıntı/bilgi süzülür."""
    if state.get("stage", "idle") != "idle":
        tg.send_message(CHAT, "Onay bekleyen bir kart zaten var. Önce onu bitir "
                              "(Yayınla / Atla).")
        return False
    entry = pick_typed(bank, state, tip)
    if not entry:
        ne = {"bilgi": "bilgi kartı", "alinti": "alıntı"}.get(tip, "kart")
        tg.send_message(CHAT, f"Bankada paylaşılacak yeni {ne} kalmadı.")
        return False
    theme = entry.get("tema_arkaplan") if entry.get("tema_arkaplan") \
            else theme_for(entry, state.get("pointer", 0))
    url = render_and_push(entry, theme)
    caption = build_caption(entry, bank)
    send_card(url, caption)
    state["stage"] = "await_publish"
    state["pending"] = {"id": entry["id"], "theme": theme,
                        "image_url": url, "caption": caption}
    return True

def prepare(dry=False):
    bank = load_bank(); state = load_state()
    if dry:
        entry, _ = pick(bank, state)
        entry = entry or (approved(bank) or bank["girisler"])[0]
        theme = entry.get("tema_arkaplan") or theme_for(entry, state.get("pointer", 0))
        PUBDIR.mkdir(exist_ok=True)
        render(build_card(entry, theme), ROOT / f"published/_dry_{entry['id']}.png")
        print(f"[dry] {entry['id']} / {theme}\n--- CAPTION ---\n{build_caption(entry, bank)}")
        return
    if queue_next(bank, state):
        save_state(state); commit("state: await_publish", "state/state.json")

def poll():
    bank = load_bank(); state = load_state()
    offset = state.get("telegram_offset", 0)
    updates = tg.get_updates(offset)
    changed = False
    for u in updates:
        offset = max(offset, u["update_id"] + 1); changed = True
        try:
            if u.get("callback_query"):
                handle_cb(bank, state, u["callback_query"]["data"])
            elif u.get("message", {}).get("text"):
                handle_text(bank, state, u["message"]["text"])
        except Exception as ex:                       # bir dokunuş patlarsa kuyruğu tıkamasın
            print("update işleme hatası:", ex)
            try: tg.send_message(CHAT, "Bu işlemde bir şey ters gitti, atlandı. Tekrar dene.")
            except Exception: pass
    state["telegram_offset"] = offset
    if changed:
        save_state(state); commit("state: poll", "state/state.json")
    print(f"{len(updates)} güncelleme işlendi.")

def handle_cb(bank, state, data):
    if state.get("stage") != "await_publish":
        return
    pend = state.get("pending") or {}
    if data == "yayinla":
        media = ig_publish(os.environ["IG_USER_ID"], os.environ["IG_TOKEN"],
                           pend["image_url"], pend["caption"])
        state.setdefault("posted", []).append(
            {"id": pend["id"], "date": dt.date.today().isoformat(), "media_id": media})
        state["pointer"] = state.get("pointer", 0) + 1
        state["stage"] = "idle"; state["pending"] = None; state["await_edit"] = False
        tg.send_message(CHAT, f"Yayınlandı ✅  (media_id {media})")
    elif data == "atla":
        state["pointer"] = state.get("pointer", 0) + 1
        state["stage"] = "idle"; state["pending"] = None; state["await_edit"] = False
        tg.send_message(CHAT, "Atlandı. Sıradakini hazırlıyorum…")
        queue_next(bank, state)
    elif data == "duzelt":
        state["await_edit"] = True
        tg.send_message(CHAT, "Yeni caption'ı yazıp gönder.")

def handle_text(bank, state, text):
    t = text.strip()
    if t.lower() in ("sonraki", "/sonraki", "next"):
        queue_next(bank, state); return
    if t.lower() in ("bilgi", "/bilgi"):
        queue_next(bank, state, tip="bilgi"); return
    if t.lower() in ("alıntı", "alinti", "/alinti"):
        queue_next(bank, state, tip="alinti"); return
    if t.lower() in ("bölüm", "bolum", "/bolum", "podcast"):
        queue_next(bank, state, tip="podcast"); return
    if t.lower() in ("/start", "start", "merhaba"):
        tg.send_message(CHAT, "Merhaba! Kart geldikçe görsel+caption tek mesajda gelir; "
                              "Yayınla dersen paylaşılır.\n\nKomutlar:\n"
                              "• sonraki — sıradaki kart (farketmez)\n"
                              "• alıntı — sıradaki alıntı kartı\n"
                              "• bilgi — sıradaki bilgi kartı\n"
                              "• bölüm — sıradaki podcast/bölüm kartı"); return
    if state.get("stage") == "await_publish":       # metin = yeni caption
        pend = state.get("pending") or {}
        pend["caption"] = text; state["pending"] = pend; state["await_edit"] = False
        send_card(pend["image_url"], text)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "poll"])
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    prepare(dry=a.dry) if a.cmd == "prepare" else poll()
