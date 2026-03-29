# AI Email Package Tracker

Track every order and shipment automatically by connecting your Gmail accounts. Claude AI classifies and extracts structured data from order, shipping, and delivery emails — no copy-pasting tracking numbers needed.

**Live app:** [email-tracker-umber.vercel.app](https://email-tracker-umber.vercel.app)

---

## Screenshots

### Orders Dashboard
<img width="1382" height="1568" alt="SCR-20260329-jmfd-blurred" src="https://github.com/user-attachments/assets/1f1fe880-8481-468a-90d0-b7f755a66525" />

### Spending Analysis
<img width="506" height="802" alt="SCR-20260329-jlxa" src="https://github.com/user-attachments/assets/1d405dca-f37c-4753-8292-f26e916aa66a" />

---

## Features

- **Multi-Gmail support** — connect multiple Gmail accounts to a single dashboard
- **Gmail OAuth** — read-only access, connects in one click
- **AI classification** — Claude identifies order confirmations, shipping updates, and delivery confirmations
- **Structured extraction** — vendor, order ID, items, price, tracking number, carrier, estimated delivery
- **Live dashboard** — filterable order list (All / Ordered / Shipped / Delivered) with expandable cards
- **Spending Analysis** — 6 chart breakdowns: by month, month of year, week of month, week of year, product category, and top vendors
- **Date range picker** — filter all spending charts by any date range
- **Auto-sync** — background sync every 30 minutes; manual Sync Now and Reset & Re-sync buttons
- **Reset & Re-sync** — wipe and reprocess all emails from scratch

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, React Query, Recharts |
| Backend | FastAPI (Python), SQLAlchemy 2.0 |
| Database | PostgreSQL (Supabase) |
| AI | Anthropic Claude (`claude-sonnet-4-6`) |
| Email | Gmail API (read-only OAuth2 + PKCE) |
| Auth | Google OAuth2 → encrypted session cookie (Fernet) |
| Hosting | Vercel (frontend) + Render (backend) |

---

## Prerequisites

- **Python 3.11+** — `python3 --version`
- **Node.js 18+** — `node --version`
- **Google Cloud account** — for Gmail API credentials (free)
- **Anthropic API key** — from [console.anthropic.com](https://console.anthropic.com)
- **PostgreSQL database** — [Supabase free tier](https://supabase.com) recommended

---

## Local Development

### 1. Clone the repo

```bash
git clone https://github.com/ganapathy-r-balaji/email-tracker.git
cd email-tracker
```

### 2. Google Cloud Console setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. `email-tracker`)
3. **Enable Gmail API**: APIs & Services → Library → search "Gmail API" → Enable
4. **Configure OAuth consent screen**:
   - APIs & Services → OAuth consent screen → User type: **External** → Create
   - Fill in App name, support email, developer email → Save
   - Add your Gmail address under **Test users**
5. **Create OAuth credentials**:
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
   - Authorized JavaScript origins: `http://localhost:3000`
   - Copy the **Client ID** and **Client Secret**

### 3. Configure environment variables

```bash
# backend/.env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_generated_secret_here

DATABASE_URL=postgresql://user:password@host:5432/dbname
FRONTEND_URL=http://localhost:3000
EMAIL_SYNC_MAX_RESULTS=500
OAUTHLIB_INSECURE_TRANSPORT=1
```

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4. Start the backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:3000`.

---

## Deployment

| Service | Purpose | Cost |
|---|---|---|
| [Vercel](https://vercel.com) | Frontend (Next.js) | Free |
| [Render](https://render.com) | Backend (FastAPI) | Free tier |
| [Supabase](https://supabase.com) | PostgreSQL database | Free tier |

**Environment variables required on Render:**

| Key | Value |
|---|---|
| `DATABASE_URL` | Supabase session pooler URI |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `GOOGLE_REDIRECT_URI` | `https://your-api.onrender.com/auth/google/callback` |
| `ANTHROPIC_API_KEY` | From Anthropic console |
| `SECRET_KEY` | Random 32-byte hex string |
| `FRONTEND_URL` | Your Vercel app URL |
| `EMAIL_SYNC_MAX_RESULTS` | `1000` (recommended) |

**After deploying:**
- Add the Render callback URL to Google Cloud Console → Authorized redirect URIs
- Add the Vercel URL to Google Cloud Console → Authorized JavaScript origins

---

## Project Structure

```
email-tracker/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLAlchemy engine + startup migration
│   ├── models.py            # ORM models: User, GmailAccount, Order, Item, Shipment, EmailLog
│   ├── auth_utils.py        # Fernet token encryption, session cookies
│   ├── scheduler.py         # APScheduler 30-min background sync
│   ├── routers/
│   │   ├── auth.py          # Google OAuth2 + PKCE flow
│   │   ├── accounts.py      # /api/accounts — list + disconnect Gmail accounts
│   │   ├── orders.py        # /api/orders, /api/stats/summary
│   │   ├── spending.py      # /api/stats/spending — 6 breakdown charts
│   │   └── sync.py          # /api/sync pipeline orchestration
│   ├── services/
│   │   ├── gmail.py         # Gmail API + recursive MIME parser
│   │   ├── classifier.py    # Claude email classification
│   │   ├── extractor.py     # Claude structured data extraction
│   │   └── linker.py        # Match emails to existing orders
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx              # Landing page
    │   ├── dashboard/page.tsx    # Main dashboard
    │   ├── spending/page.tsx     # Spending analysis page
    │   └── error.tsx             # Error boundary
    ├── components/
    │   ├── OrderCard.tsx         # Expandable order card
    │   ├── StatusBadge.tsx       # Color-coded status pill
    │   ├── StatsBar.tsx          # Summary stat tiles
    │   ├── SyncButton.tsx        # Sync trigger button
    │   ├── Toast.tsx             # Notification toast
    │   ├── ConnectedAccounts.tsx # Multi-Gmail account panel
    │   └── spending/             # Spending chart components
    └── lib/
        ├── api.ts                # Typed Axios client
        └── providers.tsx         # React Query provider
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/google` | Redirect to Google OAuth consent |
| `GET` | `/auth/google/callback` | OAuth callback — sets session cookie |
| `GET` | `/auth/logout` | Clear session, redirect to frontend |
| `GET` | `/api/me` | Current user info |
| `GET` | `/api/accounts` | List connected Gmail accounts |
| `DELETE` | `/api/accounts/{id}` | Disconnect a Gmail account |
| `POST` | `/api/sync` | Trigger email sync (background) |
| `POST` | `/api/sync/reset` | Clear all data and re-sync from scratch |
| `GET` | `/api/sync/status` | Last sync timestamp |
| `GET` | `/api/orders` | Paginated order list (`?page&per_page&status`) |
| `GET` | `/api/orders/{id}` | Order detail with items + shipments |
| `GET` | `/api/stats/summary` | Dashboard summary stats |
| `GET` | `/api/stats/spending` | Spending breakdown (`?start_date&end_date`) |

---

## How the AI Pipeline Works

```
Gmail API (search order-related emails by subject keywords)
        ↓
Email fetcher (decode MIME, extract plain text)
        ↓
Claude classifier → order_confirmation / shipping_update / delivery_confirmation / irrelevant
        ↓ (skip irrelevant)
Claude extractor → { vendor, order_id, items[], price, tracking_number, carrier, delivery_date }
        ↓
Order linker → match to existing order by order_id → tracking_number → vendor+date
        ↓
PostgreSQL (upsert Order, Items, Shipment) + EmailLog (deduplication)
```

- **Classification** uses 2000-char truncation, 150 max tokens → fast and cheap
- **Extraction** uses 8000-char body, 1024 max tokens → accurate structured data
- **Deduplication** via `email_log.gmail_message_id` — each email processed exactly once
- **Multi-account** — all connected Gmail accounts synced in a single pipeline run

---

## Security

- **Read-only Gmail scope** — `gmail.readonly` only; the app can never send or delete emails
- **PKCE** — Proof Key for Code Exchange enforced on all OAuth flows
- **Encrypted token storage** — OAuth tokens AES-encrypted (Fernet) before storing in database
- **Email bodies never stored** — only structured extracted fields are persisted
- **Session cookies** — `httponly`, `secure`, `samesite=none` in production

---

## Roadmap

- [ ] Outlook / Microsoft 365 support
- [ ] Real-time carrier tracking API integration
- [ ] Return window reminders
- [ ] Yahoo Mail support (IMAP)
- [ ] iOS / Android app
- [ ] Export spending data to CSV
