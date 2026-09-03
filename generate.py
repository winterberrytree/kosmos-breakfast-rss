#!/usr/bin/env python3
import os
import re
import sys
import html
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

SHOW_NAME = "Breakfast στον Κόσμο"
AUTHOR = "Προκόπης Δούκας"
SHOW_URL = "https://www.ertecho.gr/radio/kosmos/show/breakfast-ston-kosmo/"
DESCRIPTION = (
    "Ιδιωτικό RSS feed για την εκπομπή «Breakfast στον Κόσμο» του Προκόπη Δούκα "
    "στο KOSMOS / ΕΡΤ. Τα αρχεία ήχου μεταδίδονται απευθείας από τους servers της ΕΡΤ."
)

MAX_ARCHIVE_PAGES = int(os.getenv("MAX_ARCHIVE_PAGES", "3"))
MAX_EPISODES = int(os.getenv("MAX_EPISODES", "40"))
TIMEOUT = 30

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 "
    "KosmosBreakfastRSS/1.0"
)
session = requests.Session()
session.headers.update({"User-Agent": UA})

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)


def get(url):
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def archive_url(page):
    if page == 1:
        return SHOW_URL
    return urljoin(SHOW_URL, f"page/{page}/")


def episode_links():
    links = []
    seen = set()
    for page in range(1, MAX_ARCHIVE_PAGES + 1):
        soup = BeautifulSoup(get(archive_url(page)).text, "html.parser")
        found = 0
        for a in soup.find_all("a", href=True):
            href = urljoin(SHOW_URL, a["href"])
            if "/show/breakfast-ston-kosmo/ondemand/" not in href:
                continue
            href = href.split("#")[0].split("?")[0]
            if not href.endswith("/"):
                href += "/"
            if href not in seen:
                seen.add(href)
                links.append(href)
                found += 1
        if found == 0:
            break
    return links[:MAX_EPISODES]


DATE_RE = re.compile(r"(\d{2})[./-](\d{2})[./-](\d{4})")
MP3_RE = re.compile(r'https?://[^"\'<>\s]+\.mp3(?:\?[^"\'<>\s]*)?', re.I)


def parse_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    # The recording is normally the 08:00–10:00 programme, Athens time.
    # RSS requires an absolute timestamp; using 08:00 UTC is adequate for ordering.
    return datetime(y, mth, d, 8, 0, tzinfo=timezone.utc)


def episode_data(url):
    amp_url = urljoin(url, "amp/")
    amp = get(amp_url)
    soup = BeautifulSoup(amp.text, "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)

    date = parse_date(title) or parse_date(soup.get_text(" ", strip=True))
    if not date:
        raise RuntimeError(f"Could not find episode date: {url}")

    mp3 = None

    # First prefer actual audio/source tags.
    for tag in soup.find_all(["audio", "source"]):
        src = tag.get("src")
        if src and ".mp3" in src.lower():
            mp3 = urljoin(amp_url, src)
            break

    # ERT's AMP pages also expose the MP3 as plain text/markup.
    if not mp3:
        match = MP3_RE.search(amp.text)
        if match:
            mp3 = html.unescape(match.group(0))

    if not mp3:
        raise RuntimeError(f"Could not find MP3: {url}")

    desc = ""
    # Prefer a meaningful paragraph rather than cookie/menu text.
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if "Προκόπης Δούκας" in t or "Δευτέρα" in t:
            desc = t
            break
    if not desc:
        desc = f"{SHOW_NAME} — {AUTHOR}"

    length = "0"
    try:
        head = session.head(mp3, allow_redirects=True, timeout=TIMEOUT)
        if head.ok and head.headers.get("Content-Length"):
            length = head.headers["Content-Length"]
    except requests.RequestException:
        pass

    return {
        "title": title.replace(" - ERT εcho", "").strip(),
        "url": url,
        "mp3": mp3,
        "date": date,
        "description": desc,
        "length": length,
    }


def feed_url():
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/feed.xml"
    return "https://example.invalid/feed.xml"


def build_feed(episodes):
    rss = ET.Element("rss", {
        "version": "2.0",
    })
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = SHOW_NAME
    ET.SubElement(channel, "link").text = SHOW_URL
    ET.SubElement(channel, "description").text = DESCRIPTION
    ET.SubElement(channel, "language").text = "el"
    ET.SubElement(channel, "generator").text = "Kosmos Breakfast RSS"
    ET.SubElement(channel, f"{{{ITUNES}}}author").text = AUTHOR
    ET.SubElement(channel, f"{{{ITUNES}}}explicit").text = "false"
    ET.SubElement(channel, f"{{{ITUNES}}}type").text = "episodic"
    ET.SubElement(channel, f"{{{ATOM}}}link", {
        "href": feed_url(),
        "rel": "self",
        "type": "application/rss+xml",
    })

    if episodes:
        ET.SubElement(channel, "lastBuildDate").text = format_datetime(
            datetime.now(timezone.utc)
        )

    for ep in sorted(episodes, key=lambda x: x["date"], reverse=True):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = ep["title"]
        ET.SubElement(item, "link").text = ep["url"]
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = ep["mp3"]
        ET.SubElement(item, "pubDate").text = format_datetime(ep["date"])
        ET.SubElement(item, "description").text = ep["description"]
        ET.SubElement(item, f"{{{ITUNES}}}author").text = AUTHOR
        ET.SubElement(item, f"{{{ITUNES}}}explicit").text = "false"
        ET.SubElement(item, "enclosure", {
            "url": ep["mp3"],
            "length": ep["length"],
            "type": "audio/mpeg",
        })

    return ET.ElementTree(rss)


def main():
    links = episode_links()
    if not links:
        raise RuntimeError("No episode links found on ERT archive.")

    episodes = []
    errors = []
    for i, url in enumerate(links, 1):
        try:
            ep = episode_data(url)
            episodes.append(ep)
            print(f"[{i}/{len(links)}] OK: {ep['title']}")
        except Exception as e:
            errors.append(f"{url}: {e}")
            print(f"[{i}/{len(links)}] WARN: {url}: {e}", file=sys.stderr)

    if not episodes:
        raise RuntimeError("Could not extract any playable episodes.")

    out = Path("docs")
    out.mkdir(exist_ok=True)
    tree = build_feed(episodes)
    ET.indent(tree, space="  ")
    tree.write(out / "feed.xml", encoding="utf-8", xml_declaration=True)

    latest = max(episodes, key=lambda x: x["date"])
    index = f"""<!doctype html>
<html lang="el">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{SHOW_NAME} — RSS</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:720px;margin:64px auto;padding:0 24px;line-height:1.55}}
code{{word-break:break-all}}
</style>
<h1>{SHOW_NAME}</h1>
<p>Ανεπίσημο προσωπικό RSS feed για την εκπομπή του {AUTHOR} στο KOSMOS.</p>
<p><strong>RSS:</strong> <a href="feed.xml">feed.xml</a></p>
<p>Τελευταίο επεισόδιο στο feed: {latest['date'].strftime('%d/%m/%Y')}</p>
<p>Ο ήχος δεν φιλοξενείται εδώ· το podcast app συνδέεται απευθείας στα MP3 της ΕΡΤ.</p>
</html>"""
    (out / "index.html").write_text(index, encoding="utf-8")

    print(f"\nWrote {len(episodes)} episodes to docs/feed.xml")
    if errors:
        print(f"{len(errors)} episode(s) skipped.", file=sys.stderr)


if __name__ == "__main__":
    from pathlib import Path
    main()
