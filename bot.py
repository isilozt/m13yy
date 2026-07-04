#!/usr/bin/env python3
"""
bot.py — ONAYLI yayın akışı. Hiçbir şey sen onaylamadan Instagram'a gitmez.

Komutlar (GitHub Actions çalıştırır, sen dokunmazsın):
  python bot.py prepare   # (günlük) sıradaki kartı hazırlar, görseli Telegram'a yollar
  python bot.py poll      # (10 dk'da bir) senin dokunuşlarını/işleyip yayınlar

Telegram akışı:
  1) Görsel gelir  -> [Onayla ✅] [Farklı zemin 🎨] [Atla ⏭️]
  2) Onaylarsan caption gelir -> [Yayınla 🚀] [Düzelt ✏️] [İptal ❌]
     (Düzeltmek için yeni caption'ı yazıp gönder.)
  3) Yayınla dersen -> Instagram'a paylaşılır.

Yerel test (Telegram/IG'siz):  python bot.py prepare --dry
"""
import argparse, datetime as dt, os
from pathlib import Path
import telegram as tg
from render import build_html, render, theme_for, ROTATION
from post import (approved, build_caption, pick, ig_publish, raw_url,
                  wait_until_live, load_bank, load_state, save_state, sh, ROOT, PUBDIR)

CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

IMG_BTNS = [[tg.btn("Onayla ✅", "img_ok")],
            [tg.btn("Farklı zemin 🎨", "img_theme")],
            [tg.btn("Atla ⏭️", "img_skip")]]
CAP_BTNS = [[tg.btn("Yayınla 🚀", "cap_ok")],
            [tg.btn("Düzelt ✏️", "cap_edit")],
            [tg.btn("İptal ❌", "cap_cancel")]]

# ---------- git yardımcıları ------------------------------------------------
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

# ---------- kart hazırla (state'i yerinde değiştirir; kaydetmez) -------------
def render_and_push(entry, theme):
    PUBDIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    rel = f"published/{today}_{entry['id']}.png"
    render(build_html(tema=entry.get("tema", ""), quote=entry["metin_tr"],
                      author=entry["sahis"], work=entry.get("eser", ""),
                      theme_name=theme), ROOT / rel)
    commit(f"kart: {entry['id']} ({theme})", rel)
    url = raw_url(rel)
    wait_until_live(url)
    return rel, url

def queue_next(bank, state):
    """stage idle ise sıradaki kartı hazırlayıp görseli yollar. state'i günceller."""
    if state.get("stage", "idle") != "idle":
        return False
    entry, _ = pick(bank, state)
    if not entry:
        if CHAT:
            tg.send_message(CHAT, "Bankada paylaşılacak onaylı alıntı kalmadı. "
                                  "Yeni alıntı ekleyince buradan devam ederiz.")
        return False
    theme = theme_for(entry, state.get("pointer", 0))
    rel, url = render_and_push(entry, theme)
    tg.send_photo(CHAT, url,
                  caption=f"Yeni kart hazır ({entry['id']}). Bu görseli onaylıyor musun?",
                  buttons=IMG_BTNS)
    state["stage"] = "await_image"
    state["pending"] = {"id": entry["id"], "theme": theme,
                        "theme_i": ROTATION.index(theme) if theme in ROTATION else 0,
                        "image_rel": rel, "image_url": url}
    return True

# ---------- komutlar ---------------------------------------------------------
def prepare(dry=False):
    bank = load_bank(); state = load_state()
    if dry:
        entry, _ = pick(bank, state)
        entry = entry or (approved(bank) or bank["girisler"])[0]
        theme = theme_for(entry, state.get("pointer", 0))
        PUBDIR.mkdir(exist_ok=True)
        render(build_html(tema=entry.get("tema", ""), quote=entry["metin_tr"],
                          author=entry["sahis"], work=entry.get("eser", ""),
                          theme_name=theme), ROOT / f"published/_dry_{entry['id']}.png")
        print(f"[dry] {entry['id']} / {theme}\n--- CAPTION ---\n{build_caption(entry, bank)}")
        return
    if state.get("stage", "idle") != "idle":
        print("Onay bekleyen bir kart zaten var; yeni hazırlanmadı."); return
    if queue_next(bank, state):
        save_state(state); commit("state: await_image", "state/state.json")

