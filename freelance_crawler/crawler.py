from __future__ import annotations

import csv
import re
import time
from dataclasses import asdict
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from freelance_crawler.config import CrawlResult, CrawlerConfig

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s().\-]{6,}\d)")
OBFUSCATED_RE = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*(?:\(|\[)?at(?:\)|\])?\s*"
    r"([a-zA-Z0-9.\-]+)\s*(?:\(|\[)?dot(?:\)|\])?\s*([a-zA-Z]{2,})",
    flags=re.IGNORECASE,
)


def fetch(url: str, config: CrawlerConfig) -> str:
    response = requests.get(url, headers=config.headers, timeout=config.timeout_s)
    response.raise_for_status()
    return response.text


def extract_links(html: str, base_url: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        if href.startswith("http://") or href.startswith("https://"):
            links.add(href)
        else:
            links.add(urljoin(base_url, href))
    return links


def normalize_site(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def find_candidate_contact_pages(
    html: str,
    base_url: str,
    config: CrawlerConfig,
) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        text = (anchor.get_text() or "").lower()
        target = (href or "").lower()
        if any(hint in text or hint in target for hint in config.contact_hints):
            candidates.append(urljoin(base_url, href))
    deduped: list[str] = []
    seen = set()
    for url in candidates:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped[: config.max_contact_pages]


def extract_contacts(text: str) -> tuple[list[str], list[str]]:
    emails = set(EMAIL_RE.findall(text))
    phones = set(match.strip() for match in PHONE_RE.findall(text))

    for user, domain, tld in OBFUSCATED_RE.findall(text):
        emails.add(f"{user}@{domain}.{tld}")

    return sorted(emails), sorted(phones)


def crawl_site(site: str, config: CrawlerConfig) -> CrawlResult:
    html = fetch(site, config)
    emails, phones = extract_contacts(html)
    contact_pages = find_candidate_contact_pages(html, site, config)

    for contact_page in contact_pages:
        time.sleep(config.delay_s)
        try:
            contact_html = fetch(contact_page, config)
        except requests.RequestException:
            continue
        more_emails, more_phones = extract_contacts(contact_html)
        emails = sorted(set(emails) | set(more_emails))
        phones = sorted(set(phones) | set(more_phones))

    return CrawlResult(
        site=site,
        emails=emails,
        phones=phones,
        contact_pages_checked=contact_pages,
    )


def collect_sites(directory_url: str, config: CrawlerConfig) -> list[str]:
    directory_html = fetch(directory_url, config)
    member_links = extract_links(directory_html, directory_url)
    sites = sorted({normalize_site(link) for link in member_links if normalize_site(link)})
    return [site for site in sites if site is not None]


def run_crawl(
    config: CrawlerConfig,
    progress_callback: Callable[[int, int, CrawlResult], None] | None = None,
) -> list[CrawlResult]:
    sites = collect_sites(config.directory_url, config)
    results: list[CrawlResult] = []
    for index, site in enumerate(sites, start=1):
        try:
            result = crawl_site(site, config)
            results.append(result)
            print(
                f"[{index}/{len(sites)}] {site} -> {len(result.emails)} emails, "
                f"{len(result.phones)} phones",
            )
        except requests.RequestException as exc:
            results.append(
                CrawlResult(
                    site=site,
                    error=str(exc),
                ),
            )
            print(f"[{index}/{len(sites)}] {site} -> ERROR: {exc}")
        if progress_callback:
            progress_callback(index, len(sites), results[-1])
        time.sleep(config.delay_s)
    return results


def write_csv(results: Iterable[CrawlResult], output_csv: str) -> None:
    fieldnames = ["site", "emails", "phones", "contact_pages_checked", "error"]
    with open(output_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            row["emails"] = "; ".join(result.emails)
            row["phones"] = "; ".join(result.phones)
            row["contact_pages_checked"] = "; ".join(result.contact_pages_checked)
            writer.writerow(row)
