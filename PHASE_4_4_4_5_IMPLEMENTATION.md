# Phase 4.4 & 4.5: Company Research Assistant + AI Explanations

## Overview

Phase 4.4 and 4.5 add two critical capabilities:
1. **Company Research Assistant** - Comprehensive analysis and reports
2. **AI Explanations** - Interpretability for all model outputs

These work together to make ArthAI a complete research platform.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Request                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Company Research Assistant (4.4)             │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │ • Generate company overview                    │  │   │
│  │  │ • Financial performance analysis               │  │   │
│  │  │ • Annual report summary                        │  │   │
│  │  │ • SWOT analysis                                │  │   │
│  │  │ • Peer comparison                              │  │   │
│  │  │ • Structured research report                   │  │   │
│  │  │ • Save for future reference                    │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                           ↓                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │        AI Explanations Layer (4.5)                   │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │ • Explain ML predictions                       │  │   │
│  │  │ • Explain technical signals                    │  │   │
│  │  │ • Explain fundamental scores                   │  │   │
│  │  │ • Explain news sentiment                       │  │   │
│  │  │ • Communicate uncertainty & limitations        │  │   │
│  │  └────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                    LLM Service (Gemini/Groq)                │
│  + Data Integration (Markets, Fundamentals, News)           │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 4.4: Company Research Assistant

### Capability 1: Generate Company Overview

**Input:**
```python
{
  "ticker": "TCS",
  "include_history": true,  # 5-year context
  "language": "simple"      # Complexity level
}
```

**Output:**
```markdown
# TCS (Tata Consultancy Services) - Company Overview

## At a Glance
- **Market Cap:** ₹15.2 Lakh Crore
- **Sector:** Information Technology
- **Employees:** 614,000
- **Founded:** 1968
- **HQ:** Mumbai, India

## Business Model
TCS is one of India's largest IT services companies, providing...

## Key Services
- IT Services & Consulting (68% revenue)
- Business Process Outsourcing (22% revenue)
- Cyber Security (10% revenue)

## Recent Performance
- FY2023 Revenue: ₹2,50,000 Cr (↑ 15.2% YoY)
- Net Profit: ₹42,500 Cr (↑ 12.1% YoY)
- Operating Margin: 17.2% (stable)

## Market Position
- Ranked #1 in Indian IT sector
- Consistent dividend payer
- Strong cash position
```

**Implementation:**
```python
# backend/app/services/research_assistant.py

class CompanyResearchAssistant:
    def generate_company_overview(
        self,
        ticker: str,
        include_history: bool = True,
        language: str = "simple"
    ) -> str:
        """Generate executive summary of a company."""
        
        # 1. Fetch company data
        company = self.get_company_data(ticker)
        fundamentals = self.get_fundamentals(ticker)
        performance = self.get_performance_metrics(ticker)
        
        # 2. Build context
        context = {
            "company_name": company.name,
            "ticker": ticker,
            "sector": company.sector,
            "market_cap": fundamentals.market_cap,
            "revenue_5y": performance.revenue_5y,
            "net_profit_5y": performance.net_profit_5y,
            "employees": company.employees,
            "founded": company.founded,
            "about": company.description,
        }
        
        # 3. Generate with LLM
        prompt = f"""
Create a company overview for {company.name} ({ticker}).

Company Data:
{json.dumps(context, indent=2, default=str)}

Guidelines:
- Use "{language}" language (simple/technical)
- Include 5-year trends if available
- Format as markdown with clear sections
- Keep it concise (500-800 words)
- Use Indian rupee (₹) for currency
"""
        
        response = self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are a financial analyst. Create clear, accurate company overviews.",
            temperature=0.5,  # Conservative
            max_tokens=1500,
        )
        
        return response.content
```

### Capability 2: Financial Performance Analysis

**Input:**
```python
{
  "ticker": "TCS",
  "metrics": ["revenue", "profitability", "cash_flow"],
  "period": "5Y"  # 1Y, 3Y, 5Y
}
```

**Output:**
```markdown
# TCS - Financial Performance Analysis (5-Year)

## Revenue Trajectory
| Year   | Revenue (₹ Cr) | YoY Growth | Trend |
|--------|----------------|-----------|-------|
| 2019   | 1,92,000       | -         | —     |
| 2020   | 2,01,000       | +4.7%     | ↑     |
| 2021   | 2,22,000       | +10.4%    | ↑     |
| 2022   | 2,38,000       | +7.2%     | ↑     |
| 2023   | 2,50,000       | +5.0%     | ↑     |

**Analysis:**
- Consistent growth over 5 years (CAGR: 6.9%)
- FY2021 showed strong acceleration (+10.4%)
- Growth moderating in recent years (expected in mature sector)
- COVID impact minimal in 2020-21

## Profitability Metrics
- **Net Profit Margin:** 17.0% (FY2023) - Stable
- **Operating Margin:** 17.2% (FY2023) - Strong
- **ROE:** 32.5% (FY2023) - Excellent
- **ROA:** 12.1% (FY2023) - Good

**Interpretation:**
- Strong margins indicate pricing power
- High ROE shows efficient capital usage
- Margins stable despite revenue deceleration

## Cash Flow Health
- **Operating Cash Flow:** ₹50,000 Cr (FY2023) ✓ Strong
- **Free Cash Flow:** ₹45,000 Cr (FY2023) ✓ Excellent
- **Capex as % Revenue:** 1.2% (FY2023) - Low
- **Dividend Payout:** ₹15,000 Cr (FY2023) - Generous

**Key Takeaways:**
1. Company converts profits to cash efficiently
2. Low capex needs (asset-light model)
3. Can sustain high dividend payouts
4. Strong financial health
```

