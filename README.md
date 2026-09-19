# BIT Freshers Party 2026 — Registration App 🎉

A lightweight Flask + PostgreSQL web app for collecting freshers party
registrations at **Bangalore Institute of Technology**.

## Tech Stack

| Layer     | Tech                               |
| --------- | ---------------------------------- |
| Backend   | Python 3.11+, Flask, SQLAlchemy    |
| Database  | PostgreSQL (Supabase / Render)     |
| Auth      | Flask-BasicAuth (admin dashboard)  |
| Server    | Gunicorn                           |
| Hosting   | Render (free tier)                 |

---

## Local Development

```bash
# 1. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run locally (uses SQLite by default)
python app.py
```

Visit **http://127.0.0.1:5000** for the registration form and
**http://127.0.0.1:5000/admin** for the admin dashboard
(default credentials: `admin` / `bitfreshers2026`).

---

## Deploy to Render (Free Tier) — Step by Step

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
# Create a repo on GitHub, then:
git remote add origin https://github.com/codestack-hub/bit-freshers-party.git
git push -u origin main
```

### 2. Create a PostgreSQL Database on Render
1. Go to [render.com](https://render.com) → **New +** → **PostgreSQL**.
2. Pick the **Free** plan, give it a name (e.g. `bit-freshers-db`), and click **Create Database**.
3. Once provisioned, copy the **Internal Database URL** (starts with `postgresql://…`).

### 3. Create the Web Service on Render
1. **New +** → **Web Service** → connect your GitHub repo.
2. Configure:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
3. Add **Environment Variables**:
   | Key              | Value                                         |
   | ---------------- | --------------------------------------------- |
   | `DATABASE_URL`   | *(paste the Internal Database URL from step 2)*|
   | `SECRET_KEY`     | *(any random string, e.g. `s3cR3t!k3y#2026`)* |
   | `ENCRYPTION_KEY` | *(see below — Fernet key for gift card encryption)* |
   | `ADMIN_USERNAME` | `admin` *(or your preferred username)*         |
   | `ADMIN_PASSWORD` | *(a strong password of your choice)*           |

   **Generate your encryption key** by running:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Copy the output and paste it as the `ENCRYPTION_KEY` value.

4. Click **Create Web Service**. Render will build and deploy automatically.

### 4. Done!
- **Registration form**: `https://your-app.onrender.com/`
- **Admin dashboard**: `https://your-app.onrender.com/admin`

---

## Environment Variables Reference

| Variable         | Required | Description                                | Default              |
| ---------------- | -------- | ------------------------------------------ | -------------------- |
| `DATABASE_URL`   | Yes      | PostgreSQL connection URI                  | `sqlite:///local.db` |
| `SECRET_KEY`     | Yes      | Flask session / CSRF secret key            | `change-me-…`        |
| `ENCRYPTION_KEY` | Yes*     | Fernet key for encrypting gift card codes  | Auto-generated (dev) |
| `ADMIN_USERNAME` | No       | Basic Auth username for `/admin`           | `admin`              |
| `ADMIN_PASSWORD` | No       | Basic Auth password for `/admin`           | `bitfreshers2026`    |

> *`ENCRYPTION_KEY` auto-generates for local dev, but **must** be set in production — otherwise data won't survive restarts.
