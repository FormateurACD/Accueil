#!/usr/bin/env python3
"""Récupère les actualités BTS ACD depuis les pages paginées du site officiel."""
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
ACD = re.compile(r"\bBTS\s*ACD\b|BTSA\s+ACD|Agronomie\s+Cultures\s+Durables", re.I)
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

candidates = {}
# La rubrique est paginée par tranches de dix articles. On parcourt les pages
# récentes pour ne pas confondre la page de présentation du diplôme avec une actualité.
for offset in range(0, 101, 10):
    listing_url = NEWS if offset == 0 else f"{NEWS}?debut_articles={offset}"
    try:
        listing = get_soup(listing_url)
    except requests.RequestException as exc:
        print(f"Page d'actualités ignorée ({listing_url}): {exc}")
        continue

    for a in listing.select("a[href]"):
        href = urljoin(BASE, a.get("href", "").strip()).split("#")[0]
        parsed = urlparse(href)
        if parsed.netloc != urlparse(BASE).netloc:
            continue
        # Écarte les liens du menu et de navigation : l'article doit être
        # dans un bloc de contenu d'actualité qui mentionne explicitement ACD.
        if href.rstrip("/") in (BASE.rstrip("/"), NEWS.rstrip("/")):
            continue
        title_text = " ".join(a.get_text(" ", strip=True).split())
        block = a.find_parent(["article", "li"])
        if block is None:
            block = a.parent.parent if a.parent and a.parent.parent else a.parent
        context = " ".join(block.get_text(" ", strip=True).split()) if block else title_text
        if not ACD.search(title_text + " " + context):
            continue
        # Le lien vers une actualité doit être un vrai lien de contenu, pas
        # la fiche de formation du BTS.
        if "Agronomie-Cultures-Durables" in parsed.path and "BTS-ACD-" not in parsed.path:
            continue
        candidates[href] = title_text or context[:160]

items = []
for url, link_title in candidates.items():
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
            title = link_title
        if not title or not ACD.search(title):
            continue

        body = page.find("main") or page.find("article") or page.body or page
        body_text = " ".join(body.get_text(" ", strip=True).split())
        # La date de publication est généralement proche du titre en haut de page.
        date_match = DATE.search(body_text[:1200])
        date = date_match.group(0).strip() if date_match else ""
        items.append({"title": title, "url": url, "date": date})
    except requests.RequestException as exc:
        print(f"Article ignoré ({url}): {exc}")

# Déduplique et conserve les cinq articles les plus récents selon l'ordre du site.
unique = []
seen = set()
for item in items:
    if item["url"] in seen:
        continue
    seen.add(item["url"])
    unique.append(item)
    if len(unique) == 5:
        break

payload = {
    "source": NEWS,
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "count": len(unique),
    "items": unique,
}
Path("acd-news.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"{len(unique)} actualité(s) BTS ACD trouvée(s).")
