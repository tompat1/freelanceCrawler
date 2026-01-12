from __future__ import annotations

import argparse

from freelance_crawler.config import CrawlerConfig
from freelance_crawler.crawler import run_crawl, write_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl member sites for contact details.")
    parser.add_argument(
        "--directory-url",
        default=CrawlerConfig().directory_url,
        help="Member directory page to start from.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=CrawlerConfig().delay_s,
        help="Delay in seconds between requests.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=CrawlerConfig().timeout_s,
        help="Timeout in seconds for each request.",
    )
    parser.add_argument(
        "--output",
        default=CrawlerConfig().output_csv,
        help="Output CSV path.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = CrawlerConfig(
        directory_url=args.directory_url,
        delay_s=args.delay,
        timeout_s=args.timeout,
        output_csv=args.output,
    )

    results = run_crawl(config)
    write_csv(results, config.output_csv)
    print(f"Done. Wrote {config.output_csv}")


if __name__ == "__main__":
    main()
