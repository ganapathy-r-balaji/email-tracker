# AI Email Package Tracker — Build Plan & Journal

This document captures the full build journey from initial idea to deployed app.

---

## Original Goal

Build an AI-powered email package tracker where users connect their Gmail account(s) via OAuth, and get a dashboard showing all tracked packages and orders. Claude AI classifies and extracts structured data from emails automatically.

---

## Key Decisions Made

| Decision | Choice | Reason |
|---|---|---|
| AI model | `claude-sonnet-4-6` | Best balance of speed and accuracy |
| Database | PostgreSQL (Supabase) | Started with SQLite locally, migrated for cloud hosting |
| Email provider | Gmail only (MVP) | Simplest OAuth, largest user base |
| Backend | FastAPI (Python) | Fast, async, great for AI integrations |
| Frontend | Next.js 14 + TypeScript | App Router, React Query, Tailwind |
| Hosting | Vercel + Render + Supabase | All free tiers |
| Auth | Google OAuth2 + PKCE | Required by Google for web apps |

---

## Build Steps

### Step 1 — Project Setup
- Created repo at `~/Documents/GitHub/Email-tracker`
- Set up `backend/` (FastAPI) and `frontend/` (Next.js) folders
- Configured `.env` for backend, `.env.local` for frontend

### Step 2 — Database Models
- `User` — stores user info and session data
- `Order` — vendor, order ID, total price, currency, status, order date
- `Item` — line items per order (name, quantity, unit price, category)
- `Shipment` — tracking number, carrier, estimated delivery, actual delivery
- `EmailLog` — deduplication table (one row per processed Gmail message ID)

### Step 3 — Gmail OAuth
- Implemented Google OAuth2 flow with PKCE (Proof Key for Code Exchange)
- `code_verifier` stored in httponly cookie, `code_challenge` sent in auth URL
- Session cookie signed with `itsdangerous.URLSafeTimedSerializer`
- OAuth tokens encrypted with Fernet before storing in database

### Step 4 — Gmail Sync Pipeline
- Gmail API search query targets order-related subjects
- Recursive MIME parser extracts plain text from all email parts
- Claude classifier: `order_confirmation / shipping_update / delivery_confirmation / irrelevant`
- Claude extractor: structured JSON (vendor, order_id, items, price, tracking, carrier, dates)
- Order linker: matches emails to existing orders by order_id → tracking_number → vendor+date
- APScheduler runs sync every 30 minutes in background

### Step 5 — REST API
- `GET /api/me` — current user
- `GET /api/orders` — paginated, filterable by status
- `GET /api/stats/summary` — total orders, pending, delivered
- `POST /api/sync` — trigger manual sync
- `GET /health` — health check

### Step 6 — Frontend Dashboard
- Landing page with "Connect Gmail" button
- Dashboard with StatsBar, OrderCard (expandable), StatusBadge, SyncButton, Toast
- React Query for data fetching and cache invalidation
- Status filter tabs: All / Ordered / Shipped / Delivered
- Pagination

### Step 7 — Bug Fixes During Initial Testing
- **Error 403 access_denied** — fixed by adding Gmail address to Google Cloud Console test users
- **token_exchange_failed** — fixed by setting `OAUTHLIB_INSECURE_TRANSPORT=1` for localhost HTTP
- **invalid_grant: Missing code verifier** — fixed by implementing full PKCE flow

### Step 8 — Multi-Gmail Account Support
Added ability to connect multiple Gmail accounts to one dashboard:
- New `GmailAccount` model (separate table, FK to User)
- Startup migration copies existing User tokens → GmailAccount rows
- `?action=add` OAuth flow preserves existing session while linking new account
- `oauth_linking_user_id` short-lived cookie tracks which user is adding an account
- `GET /api/accounts` — list connected accounts
- `DELETE /api/accounts/{id}` — disconnect (blocked if last account)
- Sync pipeline iterates over all GmailAccount rows per user
- Frontend: `ConnectedAccounts` component with Add / Disconnect buttons

### Step 9 — Spending Analysis Page
New `/spending` page with 6 chart breakdowns:

