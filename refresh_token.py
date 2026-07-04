#!/usr/bin/env python3
"""
refresh_token.py — long-lived token'ı yeniler (60 gün uzatır) ve IG_TOKEN secret'ını günceller.

Gerekli ortam değişkenleri:
  IG_TOKEN            mevcut long-lived token
  GH_PAT             repo secrets: read+write yetkili fine-grained token
  GITHUB_REPOSITORY  owner/repo (Actions otomatik verir)

GH_PAT tanımlı değilse: sadece yeni token'ı basar, secret'ı güncelleyemez (uyarı verir).
"""
import base64, os, sys, requests
from nacl import encoding, public

GRAPH = "https://graph.instagram.com"

def refresh(token):
    r = requests.get(f"{GRAPH}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token},
                     timeout=30)
    r.raise_for_status()
    j = r.json()
    return j["access_token"], j.get("expires_in")

def update_secret(repo, pat, name, value):
    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    k = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                     headers=h, timeout=30).json()
    sealed = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder))
    enc = base64.b64encode(sealed.encrypt(value.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
                     headers=h, timeout=30,
                     json={"encrypted_value": enc, "key_id": k["key_id"]})
    r.raise_for_status()

def main():
    token = os.environ["IG_TOKEN"]
    new_token, expires = refresh(token)
    days = round((expires or 0) / 86400)
    print(f"Token yenilendi (~{days} gün geçerli).")
    pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if pat and repo:
        update_secret(repo, pat, "IG_TOKEN", new_token)
        print("IG_TOKEN secret güncellendi ✓")
    else:
        print("UYARI: GH_PAT yok — secret güncellenemedi. Yeni token'ı elle IG_TOKEN'a yaz.")
        print("Yeni token:", new_token)

if __name__ == "__main__":
    main()
