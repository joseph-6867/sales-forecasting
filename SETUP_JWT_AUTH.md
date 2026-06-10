# JWT Authentication Setup Guide

This guide walks through deploying the HTTP/JWT authentication architecture for your sales forecasting platform.

## Architecture Overview

- **Streamlit Frontend** (`app.py`): Web UI for registration and login
- **FastAPI Backend** (`backend/server.py`): Issues JWT tokens after password verification
- **Supabase Database**: Stores user profiles and application data (no auth system)
- **PostgreSQL Schema** (`database/schema.sql`): User table with SHA256 password hashing

---

## Step 1: Deploy Schema Changes to Supabase

The schema has been updated to remove the foreign-key constraint to Supabase's auth system and add a `password_hash` column for app-managed password storage.

### 1a. Open Supabase SQL Editor

1. Go to [https://supabase.com/dashboard](https://supabase.com/dashboard)
2. Select your project
3. Click **SQL Editor** (left sidebar)
4. Click **New Query**

### 1b. Copy and Run Schema

1. Open `database/schema.sql` in VS Code
2. Copy the entire content
3. Paste into Supabase SQL Editor
4. Click **Run** button (or `Ctrl+Enter`)

Expected output:
```
CREATE TABLE
CREATE INDEX
```

### 1c. Verify Schema in Supabase

1. Go to **Table Editor** (left sidebar)
2. Click on `public.users` table
3. Verify columns:
   - `id` (UUID, auto-generated)
   - `email` (TEXT, unique)
   - `password_hash` (TEXT)
   - `full_name` (TEXT)
   - `role` (TEXT)
   - `created_at` (TIMESTAMP)

**No foreign-key constraint should appear.**

---

## Step 2: Configure Environment Variables

Ensure your `.env` file contains:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SHARED_EMAIL_BASE=josephmanoj894@gmail.com
JWT_SECRET=your-secret-key-change-in-production
```

**Important**: In production, use a strong, random JWT_SECRET and keep it secure.

---

## Step 3: Start the FastAPI Backend

The auth server must run before Streamlit can register/login users.

### 3a. Open a New Terminal

In VS Code:
1. Press `Ctrl+`` (backtick)
2. Select **New Terminal**

### 3b. Activate Virtual Environment

```bash
# Windows
.\.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3c. Start the Server

```bash
python -m uvicorn backend.server:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 [CTRL+C to quit]
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
```

### 3d. Verify Health Check (Optional)

In another terminal:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok"}
```

---

## Step 4: Start Streamlit Frontend

In a **separate** terminal:

### 4a. Activate Virtual Environment

```bash
# Windows
.\.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 4b. Run Streamlit

```bash
streamlit run app.py
```

Expected output:
```
You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
  Network URL: http://X.X.X.X:8501
```

---

## Step 5: Test Registration & Login

### 5a. Register a New Account

1. Open browser to http://localhost:8501
2. Go to **Register** tab
3. Fill in form:
   - **Full Name**: Test User
   - **Account Name**: testuser
   - **Role**: analyst
   - **Password**: TestPassword123
   - **Confirm Password**: TestPassword123
4. Click **Create Account**

Expected result:
- ✅ "Account created successfully" message appears
- ✅ Redirects to Dashboard
- ✅ No "User not allowed" error

### 5b. Login with the Account

1. Log out by clicking **Logout** (if visible in sidebar)
2. Go to **Login** tab
3. Fill in form:
   - **Account Name**: testuser
   - **Password**: TestPassword123
4. Click **Login**

Expected result:
- ✅ "Login successful" message appears
- ✅ Redirects to Dashboard
- ✅ Session shows `user_id`, `email`, `full_name`, `role`

### 5c. Verify JWT Token in Session

Open browser DevTools (`F12`) → Console:

```javascript
// In Streamlit session (internally stored)
// You can see JWT token in auth server logs when login occurs
```

In FastAPI terminal, look for:
```
POST /auth/login - "200 OK"
```

---

## Step 6: Troubleshooting

### Error: "Connection refused (port 8000)"

- Verify FastAPI backend is running
- Check that port 8000 is not blocked by firewall
- Ensure `backend/server.py` exists and is error-free

### Error: "Could not find the 'password_hash' column"

- Schema changes may not have been applied to Supabase
- Verify in Supabase Table Editor that `password_hash` column exists
- If missing, re-run the schema.sql queries

### Error: "User not allowed"

- This error indicates you're still using Supabase auth
- Verify `backend/auth.py` is calling `http://localhost:8000/auth/register` and `http://localhost:8000/auth/login`
- Check that `app.py` is capturing `jwt_token` from the HTTP response

### Error: "rate_limit exceeded"

- Supabase auth had rate limits; this should no longer occur with app-managed auth
- If you still see this, check that you're not making redundant API calls to Supabase auth

### JWT Token Expired

- Default expiry is 24 hours
- Tokens are issued on login/registration
- To extend expiry, modify `JWT_EXPIRY_HOURS` in `backend/server.py`

---

## Step 7: Next Steps - Extend JWT to Data APIs

Once registration/login work, all data API calls should include the JWT token:

In `backend/database.py`:

```python
from backend.auth import get_auth_headers

# When making Supabase API calls:
headers = get_auth_headers()  # Returns {"Authorization": f"Bearer {token}"}
response = supabase_client.table("users").select("*").execute(headers=headers)
```

This ensures future role-based access controls can be enforced at the data layer.

---

## File Summary

| File | Purpose | Status |
|------|---------|--------|
| `database/schema.sql` | PostgreSQL user table without FK constraint | ✅ Ready to deploy |
| `backend/server.py` | FastAPI auth microservice | ✅ Implemented |
| `backend/auth.py` | Streamlit HTTP client for auth server | ✅ Updated |
| `app.py` | Login/register UI with JWT capture | ✅ Updated |
| `.env` | Environment variables | ⚠️ Add JWT_SECRET |
| `requirements.txt` | Python dependencies | ✅ Updated with FastAPI/JWT |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      STREAMLIT FRONTEND                         │
│                        (port 8501)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  app.py: Registration/Login Forms                        │  │
│  │  - Captures JWT token from backend response             │  │
│  │  - Stores in st.session_state.jwt_token                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬─────────────────────────────────────────────────┘
                 │ HTTP POST
                 │ /auth/register or /auth/login
                 │
┌────────────────▼─────────────────────────────────────────────────┐
│                   FASTAPI BACKEND                                │
│                    (port 8000)                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  backend/server.py: Authentication Endpoints            │  │
│  │  - Verifies password (SHA256 hash)                      │  │
│  │  - Issues JWT token (24-hour expiry)                    │  │
│  │  - Returns user data and token in JSON response         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬─────────────────────────────────────────────────┘
                 │ Supabase PostgREST API
                 │ (stores/retrieves user data)
                 │
┌────────────────▼─────────────────────────────────────────────────┐
│              SUPABASE DATABASE                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL public.users table                          │  │
│  │  - id (UUID)                                            │  │
│  │  - email (shared Gmail alias)                           │  │
│  │  - password_hash (SHA256)                               │  │
│  │  - full_name, role, created_at                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Support

For issues:
1. Check FastAPI terminal for error messages
2. Verify schema deployment in Supabase
3. Confirm `.env` variables are set correctly
4. Review troubleshooting section above
