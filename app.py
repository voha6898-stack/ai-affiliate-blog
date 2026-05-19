"""
AI Affiliate Blog — Flask Web App
Deploy mien phi tren Render.com
He thong AI tu dong dang bai qua /api/publish
"""
import os
import json
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort, redirect, url_for

app = Flask(__name__)

# API key bao ve endpoint /api/publish
API_SECRET = os.getenv("BLOG_API_SECRET", "change-this-secret-key")
DB_PATH = os.getenv("DB_PATH", "blog.db")


# ─── DATABASE ────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            meta_description TEXT DEFAULT '',
            keyword TEXT DEFAULT '',
            niche TEXT DEFAULT '',
            word_count INTEGER DEFAULT 0,
            affiliate_links_count INTEGER DEFAULT 0,
            seo_score INTEGER DEFAULT 0,
            published_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_slug ON articles(slug);
        CREATE INDEX IF NOT EXISTS idx_niche ON articles(niche);
    """)
    db.commit()
    db.close()


# ─── ROUTES ──────────────────────────────────────────────────

@app.route("/")
def homepage():
    db = get_db()
    articles = db.execute(
        "SELECT id,title,slug,meta_description,keyword,niche,word_count,published_at "
        "FROM articles ORDER BY published_at DESC LIMIT 20"
    ).fetchall()
    db.close()
    return render_template("index.html", articles=articles, site_name=os.getenv("SITE_NAME","AI Affiliate Blog"))


@app.route("/article/<slug>")
def article(slug):
    db = get_db()
    row = db.execute("SELECT * FROM articles WHERE slug=?", (slug,)).fetchone()
    db.close()
    if not row:
        abort(404)
    return render_template("article.html", article=dict(row), site_name=os.getenv("SITE_NAME","AI Affiliate Blog"))


@app.route("/niche/<niche>")
def niche_page(niche):
    db = get_db()
    articles = db.execute(
        "SELECT id,title,slug,meta_description,keyword,word_count,published_at "
        "FROM articles WHERE niche=? ORDER BY published_at DESC",
        (niche,)
    ).fetchall()
    db.close()
    return render_template("index.html", articles=articles, niche=niche,
                           site_name=os.getenv("SITE_NAME","AI Affiliate Blog"))


@app.route("/sitemap.xml")
def sitemap():
    db = get_db()
    articles = db.execute("SELECT slug, updated_at FROM articles").fetchall()
    db.close()
    base = os.getenv("SITE_URL", request.host_url.rstrip("/"))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>\n'
    for a in articles:
        xml += f'  <url><loc>{base}/article/{a["slug"]}</loc><lastmod>{a["updated_at"][:10]}</lastmod><priority>0.8</priority></url>\n'
    xml += '</urlset>'
    return app.response_class(xml, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    base = os.getenv("SITE_URL", request.host_url.rstrip("/"))
    txt = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    return app.response_class(txt, mimetype="text/plain")


# ─── API ENDPOINT (he thong AI dang bai) ─────────────────────

@app.route("/api/publish", methods=["POST"])
def api_publish():
    """
    AI system dang bai qua endpoint nay.
    Header: X-API-Key: <BLOG_API_SECRET>
    Body JSON: { title, slug, content, meta_description, keyword, niche, word_count, affiliate_links_count }
    """
    # Xac thuc
    api_key = request.headers.get("X-API-Key", "")
    if api_key != API_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "Missing title or content"}), 400

    slug = data.get("slug") or _make_slug(data["title"])

    db = get_db()
    try:
        db.execute("""
            INSERT INTO articles (title, slug, content, meta_description, keyword,
                niche, word_count, affiliate_links_count)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(slug) DO UPDATE SET
                title=excluded.title, content=excluded.content,
                meta_description=excluded.meta_description,
                word_count=excluded.word_count,
                updated_at=CURRENT_TIMESTAMP
        """, (
            data["title"], slug, data["content"],
            data.get("meta_description",""), data.get("keyword",""),
            data.get("niche",""), data.get("word_count",0),
            data.get("affiliate_links_count",0)
        ))
        db.commit()

        article_url = f"{os.getenv('SITE_URL', '')}/article/{slug}"
        return jsonify({
            "success": True,
            "slug": slug,
            "url": article_url,
            "message": "Article published successfully"
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/api/articles")
def api_articles():
    """Danh sach bai viet (public)."""
    db = get_db()
    rows = db.execute(
        "SELECT id,title,slug,keyword,niche,word_count,published_at FROM articles ORDER BY published_at DESC LIMIT 50"
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/stats")
def api_stats():
    """Thong ke nhanh."""
    db = get_db()
    stats = db.execute("""
        SELECT COUNT(*) as total_articles,
               SUM(word_count) as total_words,
               SUM(affiliate_links_count) as total_links,
               AVG(seo_score) as avg_seo
        FROM articles
    """).fetchone()
    db.close()
    return jsonify(dict(stats))


# ─── HELPER ──────────────────────────────────────────────────

def _make_slug(title: str) -> str:
    import re
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s[:60]


# ─── STARTUP ─────────────────────────────────────────────────

init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Blog running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
