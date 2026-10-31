from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class NewsSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider_key: str = Field(min_length=1, max_length=100)
    source_type: str = Field(min_length=1, max_length=30)
    base_url: str | None = Field(default=None, max_length=500)
    feed_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class NewsSourceRead(NewsSourceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class NewsArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    external_id: str | None
    canonical_url: str
    url_hash: str
    headline: str
    summary: str | None
    author: str | None
    published_at: datetime | None
    discovered_at: datetime
    language: str | None
    content_hash: str | None
    created_at: datetime
    updated_at: datetime


class CompanyAliasCreate(BaseModel):
    company_id: int
    alias: str = Field(min_length=1, max_length=255)
    normalized_alias: str = Field(min_length=1, max_length=255)
    alias_type: str = Field(min_length=1, max_length=30)
    is_active: bool = True


class CompanyAliasRead(CompanyAliasCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class NewsIngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    articles_discovered: int
    articles_inserted: int
    articles_updated: int
    articles_skipped: int
    error_message: str | None
    created_at: datetime


class PaginationMetadata(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class NewsCompanyMatchRead(BaseModel):
    company_id: int
    symbol: str
    name: str
    match_method: str
    match_confidence: Decimal | None
    matched_text: str | None


class NewsArticleListItem(BaseModel):
    id: int
    source_id: int
    source_provider_key: str
    source_name: str
    external_id: str | None
    canonical_url: str
    headline: str
    summary: str | None
    author: str | None
    published_at: datetime | None
    discovered_at: datetime
    language: str | None
    companies: list[NewsCompanyMatchRead] = Field(default_factory=list)


class NewsArticleDetailRead(NewsArticleListItem):
    url_hash: str
    content_hash: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedNewsArticles(BaseModel):
    items: list[NewsArticleListItem]
    pagination: PaginationMetadata


class NewsSourceReadSafe(BaseModel):
    id: int
    name: str
    provider_key: str
    source_type: str
    is_active: bool
    last_success_at: datetime | None
    last_error: str | None


class NewsIngestionRunReadSafe(BaseModel):
    id: int
    source_id: int | None
    source_provider_key: str | None
    source_name: str | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    articles_discovered: int
    articles_inserted: int
    articles_skipped: int
    error_message: str | None


class PaginatedNewsIngestionRuns(BaseModel):
    items: list[NewsIngestionRunReadSafe]
    pagination: PaginationMetadata


class NewsIngestionTriggerResponse(BaseModel):
    run_id: int
    source_key: str
    source_name: str
    status: str
    discovered_count: int
    inserted_count: int
    skipped_count: int
    failed_count: int
    started_at: datetime
    completed_at: datetime | None
    message: str
