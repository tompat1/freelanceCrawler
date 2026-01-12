# freelanceCrawler
A simple crawler of an web page of page links for getting contact info

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python -m freelance_crawler.cli
```

## Run the UI

```bash
python -m freelance_crawler.ui_server
```

Then open `http://localhost:8000` to track crawl progress and review recent contact results.

### Options

```bash
python -m freelance_crawler.cli --delay 1.5 --timeout 20 --output contacts.csv
```
Yes — technically it’s doable, but there are a few practical + legal gotchas.

On that page, “Våra medlemmar” is essentially a long directory of outbound links to member publications/sites. ([Sveriges Tidskrifter][1])
To “check every link” and extract emails/phone numbers, you’d typically build a small crawler that:

1. **Fetches the directory page** and extracts all member URLs.
2. **Visits each site** (often just the homepage first).
3. **Looks for contact pages** (links containing e.g. `kontakt`, `contact`, `om`, `about`, `annonser`, `editorial`, etc.).
4. **Extracts emails + phones** using regex + common obfuscation patterns (`name [at] domain`, `name(at)domain`, etc.).
5. **Exports results** to CSV/Excel.

### Things that can block “100% coverage”

* **Robots / terms of use**: some sites disallow crawling; you should respect `robots.txt` and be gentle with rate limits.
* **GDPR / personal emails**: collecting personal contact info can become a compliance issue depending on use/storage/purpose.
* **Obfuscation & JS rendering**: many sites hide emails behind scripts/images; basic HTML scraping won’t catch everything.
* **False positives**: regex will pick up random strings unless you validate/clean.

### A solid Python starting point (runs locally)

This is a practical “best effort” crawler that grabs the member links from the directory page, then tries to find emails/phones on the homepage + a few likely contact pages, and writes a CSV:

```python
import re
import csv
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DIRECTORY_URL = "https://sverigestidskrifter.se/vara-medlemmar/"

# Basic patterns (tweak as needed)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Loose-ish phone pattern for Sweden/international; you'll likely refine this
PHONE_RE = re.compile(r"(\+?\d[\d\s().\-]{6,}\d)")

CONTACT_HINTS = ["kontakt", "contact", "om", "about", "annonser", "editor", "redaktion"]

HEADERS = {"User-Agent": "ContactFinder/1.0 (+local script)"}
TIMEOUT = 15
DELAY_S = 1.0  # be polite

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def extract_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        # Keep http(s) only
        if href.startswith("http://") or href.startswith("https://"):
            links.add(href)
        else:
            # allow relative links on same site
            links.add(urljoin(base_url, href))
    return links

def normalize_site(url):
    # normalize to scheme+netloc root
    p = urlparse(url)
    if not p.scheme:
        return None
    return f"{p.scheme}://{p.netloc}/"

def find_candidate_contact_pages(html, base_url, limit=8):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = (a.get_text() or "").lower()
        target = (href or "").lower()
        if any(h in text or h in target for h in CONTACT_HINTS):
            full = urljoin(base_url, href)
            candidates.append(full)
    # de-dup while preserving order
    seen = set()
    out = []
    for u in candidates:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out[:limit]

def extract_contacts(text):
    emails = set(EMAIL_RE.findall(text))
    phones = set(m.strip() for m in PHONE_RE.findall(text))

    # Handle simple obfuscations like "name (at) domain . se"
    # (Very basic — expand if you need better coverage)
    obf = re.findall(r"([a-zA-Z0-9._%+\-]+)\s*(?:\(|\[)?at(?:\)|\])?\s*([a-zA-Z0-9.\-]+)\s*(?:\(|\[)?dot(?:\)|\])?\s*([a-zA-Z]{2,})", text, flags=re.I)
    for user, dom, tld in obf:
        emails.add(f"{user}@{dom}.{tld}")

    return sorted(emails), sorted(phones)

def main():
    directory_html = fetch(DIRECTORY_URL)
    member_links = extract_links(directory_html, DIRECTORY_URL)

    # Filter to unique site roots (many links go deep; normalize)
    sites = sorted({normalize_site(u) for u in member_links if normalize_site(u)})
    print(f"Found ~{len(sites)} unique site roots.")

    rows = []
    for i, site in enumerate(sites, 1):
        try:
            html = fetch(site)
            emails, phones = extract_contacts(html)

            # Try a few likely contact pages
            contact_pages = find_candidate_contact_pages(html, site)
            for cp in contact_pages:
                time.sleep(DELAY_S)
                try:
                    cp_html = fetch(cp)
                    e2, p2 = extract_contacts(cp_html)
                    emails = sorted(set(emails) | set(e2))
                    phones = sorted(set(phones) | set(p2))
                except Exception:
                    pass

            rows.append({
                "site": site,
                "emails": "; ".join(emails),
                "phones": "; ".join(phones),
                "contact_pages_checked": "; ".join(contact_pages),
            })
            print(f"[{i}/{len(sites)}] {site} -> {len(emails)} emails, {len(phones)} phones")
        except Exception as e:
            rows.append({
                "site": site,
                "emails": "",
                "phones": "",
                "contact_pages_checked": "",
            })
            print(f"[{i}/{len(sites)}] {site} -> ERROR: {e}")
        time.sleep(DELAY_S)

    with open("sverigestidskrifter_contacts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["site", "emails", "phones", "contact_pages_checked"])
        w.writeheader()
        w.writerows(rows)

    print("Done. Wrote sverigestidskrifter_contacts.csv")

if __name__ == "__main__":
    main()
```

If you want, I can also adapt this to:

* only crawl **the member sites that belong to a specific segment/category** from that page, or
* output **one row per found email/phone** (cleaner for deduping), or
* add **robots.txt checking + concurrency with rate limiting** (faster, safer).

[1]: https://sverigestidskrifter.se/vara-medlemmar/ "Våra medlemmar - Sveriges Tidskrifter"
