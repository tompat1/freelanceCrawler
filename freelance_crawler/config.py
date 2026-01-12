from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CrawlerConfig:
    directory_url: str = "https://sverigestidskrifter.se/vara-medlemmar/"
    contact_hints: tuple[str, ...] = (
        "kontakt",
        "contact",
        "om",
        "about",
        "annonser",
        "editor",
        "redaktion",
    )
    user_agent: str = "ContactFinder/1.0 (+local script)"
    timeout_s: int = 15
    delay_s: float = 1.0
    max_contact_pages: int = 8
    output_csv: str = "sverigestidskrifter_contacts.csv"

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}


@dataclass
class CrawlResult:
    site: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    contact_pages_checked: list[str] = field(default_factory=list)
    error: str | None = None
