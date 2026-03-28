# AI Email Package Tracker

Track every order and shipment automatically by connecting your Gmail account. Claude AI classifies and extracts structured data from order, shipping, and delivery emails — no copy-pasting tracking numbers needed.

## Features

- **Gmail OAuth** — read-only access, connects in one click
- **AI classification** — Claude identifies order confirmations, shipping updates, and delivery confirmations
- **Structured extraction** — vendor, order ID, items, price, tracking number, carrier, estimated delivery
- **Live dashboard** — filterable order list with status badges and expandable cards
- **Auto-sync** — background sync every 30 minutes; manual "Sync Now" button
- **Spend stats** — total orders, pending deliveries, delivered count

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, React Query |
| Backend | FastAPI (Python 3.11+), SQLAlchemy |
| Database | SQLite (local) |
| AI | Anthropic Claude (`claude-sonnet-4-6`) |
| Email | Gmail API (read-only OAuth2) |
| Auth | Google OAuth2 → encrypted session cookie |

---

## Prerequisites

- **Python 3.11+** — `python3 --version`
- **Node.js 18+** — `node --version`
- **Google Cloud account** — for Gmail API credentials (free)
- **Anthropic API key** — from [console.anthropic.com](https://console.anthropic.com)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/Email-tracker.git
cd Email-tracker
```

### 2. Google Cloud Console setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. `email-tracker`)
3. **Enable Gmail API**: APIs & Services → Library → search "Gmail API" → Enable
4. **Configure OAuth consent screen**:
   - APIs & Services → OAuth consent screen
   - User type: **External** → Create
   - Fill in App name, support email, developer email → Save
   - On the **Test users** step: add your own Gmail address
5. **Create OAuth credentials**:
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
   - Authorized JavaScript origins: `http://localhost:3000`
   - Click Create → copy the **Client ID** and **Client Secret**

### 3. Configure environment variables

```bash
cp .env.example backend/.env
```

Open `backend/.env` and fill in:

```bash
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Generate a random secret key:
# python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_generated_secret_here

DATABASE_URL=sqlite:///./tracker.db
FRONTEND_URL=http://localhost:3000
SYNC_INTERVAL_MINUTES=30
EMAIL_SYNC_MAX_RESULTS=200
```

### 4. Start the backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
uvicorn main:app --reload --port 8000
```

The API will be at `http://localhost:8000`. You can explore the auto-generated docs at `http://localhost:8000/docs`.

### 5. Start the frontend

Open a new terminal tab:

```bash
cd frontend

# Create local env file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Install dependencies
npm install

# Run
npm run dev
```

The app will be at **http://localhost:3000**.

---

## Usage

1. Visit `http://localhost:3000`
2. Click **Connect Gmail** → authorize read-only access
3. You'll land on the dashboard — click **Sync Now** to scan your inbox
4. Orders appear with vendor, status, price, and tracking info
5. Click any order card to expand and see items + shipment details
6. The background scheduler re-syncs automatically every 30 minutes

---

## Project Structure

```
Email-tracker/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # SQLAlchemy engine (SQLite + WAL mode)
│   ├── models.py            # ORM models: User, Order, Item, Shipment, EmailLog
│   ├── auth_utils.py        # Fernet token encryption, session cookies
│   ├── scheduler.py         # APScheduler 30-min background sync
│   ├── routers/
│   │   ├── auth.py          # /auth/google OAuth flow
│   │   ├── orders.py        # /api/orders, /api/stats/summary
│   │   └── sync.py          # /api/sync pipeline orchestration
│   ├── services/
│   │   ├── gmail.py         # Gmail API + recursive MIME parser
│   │   ├── classifier.py    # Claude classification (4 categories)
│   │   ├── extractor.py     # Claude structured data extraction
│   │   └── linker.py        # Match emails to existing orders
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx          # Landing page
    │   ├── dashboard/page.tsx# Main dashboard
    │   └── error.tsx         # Error boundary
    ├── components/
    │   ├── OrderCard.tsx     # Expandable order card
    │   ├── StatusBadge.tsx   # Color-coded status pill
    │   ├── StatsBar.tsx      # Summary stat tiles
    │   ├── SyncButton.tsx    # Sync trigger button
    │   └── Toast.tsx         # Notification toast
    └── lib/
        ├── api.ts            # Typed Axios client
        └── providers.tsx     # React Query provider
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/google` | Redirect to Google OAuth consent |
| `GET` | `/auth/google/callback` | OAuth callback — sets session cookie |
| `GET` | `/auth/logout` | Clear session, redirect to frontend |
| `GET` | `/api/me` | Current user info |
| `POST` | `/api/sync` | Trigger email sync (background) |
| `GET` | `/api/sync/status` | Last sync timestamp |
| `GET` | `/api/orders` | Paginated order list (`?page&per_page&status&vendor`) |
| `GET` | `/api/orders/{id}` | Order detail with all items + shipments |
| `GET` | `/api/stats/summary` | Dashboard summary stats |

Full interactive docs: `http://localhost:8000/docs`

---

## How the AI Pipeline Works

```
Gmail API (search order emails)
        ↓
Email fetcher (decode MIME, extract text)
        ↓
Claude classifier → order_confirmation / shipping_update / delivery_confirmation / irrelevant
        ↓ (skip irrelevant)
Claude extractor → { vendor, order_id, items[], price, tracking_number, carrier, delivery_date }
        ↓
Order linker → match to existing order by order_id → tracking_number → vendor+date
        ↓
SQLite (upsert Order, Items, Shipment) + EmailLog (deduplication)
```

- **Classification** uses 2000-char email truncation, 150 max tokens → fast + cheap
- **Extraction** uses 8000-char body, 1024 max tokens → accurate structured data
- **Deduplication** via `email_log.gmail_message_id` — each email is processed exactly once

---

## Security

- **Read-only Gmail scope** — `gmail.readonly` only; the app can never send or delete emails
- **Encrypted token storage** — OAuth tokens are AES-encrypted (Fernet) before writing to SQLite
- **Email bodies never stored** — only structured extracted fields are persisted
- **CSRF protection** — OAuth state parameter verified via signed cookie
- **Session cookies** — `httponly`, `samesite=lax`; change to `secure=True` behind HTTPS in production

---

## Roadmap

- [ ] Yahoo Mail support (IMAP + OAuth)
- [ ] Return window reminders
- [ ] Real-time carrier tracking API integration
- [ ] Monthly spend analytics by vendor
- [ ] Outlook / Microsoft 365 support
- [ ] iOS app (React Native + Expo)
