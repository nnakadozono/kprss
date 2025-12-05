# kprss
## Overview
kprss logs into a target site, scrapes articles, stores metadata in a local SQLite DB, saves images, optionally uploads files to Dropbox, and writes an RSS feed.

## Prerequisites
- Python 3.8+
- Python packages: requests, beautifulsoup4, feedgen, pytz, dropbox
Install with:
```sh
# shell
pip install -r requirements.txt || pip install requests beautifulsoup4 feedgen pytz dropbox
```

## Configuration
Copy and edit the environment template:
```sh
cp myenv_template.sh myenv.sh
```
Set values in `myenv.sh`:
- KPLONG — long site name
- KPSHORT — short site name (used for DB table)
- KPUSR, KPPSW — site credentials
- KPDB — path to SQLite DB
- KP_DBX_ACCESS_TOKEN — Dropbox access token (optional)
- KPRSS — output RSS filename

Do not commit `myenv.sh` (it's in .gitignore).

## Running
- Create `run.sh` based on `run_template.sh`
```sh
./run.sh
```

## Database
- The main articles table is named after `KPSHORT`.
- `photo_chart` holds image/chart metadata and Dropbox links.
Inspect with sqlite3:
```sh
sqlite3 "$KPDB"
.sqlite> .tables
sqlite> .schema  
sqlite> select key from tablename limit 20;  
sqlite> select key, url, date, dayid, title, photo, chart from tablename order by date desc limit 50;  
sqlite> .quit
```

## Dropbox (optional)
If `KP_DBX_ACCESS_TOKEN` is set the script will upload images and the generated RSS file and store/get shared links.

## Notes
- Cookies may be saved (cookies.pkl) to reuse sessions.
- Temporary image files removed after upload.
- Check `run_template.sh` and `myenv_template.sh` for examples.

## Files of interest
- `kprss.py` — main script (login, scrape, DB, RSS, Dropbox helpers)
- `run.sh`, `run_template.sh` — runners
- `myenv_template.sh`, `myenv.sh` — environment config
- `.gitignore` — ignored files (db, images, cookies, etc.)

## License
Add your project