def poll():
    bank = load_bank(); state = load_state()
    offset = state.get("telegram_offset", 0)
    updates = tg.get_updates(offset)
    changed = False
    for u in updates:
        offset = max(offset, u["update_id"] + 1); changed = True
        if u.get("callback_query"):
            cq = u["callback_query"]
            handle_cb(bank, state, cq["data"])
        elif u.get("message", {}).get("text"):
            handle_text(bank, state, u["message"]["text"])
    state["telegram_offset"] = offset
    if changed:
        save_state(state); commit("state: poll", "state/state.json")
    print(f"{len(updates)} güncelleme işlendi.")

def handle_cb(bank, state, data):
    stage = state.get("stage", "idle"); pend = state.get("pending") or {}
    if stage == "await_image":
        if data == "img_ok":
            cap = build_caption(find(bank, pend["id"]), bank)
            pend["caption"] = cap
            tg.send_message(CHAT, "Caption:\n\n" + cap +
                            "\n\nYayınlayayım mı? (Düzeltmek için yeni metni yaz.)",
                            buttons=CAP_BTNS)
            state["stage"] = "await_caption"; state["pending"] = pend
        elif data == "img_theme":
            i = (pend.get("theme_i", 0) + 1) % len(ROTATION); theme = ROTATION[i]
            rel, url = render_and_push(find(bank, pend["id"]), theme)
            pend.update(theme=theme, theme_i=i, image_rel=rel, image_url=url)
            tg.send_photo(CHAT, url, caption=f"Zemin: {theme}. Böyle mi?", buttons=IMG_BTNS)
            state["pending"] = pend
        elif data == "img_skip":
            state["pointer"] = state.get("pointer", 0) + 1
            state["stage"] = "idle"; state["pending"] = None
            tg.send_message(CHAT, "Atlandı. Sıradakini hazırlıyorum…")
            queue_next(bank, state)
    elif stage == "await_caption":
        if data == "cap_ok":
            media = ig_publish(os.environ["IG_USER_ID"], os.environ["IG_TOKEN"],
                               pend["image_url"], pend["caption"])
            state.setdefault("posted", []).append(
                {"id": pend["id"], "date": dt.date.today().isoformat(), "media_id": media})
            state["pointer"] = state.get("pointer", 0) + 1
            state["stage"] = "idle"; state["pending"] = None
            tg.send_message(CHAT, f"Yayınlandı ✅  (media_id {media})")
        elif data == "cap_edit":
            tg.send_message(CHAT, "Yeni caption'ı yazıp gönder.")
        elif data == "cap_cancel":
            state["stage"] = "idle"; state["pending"] = None
            tg.send_message(CHAT, "İptal edildi. Kart yayınlanmadı. "
                                  "Yeni bir kart için 'sonraki' yaz.")

def handle_text(bank, state, text):
    t = text.strip()
    if state.get("stage") == "await_caption":
        pend = state.get("pending") or {}
        pend["caption"] = text; state["pending"] = pend
        tg.send_message(CHAT, "Caption güncellendi:\n\n" + text +
                        "\n\nYayınlayayım mı?", buttons=CAP_BTNS)
    elif t.lower() in ("sonraki", "/sonraki", "next"):
        if not queue_next(bank, state):
            tg.send_message(CHAT, "Şu an hazırlanacak yeni kart yok "
                                  "(ya bekleyen var ya da banka bitti).")
    elif t.lower() in ("/start", "start", "merhaba"):
        tg.send_message(CHAT, "Merhaba! Kartlar hazır oldukça buraya gelecek: "
                              "önce görsel, sonra caption, sonra sen 'Yayınla' de. "
                              "İstediğin an 'sonraki' yazarak yeni kart isteyebilirsin.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "poll"])
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    prepare(dry=a.dry) if a.cmd == "prepare" else poll()
