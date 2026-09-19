import os
import random
import string
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_basicauth import BasicAuth
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# Database
database_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session / cookie hardening
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Enable in production behind HTTPS:
# app.config["SESSION_COOKIE_SECURE"] = True

# Basic Auth for /admin
app.config["BASIC_AUTH_USERNAME"] = os.environ.get("ADMIN_USERNAME", "admin")
app.config["BASIC_AUTH_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "bitfreshers2026")

SEAT_LIMIT = 200

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
db = SQLAlchemy(app)
basic_auth = BasicAuth(app)
csrf = CSRFProtect(app)

# Rate limiter — prevents brute-force & spam
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# Encryption (Fernet symmetric — for gift card codes at rest)
# ---------------------------------------------------------------------------
# Generate once:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Then set ENCRYPTION_KEY in your environment variables.
_enc_key = os.environ.get("ENCRYPTION_KEY")
if not _enc_key:
    # Auto-generate for local dev (data won't survive key change)
    _enc_key = Fernet.generate_key().decode()
    print("[WARNING] No ENCRYPTION_KEY set -- using ephemeral key (fine for local dev)")

fernet = Fernet(_enc_key.encode() if isinstance(_enc_key, str) else _enc_key)


def encrypt(plain_text: str) -> str:
    """Encrypt a string and return URL-safe base64 ciphertext."""
    return fernet.encrypt(plain_text.encode()).decode()


def decrypt(cipher_text: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    try:
        return fernet.decrypt(cipher_text.encode()).decode()
    except Exception:
        return "••••••••"  # graceful fallback

# ---------------------------------------------------------------------------
# Security Headers (applied to every response)
# ---------------------------------------------------------------------------
@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none';"
    )
    # Enable HSTS in production (uncomment when behind HTTPS):
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def generate_entry_code():
    """Generate a unique 8-character alphanumeric entry code like BIT-A3X9K2M7."""
    while True:
        code = "BIT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Registration.query.filter_by(entry_code=code).first():
            return code

# ---------------------------------------------------------------------------
# Database Model
# ---------------------------------------------------------------------------
class Registration(db.Model):
    __tablename__ = "registrations"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    usn = db.Column(db.String(50), nullable=False, unique=True)
    phone = db.Column(db.String(15), nullable=False, unique=True)
    branch = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(10), nullable=False)
    gift_card_code_enc = db.Column(db.Text, nullable=False)   # encrypted
    entry_code = db.Column(db.String(20), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_gift_card_code(self) -> str:
        """Decrypt and return the gift card code."""
        return decrypt(self.gift_card_code_enc)

    def get_masked_gift_card(self) -> str:
        """Return a masked version — only last 4 chars visible."""
        code = self.get_gift_card_code()
        if len(code) <= 4:
            return "••••"
        return "•" * (len(code) - 4) + code[-4:]

    def __repr__(self):
        return f"<Registration {self.usn} — {self.full_name}>"

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
@limiter.limit("30 per minute")
def index():
    seats_taken = Registration.query.count()
    seats_left = max(0, SEAT_LIMIT - seats_taken)
    return render_template("index.html", seats_left=seats_left, seats_taken=seats_taken)


@app.route("/register", methods=["POST"])
@limiter.limit("5 per minute")  # strict: 5 submissions per minute per IP
def register():
    full_name = request.form.get("full_name", "").strip()
    usn = request.form.get("usn", "").strip().upper()
    phone = request.form.get("phone", "").strip()
    branch = request.form.get("branch", "").strip()
    year = request.form.get("year", "").strip()
    gift_card_code = request.form.get("gift_card_code", "").strip()

    # Basic validation
    if not all([full_name, usn, phone, branch, year, gift_card_code]):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index"))

    # Validate year
    if year not in ("1st Year", "2nd Year"):
        flash("Only 1st and 2nd year students can register.", "error")
        return redirect(url_for("index"))

    # Validate phone
    if not phone.isdigit() or len(phone) != 10:
        flash("Please enter a valid 10-digit phone number.", "error")
        return redirect(url_for("index"))

    # Check seat limit
    if Registration.query.count() >= SEAT_LIMIT:
        flash("Sorry, all 200 seats are full! Registrations are closed.", "error")
        return redirect(url_for("index"))

    # Check duplicates (generic messages to avoid info leakage)
    if Registration.query.filter_by(usn=usn).first():
        flash("This USN is already registered.", "error")
        return redirect(url_for("index"))

    if Registration.query.filter_by(phone=phone).first():
        flash("This phone number is already registered.", "error")
        return redirect(url_for("index"))

    # Encrypt gift card code before storing
    encrypted_code = encrypt(gift_card_code)

    # Generate unique entry code
    entry_code = generate_entry_code()

    entry = Registration(
        full_name=full_name,
        usn=usn,
        phone=phone,
        branch=branch,
        year=year,
        gift_card_code_enc=encrypted_code,
        entry_code=entry_code,
    )
    db.session.add(entry)
    db.session.commit()

    flash(
        f"🎉 You're registered, {full_name.split()[0]}! "
        f"Your entry code is: {entry_code} — "
        f"Screenshot this! You'll need it at the door.",
        "success",
    )
    return redirect(url_for("index"))


@app.route("/admin")
@basic_auth.required
@limiter.limit("10 per minute")
def admin():
    registrations = Registration.query.order_by(Registration.created_at.desc()).all()
    seats_left = max(0, SEAT_LIMIT - len(registrations))
    return render_template(
        "admin.html",
        registrations=registrations,
        seats_left=seats_left,
        seat_limit=SEAT_LIMIT,
    )

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(429)
def ratelimit_handler(e):
    flash("Too many requests. Please wait a moment and try again.", "error")
    return redirect(url_for("index"))

# ---------------------------------------------------------------------------
# Create tables
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