**Implementation:**
```python
def analyze_financial_performance(
    self,
    ticker: str,
    metrics: List[str],
    period: str = "5Y"
) -> str:
    """Analyze and explain financial performance."""
    
    # 1. Get historical data
    financials = self.get_financial_history(ticker, years=5)
    
    # 2. Calculate metrics
    analysis = {
        "revenue_growth": self.calculate_growth_rates(financials),
        "profitability": self.calculate_profitability(financials),
        "cash_flow": self.calculate_cash_flow(financials),
        "efficiency": self.calculate_efficiency_ratios(financials),
    }
    
    # 3. Build tables and insights
    tables = self.format_as_tables(analysis)
    insights = self.generate_insights(analysis)
    
    # 4. Generate explanation with LLM
    prompt = f"""
Analyze the financial performance of {ticker}.

Historical Data (5-Year):
{tables}

Calculated Metrics:
{json.dumps(analysis, indent=2, default=str)}

Insights Generated:
{insights}

Guidelines:
- Explain trends in simple language
- Highlight positive and concerning trends
- Compare to industry benchmarks if possible
- Suggest what the metrics mean for investors
- Format as markdown with sections
"""
    
    response = self.llm_service.generate(
        prompt=prompt,
        system_prompt="You are a financial analyst. Explain financial metrics clearly.",
        temperature=0.5,
        max_tokens=2000,
    )
    
    return response.content
```

### Capability 3: Summarize Annual Reports

**Input:**
```python
{
  "ticker": "TCS",
  "report_type": "annual",  # annual, quarterly
  "fiscal_year": 2023,
  "include_md_and_a": True,
}
```

**Output:**
```markdown
# TCS - FY2023 Annual Report Summary

## Executive Summary
TCS delivered strong operational performance in FY2023 with revenue 
reaching ₹2,50,000 crore, representing 5% YoY growth...

## Key Highlights
✓ **Revenue:** ₹2,50,000 Cr (+5.0% YoY)
✓ **Net Profit:** ₹42,500 Cr (+12.1% YoY)
✓ **Margins:** 17.2% (improved from 16.8%)
✓ **Client Base:** Added 47 new logos
✓ **Attrition Rate:** 16.2% (improved from 18.5%)

## Business Performance by Segment
1. **IT Services (68% of revenue)** - ₹1,70,000 Cr
   - Growth: +8.2%
   - Key driver: Digital transformation services
   
2. **BPO (22% of revenue)** - ₹55,000 Cr
   - Growth: +1.5%
   - Facing headwinds in certain client segments

3. **Cyber Security (10% of revenue)** - ₹25,000 Cr
   - Growth: +18.3%
   - High growth segment

## Management Discussion & Analysis (MD&A)
### Market Opportunities
- Digital transformation: $2 Trillion TAM
- Cloud migration: Ongoing opportunity
- AI/ML: Emerging high-margin service

### Challenges
- Client spending caution in developed markets
- Currency headwinds (INR strengthening)
- Talent acquisition and retention costs

### Strategy Going Forward
- Focus on high-margin digital services
- Expand AI/ML capabilities
- Client account consolidation

## Financial Position
- **Cash & Equivalents:** ₹18,500 Cr (strong)
- **Debt:** ₹5,000 Cr (manageable)
- **Dividend:** ₹32 per share (increased 10% YoY)

## Risk Factors
⚠ **Market Risk:** Client spending slowdown
⚠ **Talent Risk:** High attrition in competitive market
⚠ **Currency Risk:** INR strength impacts USD revenues

## Outlook
Management guidance:
- FY2024 Revenue Growth: 3-7% (in constant currency)
- Margins expected stable to slightly improve
- Continued focus on AI and digital services
```

**Implementation:**
```python
def summarize_annual_report(
    self,
    ticker: str,
    report_type: str = "annual",
    fiscal_year: int = None,
    include_md_and_a: bool = True,
) -> str:
    """Generate structured summary of annual/quarterly report."""
    
    # Note: This will work better with RAG (Phase 4.3)
    # For now, use available data + LLM generation
    
    # 1. Get available report data
    report_data = self.get_report_data(ticker, report_type, fiscal_year)
    
    # 2. Get financial metrics from the period
    financials = self.get_financials_for_period(ticker, fiscal_year)
    
    # 3. Get company announcements for the year
    announcements = self.get_announcements(ticker, fiscal_year)
    
    # 4. Fetch MD&A if using RAG (retrieve from document)
    md_and_a_content = ""
    if include_md_and_a:
        # TODO: Implement with RAG
        pass
    
    # 5. Build comprehensive context
    context = {
        "company": report_data.get("company_name"),
        "ticker": ticker,
        "period": f"FY{fiscal_year}",
        "financial_summary": financials.summary,
        "revenue": financials.revenue,
        "net_profit": financials.net_profit,
        "announcements": announcements,
        "md_and_a": md_and_a_content,
    }
    
    # 6. Generate summary with LLM
    prompt = f"""
Generate a structured annual report summary for {ticker}.

Report Data:
{json.dumps(context, indent=2, default=str)}

Structure:
1. Executive Summary
2. Key Highlights (use ✓ and ⚠ symbols)
3. Business Performance by Segment
4. MD&A Highlights (opportunities, challenges, strategy)
5. Financial Position
6. Risk Factors
7. Outlook & Guidance

Guidelines:
- Use markdown formatting
- Include actual numbers from provided data
- Highlight key metrics
- Use structured sections
- Keep professional tone
"""
    
    response = self.llm_service.generate(
        prompt=prompt,
        system_prompt="You are a financial analyst. Create clear, structured report summaries.",
        temperature=0.5,
        max_tokens=3000,
    )
    
    return response.content
```

