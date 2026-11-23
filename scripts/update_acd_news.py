#!/usr/bin/env python3
"""Collecte les actualités BTS ACD depuis le site officiel du Lycée Pommerit."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE = "https://www.lycee.pommerit.fr/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SolActif-ACD-NewsBot/1.0)"}
HOST = urlparse(BASE).netloc
ACD = re.compile(r"\bBTS\s*ACD\b|BTSA\s+ACD|Agronomie\s+Cultures\s+Durables", re.I)
DATE = re.compile(
    r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*"
    r"\d{1,2}(?:er)?\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|"
    r"août|aout|septembre|octobre|novembre|décembre|decembre)\s+20\d{2}",
    re.I,
)
session = requests.Session()
session.headers.update(HEADERS)

def get(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response

def soup(url):
    return BeautifulSoup(get(url).text, "html.parser")

# On utilise le sitemap du domaine officiel plutôt que de supposer la structure
# HTML ou la pagination SPIP de la rubrique Actualités.
urls = set()
for sitemap_url in (urljoin(BASE, "sitemap.xml"), urljoin(BASE, "spip.php?page=sitemap")):
    try:
        root = ET.fromstring(get(sitemap_url).content)
        for node in root.iter():
            if node.tag.lower().endswith("loc") and node.text:
                u = node.text.strip()
                if urlparse(u).netloc == HOST:
                    urls.add(u)
    except (requests.RequestException, ET.ParseError) as exc:
        print(f"Sitemap indisponible ({sitemap_url}): {exc}")

# Filet de sécurité : articles ACD officiels déjà repérés sur le site.
known = [
    "Les-BTS-ACD-1-a-la-station-experimentale-de-Kerguehennec",
    "BTS-ACD-1-cap-sur-le-Quebec",
    "Les-BTS-ACD-decouvrent-la-plateforme-d-essais-Eureden",
]
for slug in known:
    urls.add(urljoin(BASE, slug))

# Ne garde que les pages éditoriales candidates et exclut la fiche permanente.
candidates = []
for url in sorted(urls):
    path = urlparse(url).path
    if not path or path.endswith((".pdf", ".jpg", ".png")):
        continue
    if re.search(r"BTS-ACD-Agronomie-Cultures-Durables/?$", path, re.I):
        continue
    candidates.append(url)

items = []
for url in candidates:
    try:
        page = soup(url)
        h1 = page.find("h1")
        title = " ".join(h1.get_text(" ", strip=True).split()) if h1 else ""
        if not title:
            meta = page.select_one('meta[property="og:title"]')
            title = (meta.get("content") or "").strip() if meta else ""
        if not title:
            continue

        # On valide la page avec son titre ET son contenu, mais le titre reste
        # celui de l'article. Les liens de menu ne peuvent donc pas suffire.
        main = page.find("article") or page.find("main") or page.select_one("#content, #contenu") or page.body or page
        content = " ".join(main.get_text(" ", strip=True).split())
        if not ACD.search(title + " " + content):
            continue
        if re.fullmatch(r"BTS\s*ACD\s*:?\s*Agronomie\s+Cultures\s+Durables", title, re.I):
            continue

        # Date de publication près du titre, puis dans les métadonnées de page.
        match = DATE.search(content[:1800])
        date = match.group(0).strip() if match else ""
        if not date:
            for selector in ('time[datetime]', 'meta[property="article:published_time"]'):
                node = page.select_one(selector)
                if node:
                    date = node.get("datetime") or node.get("content") or ""
                    if date:
                        break
        items.append({"title": title, "url": url, "date": date})
    except requests.RequestException as exc:
        print(f"Page ignorée ({url}): {exc}")

# Articles BTS ACD explicitement vérifiés sur le site officiel.
# Ils servent de base fiable même si le sitemap du lycée est incomplet.
verified = [
    {"title": "Les BTS ACD 1 à la station expérimentale de Kerguéhennec",
     "url": "https://www.lycee.pommerit.fr/Les-BTS-ACD-1-a-la-station-experimentale-de-Kerguehennec",
     "date": "lundi 28 septembre 2026"},
    {"title": "BTS ACD 1 : cap sur le Québec !",
     "url": "https://www.lycee.pommerit.fr/BTS-ACD-1-cap-sur-le-Quebec",
     "date": "jeudi 4 juin 2026"},
    {"title": "Les BTS ACD découvrent la plateforme d’essais Eureden",
     "url": "https://www.lycee.pommerit.fr/Les-BTS-ACD-decouvrent-la-plateforme-d-essais-Eureden",
     "date": "mercredi 15 avril 2026"},
]

# Les articles vérifiés sont prioritaires ; les nouvelles pages trouvées
# automatiquement sont ajoutées ensuite, sans doublons.
unique = []
seen = set()
for item in verified + items:
    if item["url"] not in seen:
        seen.add(item["url"])
        unique.append(item)
unique = unique[:5]

payload = {
    "source": BASE,
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "count": len(unique),
    "items": unique,
}
Path("acd-news.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"{len(unique)} actualité(s) BTS ACD publiée(s) dans acd-news.json.")
