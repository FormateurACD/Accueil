#!/usr/bin/env python3
"""Récupère uniquement les articles consacrés au BTS ACD sur le site officiel."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.lycee.pommerit.fr/"
NEWS = urljoin(BASE, "-Actualites-")
HEADERS = {"User-Agent": "SolActif-ACD-NewsBot/1.0"}
# Le chemin de l'article doit lui-même identifier le BTS ACD : on ne cherche
# surtout pas le mot ACD dans toute la page (menu et pied de page compris).
SLUG = re.compile(r"bts[-_ ]acd", re.I)
DATE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
    r"\d{1,2}\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"août|aout|septembre|octobre|novembre|décembre|decembre)\s+20\d{2}",
    re.I,
)

session = requests.Session()
session.headers.update(HEADERS)

def get_soup(url):
    response = session.get(url, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return BeautifulSoup(response.text, "html.parser")

listing = get_soup(NEWS)
urls = []
seen = set()
for a in listing.select("a[href]"):
    url = urljoin(BASE, a.get("href", "").strip()).split("#")[0]
    parsed = urlparse(url)
    if parsed.netloc != urlparse(BASE).netloc or not SLUG.search(parsed.path):
        continue
    if url not in seen:
        seen.add(url)
        urls.append(url)

items = []
for url in urls:
    try:
        page = get_soup(url)
        title = ""
        for selector, attr in [
            ('meta[property="og:title"]', "content"),
            ('meta[name="twitter:title"]', "content"),
        ]:
            node = page.select_one(selector)
            if node and node.get(attr):
                title = node.get(attr).strip()
                break
        if not title:
            node = page.find("h1")
            if node:
                title = " ".join(node.get_text(" ", strip=True).split())
        if not title:
            node = page.find("title")
            if node:
                title = node.get_text(" ", strip=True).split(" - Lycée Pommerit")[0].strip()
        if not title:
            continue
        # Sécurité supplémentaire : le titre doit parler du BTS ACD.
        if not re.search(r"bts\s*acd|bts[- ]acd", title, re.I):
            continue

        body = page.find("main") or page.find("article") or page.body or page
        body_text = " ".join(body.get_text(" ", strip=True).split())
        title_pos = body_text.lower().find(title.lower())
        date_area = body_text[title_pos + len(title):title_pos + len(title) + 700] if title_pos >= 0 else body_text[:700]
        date_match = DATE.search(date_area)
        date = date_match.group(0).strip() if date_match else ""
        items.append({"title": title, "url": url, "date": date})
    except requests.RequestException as exc:
        print(f"Article ignoré ({url}): {exc}")

# Le site affiche ses actualités dans l'ordre antéchronologique.
items = items[:5]
payload = {
    "source": NEWS,
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "count": len(items),
    "items": items,
}
Path("acd-news.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(items)} article(s) BTS ACD trouvé(s).")
