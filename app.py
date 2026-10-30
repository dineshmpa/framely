import hashlib
import io
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, url_for,
)
from PIL import Image, UnidentifiedImageError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("FRAMELY_DATA_DIR", os.path.join(BASE_DIR, "data"))
FRAMES_DIR = os.path.join(DATA_DIR, "frames")
DB_PATH = os.path.join(DATA_DIR, "framely.db")

MAX_FRAME_BYTES = 10 * 1024 * 1024
MIN_FRAME_SIDE = 400
MAX_FRAME_SIDE = 4000

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = MAX_FRAME_BYTES + 1024 * 1024

os.makedirs(FRAMES_DIR, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    frame_file TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    manage_token_hash TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    uses INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)


init_db()


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-")
    return slug or "frame"


def unique_slug(db, title):
    base = slugify(title)
    while True:
        slug = f"{base}-{secrets.token_hex(2)}"
        if not db.execute("SELECT 1 FROM campaigns WHERE slug = ?", (slug,)).fetchone():
            return slug


def get_campaign_or_404(slug):
    row = get_db().execute("SELECT * FROM campaigns WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        abort(404)
    return row


def validate_frame(file_storage):
    """Return (rgba_image, error_message)."""
    data = file_storage.read()
    if not data:
        return None, "Please choose a PNG frame to upload."
    if len(data) > MAX_FRAME_BYTES:
        return None, "Frame must be 10 MB or smaller."
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError):
        return None, "That file isn't a valid image."
    if img.format != "PNG":
        return None, "Frame must be a PNG file."
    w, h = img.size
    if min(w, h) < MIN_FRAME_SIDE:
        return None, f"Frame must be at least {MIN_FRAME_SIDE}×{MIN_FRAME_SIDE} px (got {w}×{h})."
    if max(w, h) > MAX_FRAME_SIDE:
        return None, f"Frame must be at most {MAX_FRAME_SIDE} px on each side (got {w}×{h})."
    rgba = img.convert("RGBA")
    alpha_min, _ = rgba.getchannel("A").getextrema()
    if alpha_min == 255:
        return None, ("Frame has no transparent area. Export your PNG with a transparent "
                      "hole where the photo should show through.")
    return rgba, None


@app.context_processor
def inject_now():
    return {"year": datetime.now().year}


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "popular")
    order = "uses DESC, views DESC" if sort == "popular" else "created_at DESC"
    db = get_db()
    if q:
        rows = db.execute(
            f"SELECT * FROM campaigns WHERE title LIKE ? OR description LIKE ? ORDER BY {order} LIMIT 60",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute(f"SELECT * FROM campaigns ORDER BY {order} LIMIT 60").fetchall()
    return render_template("index.html", campaigns=rows, q=q, sort=sort)


@app.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_template("create.html")

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    errors = []
    if not title:
        errors.append("Title is required.")
    if len(title) > 80:
        errors.append("Title must be 80 characters or fewer.")
    if len(description) > 500:
        errors.append("Description must be 500 characters or fewer.")

    frame = request.files.get("frame")
    img = None
    if frame is None or not frame.filename:
        errors.append("Please choose a PNG frame to upload.")
    else:
        img, err = validate_frame(frame)
        if err:
            errors.append(err)

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("create.html", title=title, description=description), 400

    db = get_db()
    slug = unique_slug(db, title)
    filename = f"{slug}-{secrets.token_hex(4)}.png"
    img.save(os.path.join(FRAMES_DIR, filename), "PNG", optimize=True)

    token = secrets.token_urlsafe(18)
    db.execute(
        "INSERT INTO campaigns (slug, title, description, frame_file, width, height, "
        "manage_token_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (slug, title, description, filename, img.width, img.height, hash_token(token),
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return redirect(url_for("manage", slug=slug, token=token, new=1))


@app.route("/c/<slug>")
def campaign(slug):
    row = get_campaign_or_404(slug)
    db = get_db()
    db.execute("UPDATE campaigns SET views = views + 1 WHERE id = ?", (row["id"],))
    db.commit()
    return render_template("campaign.html", c=row)


@app.route("/c/<slug>/manage", methods=["GET", "POST"])
def manage(slug):
    row = get_campaign_or_404(slug)
    token = request.values.get("token", "")
    if not token or not secrets.compare_digest(hash_token(token), row["manage_token_hash"]):
        abort(403)

    if request.method == "POST":
        action = request.form.get("action")
        db = get_db()
        if action == "delete":
            db.execute("DELETE FROM campaigns WHERE id = ?", (row["id"],))
            db.commit()
            try:
                os.remove(os.path.join(FRAMES_DIR, row["frame_file"]))
            except FileNotFoundError:
                pass
            flash(f"Campaign “{row['title']}” was deleted.", "success")
            return redirect(url_for("index"))
        if action == "update":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            if not title or len(title) > 80 or len(description) > 500:
                flash("Title is required (max 80 chars); description max 500 chars.", "error")
            else:
                db.execute("UPDATE campaigns SET title = ?, description = ? WHERE id = ?",
                           (title, description, row["id"]))
                db.commit()
                flash("Campaign updated.", "success")
            return redirect(url_for("manage", slug=slug, token=token))

    return render_template("manage.html", c=row, token=token, is_new=request.args.get("new") == "1")


@app.route("/api/c/<slug>/use", methods=["POST"])
def record_use(slug):
    row = get_campaign_or_404(slug)
    db = get_db()
    db.execute("UPDATE campaigns SET uses = uses + 1 WHERE id = ?", (row["id"],))
    db.commit()
    return jsonify(uses=row["uses"] + 1)


@app.route("/frames/<path:filename>")
def frame_file(filename):
    resp = send_from_directory(FRAMES_DIR, filename, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@app.errorhandler(413)
def too_large(_e):
    flash("Upload is too large. Frames must be 10 MB or smaller.", "error")
    return redirect(url_for("create"))


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="We couldn't find that page or campaign."), 404


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, message="That manage link is invalid."), 403


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
