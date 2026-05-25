import json
import sqlite3
from pathlib import Path


ARTICLE_COLUMNS = {"key", "url", "date", "dayid", "title", "article", "photo", "chart", "media", "category"}
ASSET_COLUMNS = {"fkey", "i", "url", "text", "url_dbx"}


def rows_to_dicts(cursor, rows):
    names = [description[0] for description in cursor.description]
    return [dict(zip(names, row)) for row in rows]


def normalize_title(title):
    parts = [part.strip() for part in (title or "").splitlines()]
    parts = [part for part in parts if part]
    return " | ".join(parts) or "(no title)"


def quote_identifier(name):
    if not name:
        raise ValueError("Missing SQLite identifier.")
    return '"' + name.replace('"', '""') + '"'


def table_names(conn):
    cursor = conn.execute(
        """
        select name
        from sqlite_master
        where type = 'table' and name not like 'sqlite_%'
        order by name
        """
    )
    return [row[0] for row in cursor.fetchall()]


def table_columns(conn, table_name):
    cursor = conn.execute(f"pragma table_info({quote_identifier(table_name)})")
    return {row[1] for row in cursor.fetchall()}


def infer_table(conn, required_columns, preferred=None):
    if preferred:
        columns = table_columns(conn, preferred)
        missing = required_columns - columns
        if missing:
            missing_columns = ", ".join(sorted(missing))
            raise ValueError(f"Configured table is missing required columns: {missing_columns}")
        return preferred

    matches = [
        name
        for name in table_names(conn)
        if required_columns.issubset(table_columns(conn, name))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        required = ", ".join(sorted(required_columns))
        raise ValueError(f"Could not infer table with required columns: {required}")
    raise ValueError("Could not infer table because multiple candidates match.")


def maybe_infer_table(conn, required_columns, preferred=None):
    if preferred:
        return infer_table(conn, required_columns, preferred=preferred)

    matches = [
        name
        for name in table_names(conn)
        if required_columns.issubset(table_columns(conn, name))
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def fetch_dates(conn, article_table):
    cursor = conn.execute(
        f"""
        select distinct date
        from {quote_identifier(article_table)}
        where date is not null and date != ''
        order by date desc
        """
    )
    return [row[0] for row in cursor.fetchall()]


def fetch_articles(conn, date, article_table, asset_table):
    article_cursor = conn.execute(
        f"""
        select key as id, url, date, dayid, title, article, photo, chart, media, category
        from {quote_identifier(article_table)}
        where date = ?
        order by dayid desc, key desc
        """,
        (date,),
    )
    articles = rows_to_dicts(article_cursor, article_cursor.fetchall())

    images_by_article = {}
    if asset_table:
        image_cursor = conn.execute(
            f"""
            select fkey, i, coalesce(url_dbx, url) as url, coalesce(text, '') as caption
            from {quote_identifier(asset_table)}
            where fkey in (
                select key from {quote_identifier(article_table)} where date = ?
            )
            order by fkey, i
            """,
            (date,),
        )
        for row in rows_to_dicts(image_cursor, image_cursor.fetchall()):
            if not row["url"]:
                continue
            images_by_article.setdefault(row["fkey"], []).append(
                {
                    "url": row["url"],
                    "caption": row["caption"],
                }
            )

    for article in articles:
        article["images"] = images_by_article.get(article["id"], [])
        article["article"] = (article["article"] or "").lstrip()
        article["title"] = normalize_title(article["title"])
        article["category"] = article["category"] or ""
        article["media"] = article["media"] or ""

    return articles


def json_bytes(payload):
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(payload))


def generate_reader_payloads(conn, article_table, asset_table="photo_chart", days=10):
    dates = fetch_dates(conn, article_table)[:days]
    if not dates:
        raise ValueError("No article dates found in database.")

    daily_payloads = {}
    for date in dates:
        daily_payloads[date] = {
            "date": date,
            "articles": fetch_articles(conn, date, article_table, asset_table),
        }

    return dates, daily_payloads


def generate_reader_payloads_from_db(db_path, article_table=None, asset_table=None, days=10):
    conn = sqlite3.connect(db_path)
    try:
        resolved_article_table = infer_table(conn, ARTICLE_COLUMNS, preferred=article_table)
        resolved_asset_table = maybe_infer_table(conn, ASSET_COLUMNS, preferred=asset_table)
        return generate_reader_payloads(
            conn,
            resolved_article_table,
            asset_table=resolved_asset_table,
            days=days,
        )
    finally:
        conn.close()
