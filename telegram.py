#!/usr/bin/env python3
"""telegram.py — Telegram Bot API için ince yardımcı (sadece requests)."""
import os, requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"

def _call(method, **params):
    r = requests.post(f"{API}/{method}", json=params, timeout=40)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} hatası: "
                           f"{data.get('error_code')} — {data.get('description')}")
    return data["result"]

def send_photo(chat_id, photo_url, caption=None, buttons=None):
    p = {"chat_id": chat_id, "photo": photo_url}
    if caption: p["caption"] = caption
    if buttons: p["reply_markup"] = {"inline_keyboard": buttons}
    return _call("sendPhoto", **p)

def send_message(chat_id, text, buttons=None):
    p = {"chat_id": chat_id, "text": text}
    if buttons: p["reply_markup"] = {"inline_keyboard": buttons}
    return _call("sendMessage", **p)

def answer_callback(cb_id, text=None):
    p = {"callback_query_id": cb_id}
    if text: p["text"] = text
    return _call("answerCallbackQuery", **p)

def get_updates(offset=0, timeout=0):
    return _call("getUpdates", offset=offset, timeout=timeout,
                 allowed_updates=["message", "callback_query"])

def btn(text, data):
    return {"text": text, "callback_data": data}