### Capability 4: SWOT Analysis

**Input:**
```python
{
  "ticker": "TCS",
  "include_market_data": True,
}
```

**Output:**
```markdown
# TCS - SWOT Analysis

## Strengths ✓
1. **Market Leadership** - #1 position in Indian IT sector
   - Revenue: ₹2,50,000 Cr (largest IT services company)
   - Brand recognition globally
   
2. **Strong Financial Position**
   - Operating Margin: 17.2% (healthy)
   - ROE: 32.5% (excellent capital efficiency)
   - Free Cash Flow: ₹45,000 Cr (strong)
   
3. **Diversified Client Base**
   - Clients across 50+ countries
   - No single client > 8% of revenue
   - Exposure to various industries
   
4. **Talent Bench**
   - 614,000 employees globally
   - Strong delivery capabilities
   - Continuous reskilling programs

5. **Digital Capabilities**
   - Growing AI/ML services (18%+ growth)
   - Cloud migration expertise
   - Cybersecurity offerings

## Weaknesses ⚠
1. **Margin Compression Risk**
   - High attrition costs (16.2%)
   - Wage inflation in talent markets
   - Could pressure margins going forward

2. **Slowing Growth**
   - FY2023 growth: 5% (down from 10%+ in FY2021)
   - Mature market dynamics
   - Client spending cautious

3. **Client Concentration**
   - Top 20 clients = 45% of revenue
   - Loss of major client would impact growth
   
4. **Currency Risk**
   - 60% revenue in USD
   - Strong INR impacts reported results
   - Hedging costs increase in volatile markets

5. **Legacy Services Decline**
   - Traditional IT services facing pricing pressure
   - Transition to high-margin services ongoing

## Opportunities 🚀
1. **AI & Automation** (TAM: $2+ Trillion)
   - AI services still nascent for TCS
   - High-margin opportunity
   - Significant market tailwinds

2. **Cloud Migration** (Multi-year runway)
   - Enterprise cloud adoption ongoing
   - TCS well-positioned with expertise
   - Strong growth segment

3. **Emerging Markets**
   - Penetration in India still low
   - APAC growth opportunity
   - Lower cost advantage

4. **Vertical Expansion**
   - Healthcare, retail, manufacturing growth
   - Industry-specific solutions premium-priced
   
5. **Consulting Services**
   - Strategy consulting expanding
   - Higher margins than traditional services

## Threats ⚠️
1. **Global Economic Slowdown**
   - Client spending could reduce further
   - Leads to project delays/cancellations
   - Revenue growth pressure

2. **Intense Competition**
   - Accenture, Infosys, Wipro competing for same deals
   - Price competition increasing
   - Margin pressure

3. **Tech Disruption**
   - New entrants with AI-native platforms
   - Low-code/no-code platforms reducing demand
   - Obsolescence risk in traditional services

4. **Geopolitical Risks**
   - US visa restrictions affecting delivery
   - India-Western relations uncertainty
   - Data sovereignty requirements

5. **Regulatory Changes**
   - Labor regulations increasing costs
   - Data protection regulations stricter
   - Tax policy changes

## SWOT Summary
| Factor | Assessment | Implication |
|--------|------------|-------------|
| Overall Strength | 8/10 | Market leader, strong financials |
| Growth Potential | 6/10 | Growth slowing, needs innovation |
| Risk Level | 5/10 | Moderate risks, well-managed |
| Investment Appeal | 7/10 | Stable, defensive stock |

## Strategic Recommendations
1. **Accelerate AI/ML Services** - Leverage strength in digital
2. **Expand Consulting** - Move up the value chain
3. **Talent Retention** - Invest in culture to reduce attrition
4. **M&A Strategy** - Acquire AI/consulting capabilities
5. **Geographic Expansion** - Grow in APAC, especially India
```

