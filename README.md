# kprss
## Overview
kprss logs into a target site, scrapes articles, stores metadata in a local SQLite DB, saves images, optionally uploads files to Dropbox, and writes an RSS feed.

## Prerequisites
- Python 3.12
- Python packages: requests, beautifulsoup4, feedgen, pytz, dropbox, boto3
Install with:
```sh
# shell
pip install -r requirements.txt
```

## Configuration
Copy and edit the environment template:
```sh
cp myenv_template.sh myenv.sh
```
Set values in `myenv.sh`:
- KP_SSM_PREFIX - AWS Parameter Store Prefix
- KPLONG — long site name
- KPSHORT — short site name (used for DB table)
- KPUSR, KPPSW — site credentials
- KPDB — path to SQLite DB
- KP_DBX_ACCESS_TOKEN — Dropbox access token (optional)
- KPRSS — output RSS filename
- KP_S3_BUCKET - AWS S3 Bucket Name
- KPRSS_READER_DAYS - number of latest article dates to refresh for the static reader
- KPRSS_READER_SITE_PREFIX - S3 prefix for the static reader site, usually `reader/site`

Do not commit `myenv.sh` (it's in .gitignore).

Or, set only `KP_SSM_PREFIX` in `myenv_minimum.sh`


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
- `reader/` — static web reader and JSON generator for collected articles
- `run.sh`, `run_template.sh` — runners
- `myenv_template.sh`, `myenv.sh` — environment config
- `.gitignore` — ignored files (db, images, cookies, etc.)

## Run on AWS Lambda
Small AWS-based pipeline that runs a Python Lambda (kprss.py) on a schedule to process or update a packaged database.

### Architecture summary
- **Lambda** function executes kprss.py. 
  - Required: Python 3.12, ARM64 runtime, 512 MB memory, and a KP_SSM_PREFIX as a environment variable.
- Deployment artifacts (function.zip and database) are stored in an **S3** bucket.
- Runtime configuration values are stored in **AWS Systems Manager Parameter Store**.
- Lambda assumes an **IAM role** with permissions to access S3, Parameter Store, and CloudWatch Logs.
- **EventBridge** rule triggers the Lambda on a daily schedule.
- **CloudWatch** collects and stores Lambda execution logs for observability and troubleshooting.
- Optional reader settings can be stored under the same SSM prefix:
  - `KPRSS_READER_DAYS` controls how many recent article dates are refreshed.
  - `KPRSS_READER_SITE_PREFIX` controls the S3 site prefix, usually `reader/site`.

### Deployment / operational notes
- The `build_lambda.sh` builds and packages the Lambda as function.zip and upload it (alongside the database zip) to the configured S3 bucket.
- After updating the database, the Lambda generates reader JSON for the latest `KPRSS_READER_DAYS` dates and uploads only missing daily files plus fresh `latest.json` and `manifest.json`. Existing older daily JSON files are left in S3.


## License
Add your project
