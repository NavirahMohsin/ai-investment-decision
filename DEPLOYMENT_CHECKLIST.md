# Phase 4: Deployment Checklist

## Pre-Deployment Verification ✅

### Backend Services
- [x] `research_assistant.py` - 350+ lines, fully functional
- [x] `explanations.py` - 400+ lines, fully functional
- [x] API routes registered and tested
- [x] Pydantic schemas for validation
- [x] Error handling for invalid inputs
- [x] LLM service fixed and working
- [x] Fallback strategy (Gemini → Groq) implemented

### Tests
- [x] 27/27 tests passing (Phase 4.4 & 4.5)
- [x] 12+ tests passing (Phase 4.2)
- [x] Error handling verified
- [x] Happy path tested
- [x] Invalid input handling tested

### Frontend Pages
- [x] Research page (`/research`) - 200+ lines
- [x] Explanations page (`/explanations`) - 200+ lines
- [x] Assistant page (`/assistant`) - 250+ lines
- [x] API client (`lib/api-client.ts`) - 400+ lines
- [x] Research hooks (`hooks/useResearch.ts`) - 250+ lines
- [x] Explanation hooks (`hooks/useExplanations.ts`) - 250+ lines

### UI/UX
- [x] Loading states on all buttons
- [x] Error messages displayed to users
- [x] Disclaimers on all pages
- [x] Responsive design (mobile, tablet, desktop)
- [x] React Markdown rendering working
- [x] Tab navigation functional
- [x] Dashboard quick access updated

### Documentation
- [x] `FRONTEND_INTEGRATION.md` - 570+ lines
- [x] `PHASE_4_SUMMARY.md` - 600+ lines
- [x] API examples documented
- [x] Setup instructions clear
- [x] Troubleshooting guide included

### Git/Version Control
- [x] Branch: `phase-4-frontend-integration` created
- [x] All changes committed (4 commits)
- [x] Branch pushed to remote
- [x] Ready for pull request

---

## Deployment Steps

### Step 1: Code Review
```bash
# Review all changes
git diff main..phase-4-frontend-integration

# Verify no sensitive data in commits
git log -p phase-4-frontend-integration | grep -i "api_key\|password\|secret"
```

### Step 2: Environment Setup

**Backend** (`backend/.env`):
```bash
# Required
GEMINI=<your-gemini-api-key>
GROQ=<your-groq-api-key>

# Database
DATABASE_URL=postgresql://user:password@host/dbname

# Server
ENV=production
LOG_LEVEL=INFO
PORT=8000
```

**Frontend** (`frontend/.env.production`):
```bash
NEXT_PUBLIC_API_URL=https://your-api-domain.com/api/v1
```

### Step 3: Database Preparation
```bash
# Run any pending migrations
cd backend
alembic upgrade head
```

### Step 4: Build & Test

**Backend**:
```bash
cd backend
pip install -r requirements.txt
python -m pytest test_research_and_explanations.py -v
# Verify: 27/27 tests passing
```

**Frontend**:
```bash
cd frontend
npm install
npm run build
# Verify: No build errors
```

### Step 5: Docker Build (if using containers)

```bash
# Backend
cd backend
docker build -t arthallm:backend:v4.0 .
docker tag arthallm:backend:v4.0 registry.yourdomain.com/arthallm:backend:v4.0
docker push registry.yourdomain.com/arthallm:backend:v4.0

# Frontend
cd frontend
docker build -t arthallm:frontend:v4.0 .
docker tag arthallm:frontend:v4.0 registry.yourdomain.com/arthallm:frontend:v4.0
docker push registry.yourdomain.com/arthallm:frontend:v4.0
```

### Step 6: Deploy

**Option A: Direct Server Deployment**
```bash
# SSH into production server
ssh user@prod-server

# Pull latest code
cd /var/www/arthallm
git fetch origin
git checkout phase-4-frontend-integration

# Update backend
cd backend
pip install -r requirements.txt
systemctl restart arthallm-backend

# Update frontend
cd ../frontend
npm install
npm run build
systemctl restart arthallm-frontend
```

**Option B: Kubernetes Deployment**
```bash
# Update deployments
kubectl set image deployment/arthallm-backend \
  arthallm-backend=registry.yourdomain.com/arthallm:backend:v4.0

kubectl set image deployment/arthallm-frontend \
  arthallm-frontend=registry.yourdomain.com/arthallm:frontend:v4.0

# Verify rollout
kubectl rollout status deployment/arthallm-backend
kubectl rollout status deployment/arthallm-frontend
```

**Option C: Docker Compose**
```bash
cd /var/www/arthallm
git checkout phase-4-frontend-integration
docker-compose down
docker-compose pull
docker-compose up -d
```

### Step 7: Post-Deployment Verification