**Implementation:**
```python
def generate_swot_analysis(
    self,
    ticker: str,
    include_market_data: bool = True,
) -> str:
    """Generate SWOT analysis based on company data."""
    
    # 1. Gather company data
    company = self.get_company_data(ticker)
    financials = self.get_fundamentals(ticker)
    competitors = self.get_competitors(ticker)
    market_trends = self.get_market_trends(ticker) if include_market_data else None
    
    # 2. Analyze each dimension
    context = {
        "company_name": company.name,
        "ticker": ticker,
        "sector": company.sector,
        "financial_health": {
            "margin": financials.operating_margin,
            "roe": financials.roe,
            "cash_flow": financials.free_cash_flow,
        },
        "market_position": {
            "rank": company.market_rank,
            "market_cap": company.market_cap,
            "competitors": [c.name for c in competitors[:5]],
        },
        "trends": market_trends,
    }
    
    # 3. Generate SWOT with LLM
    prompt = f"""
Create a comprehensive SWOT analysis for {company.name} ({ticker}).

Company Context:
{json.dumps(context, indent=2, default=str)}

Structure:
1. Strengths (✓ symbol, 5 points)
2. Weaknesses (⚠ symbol, 5 points)
3. Opportunities (🚀 symbol, 5 points)
4. Threats (⚠️ symbol, 5 points)
5. SWOT Summary Table
6. Strategic Recommendations

Guidelines:
- Be specific and data-driven
- Use quantitative data where available
- Keep professional tone
- Format as markdown
- Each point should have brief explanation
"""
    
    response = self.llm_service.generate(
        prompt=prompt,
        system_prompt="You are a business analyst. Create insightful SWOT analysis.",
        temperature=0.6,  # Slightly creative
        max_tokens=2500,
    )
    
    return response.content
```

### Capability 5: Compare Companies Using Actual Data

**Input:**
```python
{
  "tickers": ["TCS", "INFY", "WIPRO"],
  "metrics": ["revenue", "profitability", "growth", "valuation"],
  "period": "FY2023"
}
```

**Output:**
```markdown
# IT Services Sector Comparison: TCS vs Infosys vs Wipro

## Financial Metrics (FY2023)

### Scale & Growth
| Metric | TCS | INFY | WIPRO | Leader |
|--------|-----|------|-------|--------|
| Revenue (₹ Cr) | 2,50,000 | 2,31,300 | 1,05,100 | TCS |
| YoY Growth | +5.0% | +2.0% | -0.5% | TCS |
| Net Profit (₹ Cr) | 42,500 | 38,200 | 16,100 | TCS |
| Profit Growth | +12.1% | +4.2% | -8.5% | TCS |

### Profitability & Efficiency
| Metric | TCS | INFY | WIPRO | Best |
|--------|-----|------|-------|------|
| Operating Margin | 17.2% | 16.8% | 14.2% | TCS |
| Net Margin | 17.0% | 16.5% | 15.3% | TCS |
| ROE | 32.5% | 30.1% | 26.8% | TCS |
| Asset Turnover | 0.71x | 0.68x | 0.65x | TCS |

### Valuation Metrics
| Metric | TCS | INFY | WIPRO | Assessment |
|--------|-----|------|-------|------------|
| P/E Ratio | 24.5x | 23.2x | 18.5x | WIPRO cheapest |
| P/B Ratio | 8.2x | 7.5x | 5.8x | WIPRO attractive |
| Price/Sales | 6.1x | 5.9x | 4.8x | WIPRO lowest |
| Dividend Yield | 2.8% | 2.5% | 3.2% | WIPRO highest |

### Balance Sheet Strength
| Metric | TCS | INFY | WIPRO |
|--------|-----|------|-------|
| Current Ratio | 1.8x | 1.6x | 1.5x |
| Debt/Equity | 0.15x | 0.10x | 0.25x |
| Cash (₹ Cr) | 18,500 | 16,200 | 8,100 |
| ROA | 12.1% | 11.5% | 10.2% |

## Peer Analysis & Assessment

### TCS - Market Leader ⭐
**Strengths:**
- Highest profitability (17.2% margins)
- Consistent revenue growth despite slowdown
- Strongest balance sheet
- Best capital efficiency (32.5% ROE)

**Concerns:**
- Premium valuation (24.5x P/E)
- Largest exposure to currency headwinds
- Slower growth than historical

**Verdict:** Quality play, premium priced. Best for value/quality combo.

### Infosys - Balanced Player
**Strengths:**
- Strong margins (16.8%)
- Good growth trajectory
- Diverse client base
- Reasonable valuation

**Concerns:**
- Moderate growth (2.0%)
- Execution challenges in transitions
- Client concentration

**Verdict:** Solid mid-tier option, reasonable valuation.

### Wipro - Value Play 💰
**Strengths:**
- Most attractive valuation (18.5x P/E)
- High dividend yield (3.2%)
- Improving operational metrics
- Lower debt

**Concerns:**
- Negative growth (-0.5%)
- Weakest margins (14.2%)
- Client concentration risk
- Turnaround still in progress

**Verdict:** For value investors, turnaround story.

## Sector Trends
1. **Growth Slowdown** - All three showing slower growth
2. **Margin Resilience** - Margins holding despite pressures
3. **Digital Transition** - All investing in high-margin services
4. **Attrition Challenges** - All facing talent retention costs

## Investment Perspective

### For Growth Investors
**Pick: TCS**
- Consistent growth even in slowdown
- High-quality execution
- Premium justified for quality

### For Value Investors
**Pick: Wipro**
- Attractive valuation
- High dividend yield
- Turnaround opportunity

### For Balanced Approach
**Pick: Infosys**
- Middle ground in valuation
- Solid margins
- Good execution history

## Recommendation
**Diversified Approach:** Hold all three
- TCS for stability and quality
- Infosys for balanced approach
- Wipro for value and yield

**Or Single Stock:** TCS if forced to choose (best quality, growth, margins)
```

