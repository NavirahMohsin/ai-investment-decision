from dataclasses import replace

import pytest
from sqlalchemy import select

from app.db.models import NewsSource
from app.services.news import (
    ContentPolicyStatus,
    NewsSourceActivationError,
    activate_news_source,
    get_source,
    register_news_source,
)


def test_registration_is_idempotent_and_does_not_reactivate(db_session):
    config = get_source("rbi_press_releases")
    assert config is not None

    first = register_news_source(db_session, config)
    second = register_news_source(db_session, config)

    assert first.created is True
    assert second.created is False
    assert first.source_id == second.source_id
    assert second.is_active is False
    assert db_session.scalar(select(NewsSource).where(NewsSource.provider_key == config.provider_key)) is not None

    source = db_session.get(NewsSource, first.source_id)
    assert source is not None
    source.is_active = True
    db_session.commit()
    refreshed = register_news_source(db_session, config)
    assert refreshed.is_active is True


@pytest.mark.parametrize(
    "changes,kwargs",
    [
        ({"is_enabled": False}, {"feed_verified": True, "attribution_text": "RBI", "explicitly_approved": True}),
        ({"content_policy_status": ContentPolicyStatus.PENDING_REVIEW}, {"feed_verified": True, "attribution_text": "RBI", "explicitly_approved": True}),
        ({"content_policy_status": ContentPolicyStatus.APPROVED_CONTENT_STORAGE}, {"feed_verified": False, "attribution_text": "RBI", "explicitly_approved": True}),
        ({"content_policy_status": ContentPolicyStatus.APPROVED_CONTENT_STORAGE}, {"feed_verified": True, "attribution_text": None, "explicitly_approved": True}),
        ({"content_policy_status": ContentPolicyStatus.APPROVED_CONTENT_STORAGE}, {"feed_verified": True, "attribution_text": "RBI", "explicitly_approved": False}),
    ],
)
def test_activation_requires_every_explicit_safety_condition(
    db_session,
    changes,
    kwargs,
):
    config = get_source("rbi_press_releases")
    assert config is not None
    candidate = replace(config, **changes)

    with pytest.raises(NewsSourceActivationError):
        activate_news_source(db_session, candidate, **kwargs)


def test_activation_requires_content_storage_policy(db_session):
    config = get_source("rbi_press_releases")
    assert config is not None
    candidate = replace(
        config,
        is_enabled=True,
        content_policy_status=ContentPolicyStatus.APPROVED_METADATA_ONLY,
    )

    with pytest.raises(NewsSourceActivationError):
        activate_news_source(
            db_session,
            candidate,
            feed_verified=True,
            attribution_text="RBI",
            explicitly_approved=True,
        )


def test_activation_can_explicitly_approve_metadata_only_source(db_session):
    config = get_source("economic_times_markets")
    assert config is not None

    result = activate_news_source(
    db_session,
    config,
    feed_verified=True,
    attribution_text=config.attribution_text,
    explicitly_approved=True,
    allow_metadata_only=True,
    )

    assert result.is_active is True
