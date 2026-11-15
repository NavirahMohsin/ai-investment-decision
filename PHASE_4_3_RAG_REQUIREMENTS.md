# Phase 4.3: RAG Implementation — Requirements Gathering

## What I Need From You

To build a production-ready RAG system for ArthAI, I need decisions and resources in these categories:

---

## 1. Document Sources & Acquisition

### Question 1A: Where will documents come from?

**Option A: User Upload** (Most Flexible)
- Users upload PDF/documents via UI
- Full control, privacy guaranteed
- Requires storage infrastructure
- Best for: Proprietary documents, internal reports

**Option B: Web Scraping** (Most Scalable)
- Automatically crawl company websites
- Get annual reports from:
  - `company.com/investors` (IR pages)
  - NSE website: `nseindia.com/listings`
  - BSE website: `bseindia.com`
- Requires: Legal review, robots.txt compliance
- Best for: Public data at scale

**Option C: API Integration** (Most Reliable)
- Third-party document APIs:
  - **SEC/EDGAR** (US companies) - free
  - **Calamari API** - document extraction
  - **Dun & Bradstreet** - company reports
  - **Company IR APIs** - if available
- Requires: API keys, costs
- Best for: Structured, clean data

**Option D: Manual Curation** (Most Controlled)
- Pre-download specific documents
- Store in version control or S3
- Review each one before ingestion
- Best for: Starting with 5-10 companies

### What I Need You to Decide:
```
[ ] Which option? A / B / C / D / Combination?
[ ] If B (scraping): Which companies should we start with?
[ ] If C (API): Budget available for API costs?
[ ] If D (manual): Which 5-10 companies/documents?
[ ] Priority: Speed to MVP vs. Scale vs. Data quality?
```

**My Recommendation:** Start with **Option D (Manual Curation)** for MVP
- Download 10-15 annual reports manually
- Prove the system works
- Then scale to Option B (scraping) or C (API)

---

## 2. Document Storage

### Question 2A: Where should documents be stored?

**Option A: Local Filesystem** (Simplest for MVP)
```
backend/data/documents/
├── TCS/
│   ├── 2023_annual_report.pdf
│   ├── 2022_annual_report.pdf
│   └── Q1_2024_earnings_call.txt
├── INFY/
│   ├── 2023_annual_report.pdf
│   └── investor_presentation.pdf
└── ...
```
- **Pros:** Free, simple, no infrastructure
- **Cons:** Doesn't scale, not backed up, local only
- **Good for:** Development, small MVP (< 1000 documents)

**Option B: Cloud Storage (AWS S3 / Google Cloud Storage)**
```
s3://arthrai-documents/
├── TCS/2023_annual_report.pdf
├── INFY/2023_annual_report.pdf
└── ...
```
- **Pros:** Scalable, backed up, accessible from anywhere
- **Cons:** Requires AWS/GCP setup, costs (small for documents)
- **Good for:** Production, team collaboration
- **Cost:** ~$0.02-0.03 per GB/month

**Option C: Dedicated Document Management**
- Minio (self-hosted S3 alternative)
- NextCloud (document server)
- Confluence (enterprise docs)
- **Pros:** Full control, self-hosted
- **Cons:** Additional infrastructure

### What I Need You to Decide:
```
[ ] Storage option? A (local) / B (S3) / C (self-hosted)?
[ ] If B: Do you have AWS account? Budget?
[ ] If C: Do you want to manage infrastructure?
[ ] Backup requirements?
[ ] Access from team/multiple servers?
```

**My Recommendation:** Start with **Option A (Local)**, migrate to **Option B (S3)** later
- Fast MVP with no infrastructure
- Easy to switch to S3 later
- Single migration task

---

## 3. Vector Database Storage

### Question 3A: Where to store vector embeddings?

**Option A: ChromaDB (Local, File-based)** ⭐ BEST FOR MVP
```
backend/data/chroma/
├── arthrai.db
└── (vector index files)
```
- **Pros:** 
  - Free, zero setup
  - Persistent on disk
  - Included in requirements.txt
  - Works offline
  - Good for < 100K vectors
