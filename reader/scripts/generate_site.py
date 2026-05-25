#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR.parent))

from reader.generator import (  # noqa: E402
    generate_reader_payloads_from_db,
    write_json,
)


def load_dotenv(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args():
    parser = argparse.ArgumentParser(description="Generate the static kprss reader site.")
    parser.add_argument("--db", default=os.environ.get("KPDB"), help="Path to source SQLite database.")
    parser.add_argument(
        "--article-table",
        default=os.environ.get("KPRSS_READER_ARTICLE_TABLE") or os.environ.get("KPSHORT"),
        help="Source article table name. Defaults to KPRSS_READER_ARTICLE_TABLE or KPSHORT.",
    )
    parser.add_argument(
        "--asset-table",
        default=os.environ.get("KPRSS_READER_ASSET_TABLE"),
        help="Source image/asset table name. If omitted, the generator tries to infer it.",
    )
    parser.add_argument("--out", default=str(ROOT_DIR / "dist"), help="Output directory.")
    parser.add_argument("--public", default=str(ROOT_DIR / "public"), help="Static public directory.")
    parser.add_argument("--days", type=int, default=10, help="Number of latest dates to generate.")
    return parser.parse_args()


def resolve_reader_path(path):
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return ROOT_DIR / resolved


def resolve_db_path(path):
    resolved = Path(path)
    if resolved.is_absolute() or resolved.exists():
        return resolved
    return ROOT_DIR / resolved


def copy_public(public_dir, out_dir):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(public_dir, out_dir)


def main():
    load_dotenv(ROOT_DIR / ".env")
    args = parse_args()
    if not args.db:
        raise SystemExit("Database path is required. Pass --db or set KPDB.")

    db_path = resolve_db_path(args.db)
    public_dir = resolve_reader_path(args.public)
    out_dir = resolve_reader_path(args.out)

    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    if not public_dir.exists():
        raise SystemExit(f"Public directory not found: {public_dir}")

    copy_public(public_dir, out_dir)

    try:
        dates, daily_payloads = generate_reader_payloads_from_db(
            db_path,
            article_table=args.article_table,
            asset_table=args.asset_table,
            days=args.days,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    data_dir = out_dir / "data"
    for date, payload in daily_payloads.items():
        write_json(data_dir / f"{date}.json", payload)

    latest_date = dates[0]
    write_json(data_dir / "manifest.json", {"latestDate": latest_date, "dates": dates})
    shutil.copyfile(data_dir / f"{latest_date}.json", data_dir / "latest.json")

    print(f"Generated {len(dates)} days into {out_dir}")


if __name__ == "__main__":
    main()