**Implementation:**
```python
def compare_companies(
    self,
    tickers: List[str],
    metrics: List[str],
    period: str = "FY2023",
) -> str:
    """Compare multiple companies using actual financial data."""
    
    # 1. Fetch financial data for all companies
    companies_data = {}
    for ticker in tickers:
        companies_data[ticker] = {
            "financials": self.get_financials(ticker),
            "fundamentals": self.get_fundamentals(ticker),
            "market_data": self.get_market_data(ticker),
        }
    
    # 2. Build comparison tables
    comparison_tables = self.build_comparison_tables(
        companies_data,
        metrics
    )
    
    # 3. Generate insights with LLM
    prompt = f"""
Create a comprehensive peer comparison for {', '.join(tickers)}.

Financial Data:
{json.dumps(companies_data, indent=2, default=str)}

Comparison Tables:
{comparison_tables}

Structure:
1. Financial Metrics Table (scale, growth, profitability)
2. Profitability & Efficiency Table
3. Valuation Metrics Table
4. Peer Analysis (strengths, concerns, verdict for each)
5. Sector Trends
6. Investment Perspective (by investor type)
7. Recommendation

Guidelines:
- Use actual numbers from data
- Be objective and data-driven
- Include emojis for visual interest (⭐, 💰, etc.)
- Format as markdown tables
- Provide actionable insights
"""
    
    response = self.llm_service.generate(
        prompt=prompt,
        system_prompt="You are an equity analyst. Create detailed peer comparisons.",
        temperature=0.6,
        max_tokens=3000,
    )
    
    return response.content
```

### Capability 6: Structured Research Report

**Input:**
```python
{
  "ticker": "TCS",
  "report_type": "comprehensive",  # summary, comprehensive, investment_thesis
  "include_sections": [
    "overview",
    "financial_analysis",
    "swot",
    "risks",
    "valuation",
    "recommendation"
  ],
  "format": "markdown"  # markdown, pdf
}
```

**Output:** Multi-page markdown report combining all above analyses

**Implementation:**
```python
def generate_research_report(
    self,
    ticker: str,
    report_type: str = "comprehensive",
    include_sections: List[str] = None,
    format: str = "markdown",
) -> str:
    """Generate comprehensive structured research report."""
    
    if include_sections is None:
        include_sections = [
            "overview",
            "financial_analysis",
            "swot",
            "risks",
            "valuation",
            "recommendation"
        ]
    
    # 1. Generate all sections
    sections = {}
    
    if "overview" in include_sections:
        sections["overview"] = self.generate_company_overview(ticker)
    
    if "financial_analysis" in include_sections:
        sections["financial_analysis"] = self.analyze_financial_performance(
            ticker,
            metrics=["revenue", "profitability", "cash_flow"],
            period="5Y"
        )
    
    if "swot" in include_sections:
        sections["swot"] = self.generate_swot_analysis(ticker)
    
    if "risks" in include_sections:
        sections["risks"] = self.identify_risks_and_opportunities(ticker)
    
    if "valuation" in include_sections:
        sections["valuation"] = self.generate_valuation_analysis(ticker)
    
    if "recommendation" in include_sections:
        sections["recommendation"] = self.generate_investment_recommendation(ticker)
    
    # 2. Compile into report
    report = self._compile_report(
        ticker,
        sections,
        report_type,
        format
    )
    
    return report
```

### Capability 7: Save Reports for Future Reference

**Implementation:**
```python
# Database model for saved reports
class SavedReport(Base):
    __tablename__ = "saved_reports"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), index=True)
    report_type = Column(String(50))
    title = Column(String(255))
    content = Column(String(50000))  # markdown content
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    tags = Column(String(255), nullable=True)  # comma-separated
    
    def __repr__(self):
        return f"<SavedReport {self.ticker} - {self.report_type}>"

# API endpoints
@research_router.post("/reports")
async def save_report(
    ticker: str,
    report_type: str,
    content: str,
    db: Session = Depends(get_db),
):
    """Save a generated report."""
    report = SavedReport(
        ticker=ticker,
        report_type=report_type,
        content=content,
        title=f"{ticker} {report_type} Report",
    )
    db.add(report)
    db.commit()
    return {"id": report.id, "status": "saved"}

@research_router.get("/reports")
async def list_reports(
    ticker: Optional[str] = None,
    report_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List saved reports."""
    query = db.query(SavedReport)
    if ticker:
        query = query.filter(SavedReport.ticker == ticker)
    if report_type:
        query = query.filter(SavedReport.report_type == report_type)
    return query.all()

@research_router.get("/reports/{report_id}")
async def get_report(report_id: int, db: Session = Depends(get_db)):
    """Retrieve a saved report."""
    report = db.query(SavedReport).get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
```

---

## Phase 4.5: AI Explanations

The explanation layer works across all ArthAI features. Let me show how to implement it.

### Explanation 1: ML Predictions