- **Cons:** Single machine, no scaling
- **Good for:** MVP, testing, small deployments
- **Storage:** Minimal (< 500MB for 10K documents)

**Option B: Pinecone (Cloud Vector DB)** 🚀 BEST FOR SCALE
```
https://api.pinecone.io
├── Production index (millions of vectors)
└── (managed, backed up)
```
- **Pros:**
  - Enterprise-grade
  - Automatic scaling
  - Backed up & replicated
  - API-first, works anywhere
- **Cons:** 
  - Paid tier ($0.04 per 100K vectors/month)
  - Requires API key
- **Good for:** Production at scale (> 1M documents)
- **Cost:** ~$40/month for 1M vectors

**Option C: Weaviate (Self-hosted)**
```
docker-compose.yml
├── weaviate:latest
└── (vector store)
```
- **Pros:**
  - Self-hosted, full control
  - Open source
  - Scalable
- **Cons:**
  - Infrastructure to manage
  - DevOps setup needed
- **Good for:** Teams wanting self-hosting

**Option D: Milvus (Lightweight)**
- Like Weaviate but simpler
- Good middle ground

### What I Need You to Decide:
```
[ ] Vector DB? A (ChromaDB) / B (Pinecone) / C (Weaviate) / D (Milvus)?
[ ] Expected document volume? (10 / 100 / 1000 / 10000+)?
[ ] Budget for vector DB costs? (if not free)
[ ] Need multi-server access?
[ ] Need automatic backups?
```

**My Recommendation:** Start with **ChromaDB (A)**, upgrade to **Pinecone (B)** when scaling
- Zero cost for MVP
- Tested, reliable
- Easy migration path
- Add Pinecone when you exceed 10K vectors

---

## 4. Document Types & Content

### Question 4A: What types of documents?

**Primary (Structured Financial):**
- [ ] Annual Reports (10-K equivalent)
- [ ] Quarterly Reports (10-Q equivalent)
- [ ] Investor Presentations
- [ ] Earnings Call Transcripts

**Secondary (Semi-Structured):**
- [ ] Press Releases
- [ ] Regulatory Filings
- [ ] Board Resolutions
- [ ] Corporate Announcements

**Tertiary (Unstructured):**
- [ ] News Articles
- [ ] Analyst Reports
- [ ] Blog Posts

### Question 4B: Data format?

- [ ] PDFs (most documents start as this)
- [ ] Text files (.txt)
- [ ] Word documents (.docx)
- [ ] HTML
- [ ] Structured JSON/CSV

### What I Need You to Decide:
```
[ ] Document types to support? (check above)
[ ] Which companies first? (TCS / INFY / HDFC / RELIANCE / others?)
[ ] How many documents per company? (5 / 10 / 20 / unlimited?)
[ ] Time range? (Last 3 years / 5 years / all available?)
[ ] Update frequency? (Static / Monthly / Quarterly / Real-time?)
```

**My Recommendation:**
- Start with: **Annual Reports + Earnings Transcripts only**
- Companies: **TCS, INFY, HDFC Bank, Reliance** (4 blue-chips)
- Documents: **5 each = 20 total** for MVP
- Format: **PDFs** (universal)
- Time range: **Last 3 years** (enough for trends)

---

## 5. Legal & Compliance

### Question 5A: Document licensing & permissions?

- [ ] All documents are publicly available (annual reports)?
- [ ] Do we have permission to ingest/store them?
- [ ] Do we need to remove any copyrighted content?
- [ ] Do we need to add attribution/citations?
- [ ] Are there regional restrictions (data localization)?

### Question 5B: Data privacy requirements?

- [ ] Should documents stay in India (data sovereignty)?
- [ ] Any PII/sensitive data to redact?
- [ ] Regulatory compliance needed (SEBI, RBI)?
- [ ] User data separation (per-user RAG)?