#### Health Checks
```bash
# Backend API health
curl https://api.yourdomain.com/api/v1/research/health
# Expected: { "status": "healthy", "provider": "gemini" }

curl https://api.yourdomain.com/api/v1/explain/health
# Expected: { "status": "healthy", "provider": "gemini" }

curl https://api.yourdomain.com/api/v1/assistant/health
# Expected: { "status": "healthy" }

# Frontend page loads
curl https://yourdomain.com/research
curl https://yourdomain.com/explanations
curl https://yourdomain.com/assistant
```

#### Functional Testing
```bash
# Test research endpoint
curl -X POST https://api.yourdomain.com/api/v1/research/company-overview \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TCS"}'
# Verify: Returns markdown content

# Test explanation endpoint
curl -X POST https://api.yourdomain.com/api/v1/explain/ml-prediction \
  -H "Content-Type: application/json" \
  -d '{"ticker": "INFY", "prediction": 0.65, "confidence": 0.82}'
# Verify: Returns explanation with uncertainty footer

# Test assistant endpoint
curl -X POST https://api.yourdomain.com/api/v1/assistant/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a good P/E ratio?"}'
# Verify: Returns answer
```

#### Frontend Verification
1. Navigate to `https://yourdomain.com/research`
   - Enter ticker "TCS"
   - Click "Company Overview"
   - Verify: Markdown content loads in 2-5 seconds

2. Navigate to `https://yourdomain.com/explanations`
   - Enter ticker "INFY"
   - Click "ML Prediction"
   - Verify: Explanation with uncertainty footer loads

3. Navigate to `https://yourdomain.com/assistant`
   - Ask: "How do I analyze stocks?"
   - Verify: Multi-turn conversation works

### Step 8: Monitoring

**Logs to Monitor**:
```bash
# Backend
tail -f /var/log/arthallm/backend.log

# Frontend
tail -f /var/log/arthallm/frontend.log

# Database
tail -f /var/log/postgresql/postgresql.log
```

**Metrics to Watch**:
- API response time (target: < 5 seconds)
- Error rate (target: < 1%)
- LLM API quota usage
- Database query performance
- Frontend load time (target: < 2 seconds)

### Step 9: Rollback Plan

**If deployment fails**:
```bash
# Revert to previous version
git checkout main

# Rebuild and redeploy
docker-compose down
docker-compose build
docker-compose up -d

# Or revert deployment
kubectl rollout undo deployment/arthallm-backend
kubectl rollout undo deployment/arthallm-frontend
```

---

## Production Considerations

### Security
- [x] No API keys in code (use .env)
- [x] CORS properly configured
- [x] Input validation on all endpoints
- [x] Error messages don't leak sensitive info
- [x] HTTPS enforced in production
- [x] Rate limiting configured

### Performance
- [x] Database queries optimized
- [x] Markdown rendering efficient
- [x] API response caching considered
- [x] Frontend bundle size monitored
- [x] LLM API calls timeouts set

### Reliability
- [x] Fallback LLM provider (Groq)
- [x] Database backups scheduled
- [x] Error logging configured
- [x] Health check endpoints available
- [x] Graceful error handling throughout

### Maintainability
- [x] Code documented with docstrings
- [x] Configuration externalized
- [x] Deployment scripts automated
- [x] Version control clean
- [x] Change log maintained

---

## Rollback Criteria

**Immediate rollback if**:
- Error rate > 5%
- API response time > 10 seconds
- Database connection fails
- LLM API returns errors consistently
- Frontend not loading
- Security vulnerability detected

**Gradual rollback if**:
- Unexpected behavior in specific use case
- Performance degradation < 20%
- Minor UI issues

---

## Success Criteria

**Deployment successful if**:
- ✅ All health checks return 200
- ✅ No critical errors in logs
- ✅ API response time < 5 seconds
- ✅ Frontend loads in < 2 seconds
- ✅ All three pages accessible and functional
- ✅ Error rate < 1%
- ✅ Users can generate research/explanations
- ✅ No data loss or corruption
- ✅ Database integrity verified

---

## Contact & Support

**Deployment Issues**:
- Check logs: `tail -f /var/log/arthallm/*.log`
- Review troubleshooting: `FRONTEND_INTEGRATION.md#Troubleshooting`
- Check health endpoints
- Verify API keys are correct
- Test database connectivity

**Escalation**:
1. Check logs for errors
2. Review recent code changes
3. Consult deployment checklist
4. Verify all prerequisites met
5. Contact development team if needed

---

## Sign-Off

**Deployment Manager**: _______________  Date: _______

**QA Lead**: _______________  Date: _______

**DevOps Engineer**: _______________  Date: _______

---

**Document Version**: 1.0  
**Last Updated**: November 15, 2026  
**Status**: Ready for Deployment
