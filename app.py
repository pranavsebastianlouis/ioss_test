from __future__ import annotations
import os
import re
import string
import random
from datetime import datetime
from urllib.parse import urlparse

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy

# -----------------------
# Config
# -----------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mysecretkey")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------
# Model
# -----------------------


class ShortURL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    original_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    clicks = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "code": self.code,
            "original_url": self.original_url,
            "created_at": self.created_at.isoformat(),
            "clicks": self.clicks,
        }


# -----------------------
# Utilities
# -----------------------
CODE_CHARS = string.ascii_letters + string.digits


def valid_url(url: str) -> bool:
    try:
        p = urlparse(url.strip())
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def generate_code(length: int = 6) -> str:
    # Ensure uniqueness
    while True:
        code = "".join(random.choice(CODE_CHARS) for _ in range(length))
        if not ShortURL.query.filter_by(code=code).first():
            return code
        

CUSTOM_CODE_REGEX = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")

# -----------------------
# Routes
# -----------------------


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        original = request.form.get("original_url", "").strip()
        custom = request.form.get("custom_code", "").strip()

        if not valid_url(original):
            flash(
                "Please enter a valid URL starting with http:// or https://",
                "danger"
            )
            return redirect(url_for("index"))

        if custom:
            if not CUSTOM_CODE_REGEX.match(custom):
                flash(
                    (
                        "Custom alias must be 3–32 characters: "
                        "letters, numbers, _ or -"
                    ),
                    "warning"
                )
                return redirect(url_for("index"))
            if ShortURL.query.filter_by(code=custom).first():
                flash("That alias is already taken. Try another.", "warning")
                return redirect(url_for("index"))
            code = custom
        else:
            code = generate_code()

        record = ShortURL(code=code, original_url=original)
        db.session.add(record)
        db.session.commit()

        short_url = url_for("follow", code=code, _external=True)
        flash("Short URL created!", "success")
        return render_template(
            "index.html",
            short_url=short_url,
            original_url=original,
            code=code
        )

    # GET
    latest = (
        ShortURL.query
        .order_by(ShortURL.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template("index.html", latest=latest)


@app.route("/<code>")
def follow(code):
    row = ShortURL.query.filter_by(code=code).first()
    if not row:
        abort(404)
    row.clicks += 1
    db.session.commit()
    return redirect(row.original_url, code=302)


# Simple JSON API (optional nice-to-have)
@app.route("/api/shorten", methods=["POST"])
def api_shorten():
    data = request.get_json(force=True, silent=True) or {}
    original = (data.get("url") or "").strip()
    custom = (data.get("code") or "").strip()

    if not valid_url(original):
        return jsonify({"error": "invalid_url"}), 400

    if custom:
        if not CUSTOM_CODE_REGEX.match(custom):
            return jsonify({"error": "invalid_custom_code"}), 400
        if ShortURL.query.filter_by(code=custom).first():
            return jsonify({"error": "code_taken"}), 409
        code = custom
    else:
        code = generate_code()

    record = ShortURL(code=code, original_url=original)
    db.session.add(record)
    db.session.commit()
    return jsonify({
        "code": code,
        "short_url": url_for("follow", code=code, _external=True)
    }), 201


@app.route("/healthz")
def healthz():
    return "ok", 200

# -----------------------
# App bootstrap
# -----------------------


@app.before_request
def init_db():
    db.create_all()


if __name__ == "__main__":
    # Bind to 0.0.0.0 for Docker/Render
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
