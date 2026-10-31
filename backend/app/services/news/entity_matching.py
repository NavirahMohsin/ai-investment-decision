from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyAlias
from app.services.news.entity_normalization import normalize_company_name


SYMBOL_CONFIDENCE = 1.0
NAME_CONFIDENCE = 0.95
ALIAS_CONFIDENCE = 0.85


@dataclass(frozen=True, slots=True)
class CompanyMatch:
    company_id: int | None
    match_method: str | None
    match_confidence: float | None
    matched_text: str | None
    candidate_company_ids: tuple[int, ...] = ()
    is_ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class _Occurrence:
    start: int
    end: int
    match: CompanyMatch


def match_company(db: Session, value: str) -> CompanyMatch:
    normalized = normalize_company_name(value)
    if not normalized:
        return _no_match()
    companies = list(
        db.scalars(select(Company).where(Company.is_active.is_(True)))
    )
    symbol_matches = [
        company for company in companies
        if normalize_company_name(company.symbol) == normalized
    ]
    if len(symbol_matches) == 1:
        return _match(symbol_matches[0], "exact_symbol", SYMBOL_CONFIDENCE, value)
    if len(symbol_matches) > 1:
        return _ambiguous(symbol_matches)

    name_matches = [
        company for company in companies
        if normalize_company_name(company.name) == normalized
    ]
    if len(name_matches) == 1:
        return _match(name_matches[0], "exact_name", NAME_CONFIDENCE, value)
    if len(name_matches) > 1:
        return _ambiguous(name_matches)

    aliases = list(
        db.scalars(
            select(CompanyAlias).where(
                CompanyAlias.normalized_alias == normalized,
                CompanyAlias.is_active.is_(True),
            )
        )
    )
    if len(aliases) == 1:
        company = db.get(Company, aliases[0].company_id)
        if company is not None and company.is_active:
            return _match(company, "alias", ALIAS_CONFIDENCE, value)
    if aliases:
        return CompanyMatch(
            company_id=None,
            match_method="alias",
            match_confidence=None,
            matched_text=value,
            candidate_company_ids=tuple(sorted({a.company_id for a in aliases})),
            is_ambiguous=True,
        )
    return _no_match()


def match_article_companies(
    db: Session,
    headline: str | None,
    summary: str | None,
) -> tuple[CompanyMatch, ...]:
    companies = list(
        db.scalars(select(Company).where(Company.is_active.is_(True)))
    )
    aliases = list(
        db.scalars(
            select(CompanyAlias).where(CompanyAlias.is_active.is_(True))
        )
    )
    term_candidates: dict[str, dict[str, set[int]]] = {}
    for company in companies:
        term_candidates.setdefault(normalize_company_name(company.symbol), {}).setdefault(
            "exact_symbol", set()
        ).add(company.id)
        term_candidates.setdefault(normalize_company_name(company.name), {}).setdefault(
            "exact_name", set()
        ).add(company.id)
    for alias in aliases:
        term_candidates.setdefault(alias.normalized_alias, {}).setdefault(
            "alias", set()
        ).add(alias.company_id)
    occurrences: list[_Occurrence] = []
    for text in (headline, summary):
        if not text:
            continue
        normalized_text, mapping = _normalized_text_with_mapping(text)
        for term, methods in term_candidates.items():
            if not term:
                continue
            method = max(
                methods,
                key=lambda value: {"exact_symbol": 3, "exact_name": 2, "alias": 1}[value],
            )
            confidence = {
                "exact_symbol": SYMBOL_CONFIDENCE,
                "exact_name": NAME_CONFIDENCE,
                "alias": ALIAS_CONFIDENCE,
            }[method]
            candidates = tuple(sorted(methods[method]))
            pattern = _term_pattern(term)
            for found in re.finditer(pattern, normalized_text):
                matched = text[mapping[found.start()]:mapping[found.end() - 1] + 1]
                ambiguous = len(candidates) > 1
                occurrences.append(_Occurrence(
                    found.start(),
                    found.end(),
                    CompanyMatch(
                        company_id=None if ambiguous else candidates[0],
                        match_method=method,
                        match_confidence=None if ambiguous else confidence,
                        matched_text=matched,
                        candidate_company_ids=candidates,
                        is_ambiguous=ambiguous,
                    ),
                ))
    selected: list[_Occurrence] = []
    for occurrence in sorted(
        occurrences,
        key=lambda item: (
            item.start,
            -(item.end - item.start),
            -(item.match.match_confidence or 0),
        ),
    ):
        if any(
            occurrence.start < existing.end and existing.start < occurrence.end
            for existing in selected
        ):
            continue
        selected.append(occurrence)

    results: list[CompanyMatch] = []
    for occurrence in selected:
        match = occurrence.match
        if match.company_id is not None and any(
            result.company_id == match.company_id for result in results
        ):
            continue
        results.append(match)
    return tuple(results)


def _normalized_text_with_mapping(value: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    mapping: list[int] = []
    for index, character in enumerate(value):
        normalized = unicodedata.normalize("NFKC", character).casefold()
        if re.match(r"[^\w\s]", normalized, flags=re.UNICODE):
            normalized = " "
        for output in normalized:
            chars.append(output)
            mapping.append(index)
    collapsed_chars: list[str] = []
    collapsed_mapping: list[int] = []
    previous_space = False
    for character, index in zip(chars, mapping):
        is_space = character.isspace()
        if is_space and previous_space:
            continue
        collapsed_chars.append(" " if is_space else character)
        collapsed_mapping.append(index)
        previous_space = is_space
    while collapsed_chars and collapsed_chars[0] == " ":
        collapsed_chars.pop(0)
        collapsed_mapping.pop(0)
    while collapsed_chars and collapsed_chars[-1] == " ":
        collapsed_chars.pop()
        collapsed_mapping.pop()
    return "".join(collapsed_chars), collapsed_mapping


def _term_pattern(term: str) -> str:
    return r"(?<!\w)" + r"\s+".join(re.escape(part) for part in term.split()) + r"(?!\w)"


def _match(company: Company, method: str, confidence: float, value: str) -> CompanyMatch:
    return CompanyMatch(company.id, method, confidence, value, (company.id,), False)


def _ambiguous(companies: list[Company]) -> CompanyMatch:
    ids = tuple(sorted(company.id for company in companies))
    return CompanyMatch(None, "ambiguous", None, None, ids, True)


def _no_match() -> CompanyMatch:
    return CompanyMatch(None, None, None, None)