### What I Need You to Decide:
```
[ ] Legal review done? Yes / No / In Progress?
[ ] Can we use public annual reports? Yes / No?
[ ] Need to add copyright notices?
[ ] Data must stay in India? Yes / No?
[ ] Any compliance frameworks? (GDPR / ISO / SEBI / others?)
```

**My Recommendation:**
- All documents: **Public annual reports** (free to use)
- Attribution: **Add source URL + publication date**
- Compliance: **Add disclaimer in answers**
- Data location: Keep in India if required, but S3 works globally

---

## 6. Initial Data / Sample Documents

### Question 6A: Can you provide sample documents?

For me to build the system, it helps to have actual documents to test with:

```
Required (for testing):
├── 1 sample annual report PDF
├── 1 earnings call transcript
└── 1 investor presentation (optional)

Nice to have:
├── All 4 companies × 3 years
├── Multiple formats (PDF, TXT)
└── Already in a shared location (S3/Drive)
```

### Where to get documents (if you don't have them):

**Option A: You Provide**
- Download from company investor relations pages
- Store in Google Drive / S3
- Share link with me

**Option B: I'll Find Them**
- Search company websites
- Download publicly available reports
- Store in project repo or S3
- **Time needed:** 2-3 hours for 4 companies

**Option C: We Share the Task**
- You provide company list
- I create scraper/downloader
- Documents auto-downloaded

### What I Need You to Decide:
```
[ ] Can you provide sample documents? Yes / No / Partially?
[ ] If yes: Where? (Drive link / S3 / Email / Upload here?)
[ ] If no: Should I download them?
[ ] Timeline: How urgently needed? (Now / This week / Next week?)
[ ] Which companies priority? (TCS / INFY / HDFC / Reliance / others?)
```

**My Recommendation:**
- **Provide 2-3 sample PDFs** (TCS + INFY annual reports)
- Store in `backend/data/sample_documents/`
- I'll build system to handle any PDF format

---

## 7. Infrastructure & Deployment

### Question 7A: Where will this run?

**Option A: Local Development**
- Everything runs on your machine
- Fast iteration
- Good for: MVP, testing

**Option B: Staging Server**
- Separate machine/VM for testing
- Multi-user testing
- Good for: Team review, before production

**Option C: Production**
- Live user-facing system
- Proper backups, scaling
- Good for: Actual usage

### Question 7B: Infrastructure requirements?

- [ ] Can add Docker containers?
- [ ] Do you have cloud infrastructure? (AWS / GCP / Azure?)
- [ ] Need multi-region support?
- [ ] Performance requirements? (< 1s / < 5s / no constraint?)

### What I Need You to Decide:
```
[ ] Deployment target? (Local / Staging / Production)
[ ] Cloud provider? (AWS / GCP / Azure / None / Undecided?)
[ ] Docker/containers? Yes / No / Prefer not?
[ ] Performance SLA? (< 1s / < 5s / < 10s?)
```

**My Recommendation:**
- Start: **Local + ChromaDB** (no infrastructure)
- Later: Move documents to S3, vectors to Pinecone
- All behind existing FastAPI server

---

## 8. Timeline & Priorities

### Question 8A: What's the priority?

**Option A: Speed to Market (MVP First)**
- Get RAG working ASAP
- Use: ChromaDB + Local Storage + Manual Documents
- **Time: 2-3 days**
- Later: Scale infrastructure

**Option B: Production Ready (Do It Right)**
- Full infrastructure setup
- Cloud storage, scalable vector DB
- Comprehensive testing
- **Time: 1-2 weeks**

**Option C: Hybrid (Smart MVP)**
- Build for scale from start
- Use cloud storage + ChromaDB
- Easy migration path
- **Time: 4-5 days**

### What I Need You to Decide:
```
[ ] Priority? Speed (A) / Quality (B) / Balanced (C)?
[ ] When needed? (This week / This month / Flexible?)
[ ] Budget for: Development time / Infrastructure / Both?
```

