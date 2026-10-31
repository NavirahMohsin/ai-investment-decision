from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.services.news.source_registration import (
    activate_news_source,
    register_news_sources,
)
from app.services.news.source_registry import get_all_sources, get_source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register configured news sources without activating them."
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Registry provider key. Repeat to select multiple sources.",
    )
    parser.add_argument(
        "--activate-metadata-only",
        action="store_true",
        help="Explicitly activate selected sources for headline/link metadata only.",
    )
    args = parser.parse_args()
    configs = get_all_sources() if not args.sources else []
    if args.sources:
        for provider_key in args.sources:
            config = get_source(provider_key)
            if config is None:
                raise SystemExit(f"Unknown news source registry key: {provider_key}")
            configs.append(config)
    with SessionLocal() as db:
        if args.activate_metadata_only and not args.sources:
            raise SystemExit(
                "--activate-metadata-only requires at least one --source"
            )
        for config in configs:
            if args.activate_metadata_only:
                result = activate_news_source(
                    db,
                    config,
                    feed_verified=True,
                    attribution_text=config.attribution_text,
                    explicitly_approved=True,
                    allow_metadata_only=True,
                )
            else:
                result = register_news_sources(db, (config,))[0]
            action = "created" if result.created else "updated"
            print(
                f"{result.provider_key}: {action} source_id={result.source_id} "
                f"active={result.is_active}"
            )


if __name__ == "__main__":
    main()
