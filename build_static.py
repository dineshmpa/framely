"""Build the static GitHub Pages version of Framely.

Every PNG in frames/ becomes a campaign page at c/<name>/. Optional frames/<name>.json
supplies {"title": ..., "description": ...}. Output goes to _site/.

Usage: python build_static.py [--out _site] [--site-url https://user.github.io/repo]
"""
import argparse
import json
import os
import re
import shutil
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, UnidentifiedImageError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR = os.path.join(BASE_DIR, "frames")
MAX_BYTES = 10 * 1024 * 1024
MIN_SIDE, MAX_SIDE = 400, 4000


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def validate(path):
    if os.path.getsize(path) > MAX_BYTES:
        return None, "larger than 10 MB"
    try:
        img = Image.open(path)
        img.load()
    except (UnidentifiedImageError, OSError):
        return None, "not a readable image"
    if img.format != "PNG":
        return None, f"is {img.format}, not PNG"
    w, h = img.size
    if min(w, h) < MIN_SIDE or max(w, h) > MAX_SIDE:
        return None, f"is {w}x{h}px; each side must be {MIN_SIDE}-{MAX_SIDE}px"
    if img.convert("RGBA").getchannel("A").getextrema()[0] == 255:
        return None, "has no transparent area"
    return (w, h), None


def load_campaigns():
    campaigns, errors, slugs = [], [], set()
    for name in sorted(os.listdir(FRAMES_DIR)):
        stem, ext = os.path.splitext(name)
        if ext.lower() != ".png":
            continue
        path = os.path.join(FRAMES_DIR, name)
        size, err = validate(path)
        if err:
            errors.append(f"frames/{name}: {err}")
            continue
        slug = slugify(stem) or "frame"
        if slug in slugs:
            errors.append(f"frames/{name}: duplicate campaign name '{slug}'")
            continue
        slugs.add(slug)
        meta = {}
        meta_path = os.path.join(FRAMES_DIR, stem + ".json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                errors.append(f"frames/{stem}.json: invalid JSON ({e})")
                continue
        campaigns.append({
            "slug": slug,
            "source": path,
            "frame_file": f"{slug}.png",
            "title": str(meta.get("title") or stem.replace("-", " ").replace("_", " ").title())[:80],
            "description": str(meta.get("description") or "")[:500],
            "width": size[0],
            "height": size[1],
            "mtime": os.path.getmtime(path),
        })
    return campaigns, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "_site"))
    ap.add_argument("--site-url", default=os.environ.get("SITE_URL", ""))
    args = ap.parse_args()
    site_url = args.site_url.rstrip("/")

    campaigns, errors = load_campaigns()
    for e in errors:
        print(f"::error::{e}" if os.environ.get("GITHUB_ACTIONS") else f"ERROR: {e}", file=sys.stderr)
    if errors:
        sys.exit(1)

    out = args.out
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "frames"))
    shutil.copytree(os.path.join(BASE_DIR, "static"), os.path.join(out, "static"))
    for c in campaigns:
        shutil.copy2(c["source"], os.path.join(out, "frames", c["frame_file"]))

    env = Environment(
        loader=FileSystemLoader(os.path.join(BASE_DIR, "static_site", "templates")),
        autoescape=select_autoescape(["html"]),
    )

    def write(rel_path, template, **ctx):
        depth = rel_path.count("/")
        html = env.get_template(template).render(root="../" * depth, site_url=site_url, **ctx)
        dest = os.path.join(out, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(html)

    write("index.html", "index.html", campaigns=sorted(campaigns, key=lambda c: -c["mtime"]))
    write("try/index.html", "try.html")
    write("404.html", "404.html")
    for c in campaigns:
        c["link"] = f"{site_url}/c/{c['slug']}/" if site_url else ""
        write(f"c/{c['slug']}/index.html", "campaign.html", c=c)
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(f"Built {len(campaigns)} campaign(s) into {out}")


if __name__ == "__main__":
    main()
