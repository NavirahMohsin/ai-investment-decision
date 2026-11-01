"""API integration tests for fundamentals endpoints."""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Company, CompanyFinancial, CompanyFundamentalInfo, FundamentalDataUpdateRun
from app.services.fundamentals import IngestionResult


def _add_company(db: Session, symbol: str = "RELIANCE", sector: str = "Energy") -> Company:
    c = Company(
        name=f"{symbol} Industries",
        symbol=symbol,
        provider_symbol=f"{symbol}.NS",
        exchange="NSE",
        sector=sector,
        instrument_type="company",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _seed_basic(db: Session, company: Company) -> None:
    pe = date(2023, 3, 31)
    for name, value, st in [
        ("Total Revenue", Decimal("1000"), "income"),
        ("Net Income", Decimal("200"), "income"),
        ("Gross Profit", Decimal("400"), "income"),
        ("Operating Income", Decimal("300"), "income"),
        ("Basic EPS", Decimal("10"), "income"),
        ("Total Assets", Decimal("2000"), "balance"),
        ("Stockholders Equity", Decimal("800"), "balance"),
        ("Total Debt", Decimal("400"), "balance"),
        ("Current Assets", Decimal("600"), "balance"),
        ("Current Liabilities", Decimal("300"), "balance"),
        ("Operating Cash Flow", Decimal("250"), "cashflow"),
        ("Free Cash Flow", Decimal("180"), "cashflow"),
    ]:
        db.add(
            CompanyFinancial(
                company_id=company.id,
                metric_name=name,
                metric_value=value,
                period_end=pe,
                period_type="annual",
                statement_type=st,
                currency="INR",
                data_source="yahoo_finance",
                retrieved_at=datetime.now(timezone.utc),
            )
        )
    # prior year for growth
    pe2 = date(2022, 3, 31)
    db.add(
        CompanyFinancial(
            company_id=company.id,
            metric_name="Total Revenue",
            metric_value=Decimal("800"),
            period_end=pe2,
            period_type="annual",
            statement_type="income",
            currency="INR",
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        CompanyFundamentalInfo(
            company_id=company.id,
            business_summary="Test company",
            currency="INR",
            market_cap=1_000_000_000,
            data_source="yahoo_finance",
            retrieved_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def test_fundamentals_summary(client: TestClient, db_session: Session):
    company = _add_company(db_session)
    _seed_basic(db_session, company)
    resp = client.get("/api/v1/fundamentals/RELIANCE")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"]["symbol"] == "RELIANCE"
    assert data["highlights"]
    assert data["analysis"]["overall_classification"]
    assert "data_completeness" in data


def test_statements_endpoint(client: TestClient, db_session: Session):
    company = _add_company(db_session)
    _seed_basic(db_session, company)
    resp = client.get(
        "/api/v1/fundamentals/RELIANCE/statements",
        params={"statement_type": "income", "period_type": "annual"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["statement_type"] == "income"
    assert any(line["metric_name"] == "Total Revenue" for line in data["lines"])


def test_ratios_history_analysis_score(client: TestClient, db_session: Session):
    company = _add_company(db_session)
    _seed_basic(db_session, company)
    assert client.get("/api/v1/fundamentals/RELIANCE/ratios").status_code == 200
    hist = client.get("/api/v1/fundamentals/RELIANCE/history")
    assert hist.status_code == 200
    assert hist.json()["revenue"]["metric_key"] == "revenue"
    analysis = client.get("/api/v1/fundamentals/RELIANCE/analysis")
    assert analysis.status_code == 200
    assert "profitability" in analysis.json()
    score = client.get("/api/v1/fundamentals/RELIANCE/score")
    assert score.status_code == 200
    assert "methodology_version" in score.json()


def test_missing_company(client: TestClient):
    assert client.get("/api/v1/fundamentals/NOSUCH").status_code == 404


def test_index_rejected(client: TestClient, db_session: Session):
    db_session.add(
        Company(
            name="NIFTY 50",
            symbol="NIFTY50",
            provider_symbol="^NSEI",
            exchange="NSE",
            instrument_type="benchmark",
        )
    )
    db_session.commit()
    assert client.get("/api/v1/fundamentals/NIFTY50").status_code == 400


def test_compare_endpoint(client: TestClient, db_session: Session):
    a = _add_company(db_session, "AAA", "Technology")
    b = _add_company(db_session, "BBB", "Technology")
    _seed_basic(db_session, a)
    _seed_basic(db_session, b)
    resp = client.get("/api/v1/fundamentals/compare", params=[("symbols", "AAA"), ("symbols", "BBB")])
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["symbols"]) == {"AAA", "BBB"}


def test_compare_invalid(client: TestClient, db_session: Session):
    _add_company(db_session, "AAA")
    resp = client.get("/api/v1/fundamentals/compare", params=[("symbols", "AAA")])
    assert resp.status_code == 400


def test_health_endpoint(client: TestClient, db_session: Session):
    company = _add_company(db_session)
    _seed_basic(db_session, company)
    db_session.add(
        FundamentalDataUpdateRun(
            run_type="all",
            status="completed",
            companies_processed=1,
            successful_count=1,
            failed_count=0,
            trigger_source="manual",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    resp = client.get("/api/v1/fundamentals/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "yahoo_finance"
    assert data["companies"]


def test_dashboard_endpoint(client: TestClient, db_session: Session):
    company = _add_company(db_session)
    _seed_basic(db_session, company)
    resp = client.get("/api/v1/fundamentals/dashboard")
    assert resp.status_code == 200


def test_refresh_validation(client: TestClient):
    resp = client.post("/api/v1/fundamentals/refresh", json={})
    assert resp.status_code == 400


def test_refresh_mocked(client: TestClient, db_session: Session):
    company = _add_company(db_session)

    mock_result: IngestionResult = {
        "company_symbol": company.symbol,
        "success": True,
        "company_info_updated": True,
        "financials_inserted": 3,
        "financials_updated": 0,
        "ratios_inserted": 2,
        "error": None,
    }

    with patch(
        "app.services.fundamentals_refresh.ingest_company_fundamentals",
        return_value=mock_result,
    ), patch(
        "app.services.fundamentals_refresh.YahooFinanceProvider",
        return_value=MagicMock(),
    ):
        resp = client.post(
            "/api/v1/fundamentals/refresh",
            json={"symbols": ["RELIANCE"], "max_companies": 5},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"completed", "partial", "failed"}
    assert data["completed_at"] is not None
    assert data["successful_count"] == 1


def test_empty_financial_data(client: TestClient, db_session: Session):
    _add_company(db_session, "EMPTY")
    resp = client.get("/api/v1/fundamentals/EMPTY/history")
    assert resp.status_code == 200
    assert resp.json()["revenue"]["quality"] == "EMPTY"
