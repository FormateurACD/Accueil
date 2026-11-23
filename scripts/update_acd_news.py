#!/usr/bin/env python3
"""Récupère les articles BTS ACD depuis le site officiel du Lycée Pommerit."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.lycee.pommerit.fr/"
NEWS = urljoin(BASE, "-Actualites-")
HEADERS = {"User-Agent": "SolActif-ACD-NewsBot/1.0 (veille pédagogique)"}
KEYWORDS = re.compile(r"bts\s*acd|btsa.{0,50}agronomie.{0,50}cultures durables|agronomie.{0,50}cultures durables", re.I)
DATE = re.compile(r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*\d{1,2}\s+[a-zéû]+\s+20\d{2}", re.I)

session = requests.Session()
session.headers.update(HEADERS)

def soup_for(url):
    response = session.get(url, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return BeautifulSoup(response.text, "html.parser")

listing = soup_for(NEWS)
candidates = []
seen = set()
for a in listing.select("a[href]"):
    href = urljoin(BASE, a.get("href", "").strip())
    title = " ".join(a.get_text(" ", strip=True).split())
    parsed = urlparse(href)
    if parsed.netloc != urlparse(BASE).netloc or not title:
        continue
    if href.rstrip("/") in (BASE.rstrip("/"), NEWS.rstrip("/")):
        continue
    if not parsed.path.startswith("/") or parsed.path.startswith("/IMG/"):
        continue
    if href in seen:
        continue
    seen.add(href)
    candidates.append((href, title))

items = []
for url, link_title in candidates[:70]:
    try:
        page = soup_for(url)
        text = " ".join(page.get_text(" ", strip=True).split())
        title_node = page.find(["h1", "h2"])
        title = " ".join(title_node.get_text(" ", strip=True).split()) if title_node else link_title
        if not KEYWORDS.search(title + " " + text):
            continue
        match = DATE.search(text)
        date = match.group(0).strip() if match else ""
        items.append({"title": title, "url": url, "date": date})
    except requests.RequestException as exc:
        print(f"Page ignorée ({url}): {exc}")

# Déduplique et conserve les cinq articles les plus récents selon leur ordre sur le site.
unique = []
urls = set()
for item in items:
    if item["url"] not in urls:
        urls.add(item["url"])
        unique.append(item)
    if len(unique) == 5:
        break

payload = {
    "source": NEWS,
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "count": len(unique),
    "items": unique,
}
Path("acd-news.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(unique)} actualité(s) BTS ACD trouvée(s).")