**Input:**
```python
{
  "prediction": {
    "type": "price_movement",
    "direction": "UP",
    "confidence": 0.72,
    "prediction_price": 3850,
    "current_price": 3650,
  },
  "ticker": "TCS"
}
```

**Output:**
```markdown
# Why ML Predicts TCS Price Will Go UP

## Prediction Summary
- **Direction:** ⬆️ UP
- **Confidence:** 72% (Moderately High)
- **Predicted Price:** ₹3,850 (5.5% upside)
- **Current Price:** ₹3,650

## Model Confidence Breakdown
```
High Confidence (> 80%): Not reached
Moderate-High Confidence (70-80%): ✓ Current level (72%)
Moderate Confidence (50-70%): 
Low Confidence (< 50%):
```

## Key Factors Driving Prediction

### Positive Signals (Weight: 65%)
1. **Technical Indicators** (Weight: 25%)
   - RSI at 38 (oversold territory)
   - MACD showing bullish crossover
   - Moving average support at ₹3,600
   **Implication:** Potential reversal from oversold levels

2. **Momentum Factors** (Weight: 20%)
   - Volume increased 15% above average
   - Options data shows call buying
   **Implication:** Institutional buying pressure

3. **Fundamental Strength** (Weight: 20%)
   - Earnings growth trending positive
   - Analyst upgrades in last month
   **Implication:** Improving sentiment

### Negative Signals (Weight: 35%)
1. **Market Headwinds** (Weight: 15%)
   - Sector showing weakness (IT -2.3%)
   - Banking index down 1.5%
   **Implication:** Sector headwinds could limit upside

2. **Valuation Concerns** (Weight: 15%)
   - Already at 24.5x P/E (premium)
   - Relative to 5-year average
   **Implication:** Limited multiple expansion room

3. **Macro Risk** (Weight: 5%)
   - Rupee weakening could impact margins
   **Implication:** Currency headwind

## Uncertainty & Limitations ⚠️

### What Could Go Wrong
1. **Unexpected News** - Earnings miss could reverse prediction
2. **Market Shocks** - Sector rotation could change dynamics
3. **Macro Changes** - Interest rate hike could impact growth stocks
4. **Model Limitations** - Past performance ≠ future results

### Confidence Score Interpretation
- **72% = Moderate Confidence**
  - Not a strong conviction (< 80%)
  - Should be combined with other analysis
  - Consider risk/reward ratio
  - Don't base entire decision on this alone

### Data Recency
- Last updated: Today, 2:30 PM IST
- Market data: Real-time
- ML model: Retrained daily

### Proper Use
✓ Use as one input among many
✓ Combine with fundamental analysis
✓ Consider your risk tolerance
✓ Review thesis regularly
✓ Set stop losses appropriately

❌ Don't use as standalone signal
❌ Don't chase momentum blindly
❌ Don't ignore risk factors
❌ Don't assume 72% = 72% probability

## Model Details

### Algorithm Used
- Gradient Boosting (LightGBM)
- Technical indicators: 40 features
- Sentiment data: 20 features
- Fundamental data: 15 features

### Historical Accuracy
- **Directional Accuracy:** 68% (on holdout test set)
- **Precision (UP prediction):** 72%
- **Recall (UP prediction):** 65%
- **Sharpe Ratio:** 1.2x (backtested)

### Recent Performance
- Last 20 predictions: 14 correct (70%)
- Recent streak: 3 correct out of last 5
- Best in: Mid-cap stocks
- Worst in: Highly volatile penny stocks

## Recommendation
This is a **MODERATE BUY signal** for:
- Investors with 3-6 month horizon
- Risk-tolerant positions
- Combined with fundamental strength

Not suitable for:
- Very short-term traders (< 1 week)
- Risk-averse investors
- Already overweight TCS position
```

**Implementation:**
```python
# backend/app/services/explanations.py

class AIExplanationService:
    def explain_ml_prediction(
        self,
        ticker: str,
        prediction: dict,
        model_name: str = "gradient_boost",
    ) -> str:
        """Explain an ML prediction in human terms."""
        
        # 1. Get prediction details
        direction = prediction.get("direction")  # UP/DOWN
        confidence = prediction.get("confidence")
        
        # 2. Get feature importance
        feature_importance = self.get_feature_importance(
            ticker,
            model_name
        )
        
        # 3. Get market context
        market_context = self.get_market_context(ticker)
        
        # 4. Get model performance metrics
        model_metrics = self.get_model_metrics(model_name)
        
        # 5. Build explanation prompt
        context = {
            "ticker": ticker,
            "prediction": prediction,
            "feature_importance": feature_importance,
            "market_context": market_context,
            "model_metrics": model_metrics,
        }
        
        prompt = f"""
Explain this ML prediction in simple, interpretable terms.

Prediction:
- Direction: {direction}
- Confidence: {confidence:.1%}
- Target: {prediction.get('prediction_price')}

Top Contributing Factors:
{self._format_feature_importance(feature_importance)}

Market Context:
{json.dumps(market_context, indent=2, default=str)}

Model Performance:
{json.dumps(model_metrics, indent=2, default=str)}

Create explanation that:
1. Summarizes the prediction clearly
2. Explains which factors matter most
3. Shows confidence breakdown
4. Clearly states limitations and uncertainty
5. Explains proper usage
6. Includes risk warnings
7. Uses markdown formatting
8. Is accessible to non-technical users
"""
        
        response = self.llm_service.generate(
            prompt=prompt,
            system_prompt="You are an AI/ML expert. Explain predictions clearly and honestly.",
            temperature=0.5,
            max_tokens=2000,
        )
        
        return response.content
```

