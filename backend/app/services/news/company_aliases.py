from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyAlias
from app.services.news.entity_normalization import normalize_company_name


class CompanyAliasError(ValueError):
    """Base error for explicit company-alias management."""


class CompanyNotFoundError(CompanyAliasError):
    pass


class EmptyCompanyAliasError(CompanyAliasError):
    pass


def add_company_alias(
    db: Session,
    company_id: int,
    alias: str,
    *,
    alias_type: str = "manual",
) -> CompanyAlias:
    if not alias or not alias.strip():
        raise EmptyCompanyAliasError("Company alias must not be empty")
    company = db.get(Company, company_id)
    if company is None:
        raise CompanyNotFoundError(f"Company does not exist: {company_id}")
    normalized_alias = normalize_company_name(alias)
    if not normalized_alias:
        raise EmptyCompanyAliasError("Company alias must contain a name")
    existing = db.scalar(
        select(CompanyAlias).where(
            CompanyAlias.company_id == company_id,
            CompanyAlias.normalized_alias == normalized_alias,
        )
    )
    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
        return existing
    result = CompanyAlias(
        company_id=company_id,
        alias=alias.strip(),
        normalized_alias=normalized_alias,
        alias_type=alias_type,
        is_active=True,
    )
    db.add(result)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise CompanyAliasError("Company alias could not be added") from error
    db.refresh(result)
    return result


def get_active_company_aliases(
    db: Session,
    company_id: int,
) -> list[CompanyAlias]:
    if db.get(Company, company_id) is None:
        raise CompanyNotFoundError(f"Company does not exist: {company_id}")
    return list(
        db.scalars(
            select(CompanyAlias).where(
                CompanyAlias.company_id == company_id,
                CompanyAlias.is_active.is_(True),
            ).order_by(CompanyAlias.id)
        )
    )


def deactivate_company_alias(db: Session, alias_id: int) -> CompanyAlias:
    alias = db.get(CompanyAlias, alias_id)
    if alias is None:
        raise CompanyAliasError(f"Company alias does not exist: {alias_id}")
    alias.is_active = False
    db.commit()
    db.refresh(alias)
    return alias


add_alias = add_company_alias
get_active_aliases = get_active_company_aliases
deactivate_alias = deactivate_company_alias
