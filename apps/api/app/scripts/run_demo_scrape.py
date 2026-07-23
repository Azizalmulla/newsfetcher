"""CLI: enable web gates and scrape last N days.

Usage (inside API container):
  uv run python -m app.scripts.run_demo_scrape --lookback-days 5
"""

from __future__ import annotations

import argparse
import json
import logging

from app.db.session import SessionLocal
from app.services.ingestion_pipeline import run_lookback_ingest
from app.services.source_closure import apply_source_closure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo_scrape")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo scrape last N days of web sources")
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--fetch-limit", type=int, default=800)
    parser.add_argument("--skip-enable", action="store_true")
    parser.add_argument("--skip-closure-apply", action="store_true")
    parser.add_argument("--exclude-broken", action="store_true")
    parser.add_argument(
        "--purge-articles",
        action="store_true",
        help="Delete existing articles before scrape (demo reset).",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.purge_articles:
            from sqlalchemy import text

            db.execute(text("DELETE FROM article_versions"))
            db.execute(text("DELETE FROM story_cluster_members"))
            db.execute(text("DELETE FROM articles"))
            db.commit()
            logger.info("purged existing articles")
        if not args.skip_closure_apply:
            closure = apply_source_closure(db, actor_id="demo_scrape_cli")
            logger.info(
                "closure applied=%s enabled_connectors=%s",
                closure.get("applied"),
                closure.get("enabled_connectors"),
            )
        result = run_lookback_ingest(
            db,
            lookback_days=args.lookback_days,
            fetch_limit=args.fetch_limit,
            actor_id="ingest_cli",
            include_temporarily_broken=not args.exclude_broken,
            enable_first=not args.skip_enable,
            use_browser_fallback=True,
        )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