### Explanation 2: Technical Signals

We already have this from Phase 4! It's in `financial_assistant.py`:
```python
def explain_technical_signal(
    self,
    ticker: str,
    signal: str,
    indicators: dict[str, Any],
) -> str:
```

This explains **why** a BUY/SELL signal was generated.

### Explanation 3: Fundamental Scores

We already have this from Phase 4! It's in `financial_assistant.py`:
```python
def explain_fundamental_score(
    self,
    ticker: str,
    score: float,
    factors: dict[str, Any],
) -> str:
```

This explains **why** a score of X/100 was assigned.

### Explanation 4: News Sentiment

**Input:**
```python
{
  "sentiment_score": 0.72,  # 0-1 scale
  "sentiment_category": "positive",
  "key_articles": 5,
  "ticker": "TCS"
}
```

**Output:**
```markdown
# TCS - News Sentiment Analysis

## Overall Sentiment
- **Score:** 0.72/1.0 (Positive) 📈
- **Interpretation:** Moderately positive sentiment about TCS in news
- **Articles Analyzed:** 47 (last 30 days)
- **Data Freshness:** Updated today

## Sentiment Distribution
```
Positive (0.6-1.0): ████████░ 68% (32 articles)
Neutral  (0.4-0.6): ██░░░░░░░ 15% (7 articles)
Negative (0.0-0.4): ░░░░░░░░░  17% (8 articles)
```

## Key Themes in Positive Articles
1. **Q3 Results Strong** (10 articles)
   - Revenue beat expectations
   - Margin expansion
   - FY24 guidance raised
   **Implication:** Positive for stock near-term

2. **AI/Digital Growth** (8 articles)
   - TCS expanding AI services
   - Cloud capabilities improving
   **Implication:** Positive for long-term growth story

3. **Dividend Increase** (6 articles)
   - 10% dividend increase announced
   - Shareholder friendly
   **Implication:** Attracts income investors

## Key Themes in Negative Articles
1. **Currency Headwinds** (4 articles)
   - INR strength pressures USD revenues
   - Could impact FY24 guidance
   **Implication:** Near-term headwind

2. **Attrition Concerns** (3 articles)
   - Talent market competitive
   - Wage inflation ongoing
   **Implication:** Margin pressure risk

3. **Sector Weakness** (1 article)
   - IT sector facing slowdown
   - Client budget cuts
   **Implication:** Industry headwind

## Potential Implications for Stock

### Near-term (1-3 months)
- **Positive sentiment favors:** ⬆️ UP
- **Likely moves:** +2% to +5%
- **Catalysts:** Quarterly earnings, analyst upgrades

### Medium-term (3-12 months)
- **Mixed signals:** AI growth vs. currency headwinds
- **Key risks:** Client spending slowdown, attrition costs
- **Upside drivers:** Digital transformation, margin recovery

## Sentiment Momentum
- **Trend:** ↗️ Improving (was 0.65 last week)
- **Change:** +0.07 points (positive trend)
- **Volatility:** Moderate (articles mixed but trending positive)

## Limitations ⚠️

### What This Does Tell You
✓ What financial media/analysts think
✓ Current market sentiment themes
✓ Recent news drivers
✓ Sentiment trends

### What This Doesn't Tell You
❌ Actual company fundamentals (check financials)
❌ Company guidance (check earnings calls)
❌ Market surprise potential
❌ Your personal investment thesis alignment

### Proper Usage
- Use as sentiment gauge, not decision driver
- Combine with financial analysis
- Remember: News reflects past, not future
- Be contrarian when sentiment extreme

## Data Transparency
- **Sources:** 30+ financial news outlets
- **Analysis Method:** NLP + ML sentiment model
- **Accuracy on labeled data:** 82%
- **Update Frequency:** Daily
- **Article Recency:** Last 30 days
```

**Implementation:**
```python
def explain_news_sentiment(
    self,
    ticker: str,
    sentiment_data: dict,
) -> str:
    """Explain news sentiment and implications."""
    
    # 1. Get sentiment details
    overall_score = sentiment_data.get("sentiment_score")
    articles = sentiment_data.get("articles", [])
    
    # 2. Categorize articles
    positive_articles = [a for a in articles if a["sentiment"] > 0.6]
    negative_articles = [a for a in articles if a["sentiment"] < 0.4]
    neutral_articles = [a for a in articles if 0.4 <= a["sentiment"] <= 0.6]
    
    # 3. Extract themes
    positive_themes = self.extract_themes(positive_articles)
    negative_themes = self.extract_themes(negative_articles)
    
    # 4. Build context
    context = {
        "ticker": ticker,
        "overall_sentiment": overall_score,
        "distribution": {
            "positive": len(positive_articles),
            "neutral": len(neutral_articles),
            "negative": len(negative_articles),
        },
        "positive_themes": positive_themes,
        "negative_themes": negative_themes,
    }
    
    # 5. Generate explanation
    prompt = f"""
Explain the news sentiment for {ticker}.

Sentiment Data:
{json.dumps(context, indent=2, default=str)}

Create explanation that:
1. Summarizes overall sentiment
2. Shows sentiment distribution (as ASCII chart)
3. Explains key positive themes and implications
4. Explains key negative themes and implications
5. Discusses potential stock implications
6. Clearly states limitations
7. Explains proper usage
8. Uses markdown formatting
"""
    
    response = self.llm_service.generate(
        prompt=prompt,
        system_prompt="You are a financial analyst. Explain news sentiment clearly.",
        temperature=0.5,
        max_tokens=2000,
    )
    
    return response.content
```

