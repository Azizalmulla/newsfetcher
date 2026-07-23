"""CLI: python -m app.db.run_assessments"""

from __future__ import annotations

import json
import logging

from app.db.session import SessionLocal
from app.services.source_assessment import run_assessments, shortlist_technically_ready


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        summaries = run_assessments(db, write_docs=True)
        shortlist = shortlist_technically_ready(summaries, limit=4)
        print(
            json.dumps(
                {"assessed": len(summaries), "shortlist": shortlist},
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
