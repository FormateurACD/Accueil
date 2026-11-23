#!/usr/bin/env python3
"""Récupère les articles BTS ACD depuis la rubrique Actualités officielle de Pommerit."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.lycee.pommerit.fr/"
NEWS = urljoin(BASE, "-Actualites-")
HOST = urlparse(BASE).netloc
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SolActif-ACD-NewsBot/1.0)"}
ACD = re.compile(r"\bBTS\s*ACD\b|BTSA\s+ACD|Agronomie\s+Cultures\s+Durables", re.I)
DATE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
    r"\d{1,2}(?:er)?\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"août|aout|septembre|octobre|novembre|décembre|decembre)\s+20\d{2}",
    re.I,
)
session = requests.Session()
session.headers.update(HEADERS)

def get_soup(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return BeautifulSoup(response.text, "html.parser")

candidate_urls = []
seen = set()
# Pagination SPIP réelle : ?debut_articles=10, 20, 30...
for offset in range(0, 201, 10):
    listing_url = NEWS if offset == 0 else f"{NEWS}?debut_articles={offset}"
    try:
        listing = get_soup(listing_url)
    except requests.RequestException as exc:
        print(f"Impossible de lire {listing_url}: {exc}")
        continue

    content = listing.find("main")
    if content is None:
        content = listing.select_one("#content, #contenu, .content, .contenu")
    if content is None:
        content = listing.body or listing

    for a in content.select("a[href]"):
        url = urljoin(BASE, a.get("href", "").strip()).split("#")[0]
        parsed = urlparse(url)
        if parsed.netloc != HOST or parsed.path.rstrip("/") in ("", "/-Actualites-"):
            continue
        if "debut_articles" in url or "/IMG/" in parsed.path:
            continue
        # La fiche de formation permanente n'est pas un article d'actualité.
        if re.search(r"/BTS-ACD-Agronomie-Cultures-Durables/?$", parsed.path, re.I):
            continue
        if url not in seen:
            seen.add(url)
            candidate_urls.append(url)

items = []
for url in candidate_urls:
    try:
        page = get_soup(url)
        h1 = page.find("h1")
        title = " ".join(h1.get_text(" ", strip=True).split()) if h1 else ""
        og = page.select_one('meta[property="og:title"]')
        if not title and og:
            title = (og.get("content") or "").strip()
        if not title:
            continue

        article = page.find("article") or page.find("main") or page.select_one("#content, #contenu") or page.body or page
        article_text = " ".join(article.get_text(" ", strip=True).split())
        if not ACD.search(title):
            continue
        if re.fullmatch(r"BTS\s*ACD\s*:?\s*Agronomie\s+Cultures\s+Durables", title, re.I):
            continue

        title_index = article_text.lower().find(title.lower())
        near_title = article_text[title_index + len(title):title_index + len(title) + 900] if title_index >= 0 else article_text[:900]
        match = DATE.search(near_title)
        date = match.group(0).strip() if match else ""
        items.append({"title": title, "url": url, "date": date})
    except requests.RequestException as exc:
        print(f"Article ignoré ({url}): {exc}")

unique = []
used = set()
for item in items:
    if item["url"] not in used:
        used.add(item["url"])
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
print(f"{len(unique)} véritable(s) actualité(s) BTS ACD trouvée(s).")
if not unique:
    raise SystemExit("Aucun article ACD trouvé : vérifier la structure de la rubrique officielle.")