### Explanation 5: Uncertainty & Limitations

Every explanation should include uncertainty communication:

**Implementation:**
```python
class UncertaintyExplainer:
    """Communicates uncertainty and limitations clearly."""
    
    @staticmethod
    def add_uncertainty_section(
        explanation: str,
        confidence: float,
        data_freshness: datetime,
        model_type: str,
    ) -> str:
        """Add uncertainty/limitations section to any explanation."""
        
        # Determine confidence language
        if confidence > 0.8:
            confidence_text = "High confidence"
        elif confidence > 0.6:
            confidence_text = "Moderate confidence"
        else:
            confidence_text = "Low confidence"
        
        # Calculate data age
        data_age = datetime.utcnow() - data_freshness
        if data_age.days == 0:
            freshness_text = "Today"
        elif data_age.days == 1:
            freshness_text = "Yesterday"
        else:
            freshness_text = f"{data_age.days} days ago"
        
        # Build uncertainty section
        uncertainty_section = f"""

## Uncertainty & Limitations ⚠️

### Confidence Level
- **{confidence_text}** ({confidence:.0%})
- This is an AI-generated analysis
- Not a financial recommendation
- Always do your own research

### Data Freshness
- Last updated: {freshness_text}
- May not reflect latest developments
- Always check current news

### Model Limitations
- Based on historical patterns
- Cannot predict unprecedented events
- {model_type} has inherent limitations
- Past performance ≠ future results

### Proper Usage
✓ Use as one input among many
✓ Combine with expert analysis
✓ Verify claims independently
✓ Consider your risk tolerance
✓ Consult financial advisor

❌ Don't treat as investment advice
❌ Don't rely solely on this analysis
❌ Don't ignore fundamentals
❌ Don't override your judgment
"""
        
        return explanation + uncertainty_section
```

---

## Implementation Roadmap

### What Needs to Be Built

```
Phase 4.4: Company Research Assistant
├── generate_company_overview()
├── analyze_financial_performance()
├── summarize_annual_report()
├── generate_swot_analysis()
├── compare_companies()
├── generate_research_report()
└── save_reports_database()

Phase 4.5: AI Explanations
├── explain_ml_prediction()
├── explain_technical_signal() [Already have]
├── explain_fundamental_score() [Already have]
├── explain_news_sentiment()
└── add_uncertainty_section()
```

### API Endpoints Needed

```python
# Research endpoints
POST   /api/v1/research/company-overview
POST   /api/v1/research/financial-analysis
POST   /api/v1/research/swot
POST   /api/v1/research/comparison
POST   /api/v1/research/reports          # Generate & save
GET    /api/v1/research/reports          # List
GET    /api/v1/research/reports/{id}     # Retrieve

# Explanation endpoints
POST   /api/v1/explain/ml-prediction
POST   /api/v1/explain/technical-signal  [Already have]
POST   /api/v1/explain/fundamental-score [Already have]
POST   /api/v1/explain/news-sentiment
```

### Files to Create

```
backend/
├── app/
│   ├── services/
│   │   ├── research_assistant.py       [NEW] Company analysis
│   │   └── explanations.py             [NEW] AI explanations
│   │
│   ├── schemas/
│   │   └── research.py                 [NEW] Research schemas
│   │
│   ├── api/routes/
│   │   ├── research.py                 [NEW] Research endpoints
│   │   └── explanations.py             [NEW] Explanation endpoints
│   │
│   └── db/
│       └── models.py                   [MODIFIED] Add SavedReport
│
└── test_research_and_explanations.py   [NEW] Tests
```

---

## Timeline & Effort

### Phase 4.4: Company Research (3-4 days)
- Day 1: Data gathering & analysis methods
- Day 2: LLM integration for generation
- Day 3: API endpoints & storage
- Day 4: Testing & documentation

### Phase 4.5: AI Explanations (2-3 days)
- Day 1: ML prediction explanations
- Day 2: News sentiment explanations
- Day 3: Uncertainty communication & testing

**Total: 5-7 days**

---

## What You Need From Me

To start building:

```
1. Confirm you want this approach
2. Sample data format (optional - I can work with existing)
3. Any specific companies for initial testing
4. Preference: PDF export for reports? (requires reportlab)
```

Ready to start? I can have Phase 4.4 & 4.5 done in 5-7 days with:
- **Zero infrastructure changes** (uses existing systems)
- **Zero new dependencies** (mostly LLM + existing data)
- **Backward compatible** (adds to existing Phase 4 work)
- **Production ready** (tested, documented, with uncertainty communication)

What do you say? Should I proceed with this implementation?