| Chart | Description |
|---|---|
| Spending by Month | Monthly totals over time (time series bar chart) |
| Spending by Month of Year | Jan–Dec aggregate across all years (seasonal patterns) |
| Spending by Week of Month | Week 1–5 aggregate (which part of month you spend most) |
| Spending by Week of Year | ISO weeks 1–52 (fine-grained time pattern) |
| Spending by Category | Product category breakdown (donut chart) |
| Top Vendors | Ranked by total spend (table with inline bar) |

- Date range picker (default: last 12 months)
- All charts react to the same date range
- `GET /api/stats/spending?start_date=&end_date=`
- Built with Recharts + react-day-picker

### Step 10 — Cloud Deployment

**Architecture:**
- Frontend → Vercel (free, auto-deploys on git push)
- Backend → Render (free web service)
- Database → Supabase PostgreSQL (free tier, no 90-day expiry)

**Issues resolved during deployment:**
1. `postgres://` → `postgresql://` prefix fix for SQLAlchemy
2. IPv6 incompatibility — switched from Supabase direct connection to Session Pooler URL
3. `redirect_uri_mismatch` — `GOOGLE_REDIRECT_URI` had wrong Render URL (missing `-31s1` suffix)
4. `state_mismatch` — fixed by updating `FRONTEND_URL` from placeholder to real Vercel URL
5. SQLite `strftime()` → PostgreSQL `extract()` migration in spending router
6. `ENCRYPTION_KEY` not needed — derived automatically from `SECRET_KEY` via SHA-256

### Step 11 — Sync Fixes

**Problem:** Dashboard showed 0 orders despite 200 emails found
**Root cause:** `-category:promotions` in Gmail search was excluding order confirmation emails (Gmail puts them in Promotions tab)
**Fix:** Removed `-category:promotions` from search query

**Problem:** All orders showing March 2026 only, not spread across year
**Root cause 1:** Email received date not passed to extractor → `order_date` stored as null → excluded from charts
**Fix 1:** Pass `email_date` to Claude as context; use it as fallback when Claude returns null order_date
**Root cause 2:** `Reset & Re-sync` only cleared `EmailLog`, not `Order` records → re-sync found existing orders and skipped updating dates
**Fix 2:** Reset now deletes EmailLog → Shipments → Items → Orders in correct FK order

**Added:** `POST /api/sync/reset` endpoint + "Reset & Re-sync" button in dashboard UI

---

## Environment Variables Reference

### Backend (Render)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase session pooler PostgreSQL URI |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `GOOGLE_REDIRECT_URI` | `https://your-api.onrender.com/auth/google/callback` |
| `ANTHROPIC_API_KEY` | From console.anthropic.com |
| `SECRET_KEY` | Random 32-byte hex (also derives encryption key) |
| `FRONTEND_URL` | Your Vercel app URL |
| `EMAIL_SYNC_MAX_RESULTS` | `1000` recommended |

### Frontend (Vercel)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Your Render backend URL |

---

## Google Cloud Console Checklist

- [ ] Gmail API enabled
- [ ] OAuth consent screen configured (External)
- [ ] All Gmail addresses added as Test Users
- [ ] Authorized redirect URIs include both localhost and Render callback URLs
- [ ] Authorized JavaScript origins include both localhost and Vercel URL

---

## Live URLs

| Service | URL |
|---|---|
| Frontend | https://email-tracker-umber.vercel.app |
| Backend | https://email-tracker-api-31s1.onrender.com |
| API Docs | https://email-tracker-api-31s1.onrender.com/docs |

---

## Pending / Future Work

- [ ] Fix spending charts to show full year history (sync date range issue)
- [ ] Outlook / Microsoft 365 support
- [ ] Real-time carrier tracking API integration (UPS, FedEx, USPS APIs)
- [ ] Return window reminders / notifications
- [ ] Export spending data to CSV
- [ ] Yahoo Mail support (IMAP)
- [ ] iOS / Android app
- [ ] Google OAuth app verification (to remove "unverified app" warning for non-test users)