**My Recommendation:**
- **Go with Option C (Hybrid Smart MVP)**
- Build with scaling in mind
- Start local, easy to move to cloud
- Deliver in 4-5 days

---

## 9. Success Metrics

### Question 9A: How do we measure success?

What would make this RAG system successful for you?

```
[ ] Answer accuracy: > 90% answers cite correct sources?
[ ] Retrieval speed: < 2 seconds per query?
[ ] Coverage: Works for all 4 companies?
[ ] Usability: Users see citations?
[ ] Scalability: Supports 100+ documents?
[ ] Cost: Free or < $100/month?
```

### What I Need You to Decide:
```
[ ] Must-have metrics? (pick top 3)
[ ] Nice-to-have metrics? (pick 2-3)
[ ] Acceptable latency? (1s / 2s / 5s / 10s?)
[ ] Budget constraint? (Yes / No / Amount?)
```

---

## Summary: Decision Matrix

Create this matrix and fill it out:

```
┌─────────────────────────┬──────────────────────────────────┐
│ Decision                │ Your Choice                      │
├─────────────────────────┼──────────────────────────────────┤
│ 1. Document Source      │ A / B / C / D / [ ]              │
│ 2. Document Storage     │ A / B / C / [ ]                  │
│ 3. Vector DB            │ A / B / C / D / [ ]              │
│ 4. Companies (1st batch)│ TCS, INFY, HDFC, Reliance, [...] │
│ 5. Document Types       │ Annual / Earnings / [...] / [ ]  │
│ 6. Legal Review Done?   │ Yes / No / In Progress           │
│ 7. Sample Docs Avail?   │ Yes / No / Can provide [ ]       │
│ 8. Infrastructure       │ Local / Cloud / Hybrid           │
│ 9. Timeline             │ Speed / Quality / Balanced       │
│ 10. Budget              │ Amount / Open ended              │
└─────────────────────────┴──────────────────────────────────┘
```

---

## What I'll Do Once You Decide

### Phase 4.3 Implementation (I handle):

```
✓ Set up vector database (ChromaDB or chosen option)
✓ Build document ingestion pipeline
✓ Create embedding generation service
✓ Build retrieval/search service
✓ Integrate with existing LLM service
✓ Add citations to answers
✓ Create API endpoints for document management
✓ Write comprehensive tests
✓ Document everything
✓ Provide deployment guide

Timeline: 4-5 days (with clear requirements)
```

### What You Do:

```
✓ Provide sample documents OR approval to download
✓ Make infrastructure decisions
✓ Decide on document sources
✓ Review legal/compliance aspects
✓ Test and provide feedback
✓ Approve before production
```

---

## Next Steps

1. **Read this document** - You're here ✓
2. **Fill out the decision matrix** - Share with me
3. **Provide 2-3 sample PDFs** - For testing
4. **Approve infrastructure choices** - Or let me recommend
5. **I'll start building** - 4-5 day delivery

---

## Questions for You

Before I can start, please answer:

1. **Where do you want documents to come from?** (specific sources)
2. **Where should they be stored?** (local / cloud / hybrid)
3. **Which vector DB?** (ChromaDB for MVP, or something else?)
4. **Which 4-5 companies first?** (for MVP)
5. **Can you provide sample PDFs?** (or should I find them?)
6. **What's your timeline?** (this week / flexible?)
7. **Any budget constraints?** (free tools only, or willing to spend?)
8. **Any legal/compliance concerns?** (data sovereignty, etc?)

---

## Recommended Quick Path

If you just want me to start building (I'll make smart defaults):

```
✅ DO THIS:
- Provide 2-3 sample annual report PDFs
- Confirm these 4 companies: TCS, INFY, HDFC, Reliance
- Say "Go with MVP approach"

I WILL:
- Use ChromaDB (local, free)
- Store documents in backend/data/documents/
- Build full RAG pipeline
- Integrate with existing assistant
- Add citations to all answers

TIME: 4-5 days, fully tested
COST: $0 (all free tools)
```

Would you like to go with this approach, or do you have specific requirements for any of the decisions above?
