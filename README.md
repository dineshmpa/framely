# Framely — Twibbonize-style profile picture frames

Create a campaign by uploading a transparent PNG frame, share the link, and let supporters
add their own photo underneath, adjust it, and download a ready-to-post profile picture.

## Features
- **Create campaigns**: upload a PNG frame (validated server-side: real PNG, 400–4000 px, ≤10 MB, must contain transparency), title + description.
- **Shareable campaign page** (`/c/<slug>`) with Open Graph tags for link previews.
- **Photo editor** (100% client-side, photos never leave the device): drag, mouse-wheel / pinch zoom, two-finger rotate, zoom & rotate sliders, flip, background colour, keyboard nudging, drag-and-drop upload.
- **Circular preview** showing how the result looks as a round profile picture.
- **Download** full-resolution PNG at the frame's native size; native **Share** on mobile (Web Share API); WhatsApp / X / Facebook / LinkedIn share links.
- **Explore page** with search and sort by most used / newest; view & download counters.
- **Private manage link** (shown after creating) to edit title/description or delete the campaign — no accounts needed.

## Free hosting on GitHub Pages
The repo deploys a static version of the site to GitHub Pages on every push to `main`
(`.github/workflows/pages.yml` → `build_static.py`).

- **Add a campaign**: upload a transparent PNG to [`frames/`](frames/) (optionally with a `.json` for title/description). See [`frames/README.md`](frames/README.md).
- Supporters get the full editor and download/share, all client-side.
- `/try/` lets anyone test their own PNG frame locally in the browser.
- Not available on Pages (needs the Flask server): creating campaigns from the website, manage links, use counters.
- One-time setup: **Settings → Pages → Source: GitHub Actions**.

Build locally: `.venv/bin/python build_static.py --site-url https://<user>.github.io/<repo>` → `_site/`.

## Run the full Flask app locally
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py                 # dev server on http://localhost:5000
# or production:
.venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

## Docker
```bash
docker build -t framely .
docker run -p 8000:8000 -v framely-data:/data -e SECRET_KEY=change-me framely
```

## Configuration
| Env var | Default | Purpose |
|---|---|---|
| `FRAMELY_DATA_DIR` | `./data` | SQLite DB + uploaded frames |
| `SECRET_KEY` | random per start | Flask session signing (set it in production) |
| `PORT` | `5000` | Port for `python app.py` |

Sample frames for testing are in `samples/` (`opaque-invalid.png` demonstrates the transparency check).
