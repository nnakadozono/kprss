# Hosting

The reader should be hosted from the existing `kprss` AWS environment rather
than a separate stack. Keep the generated site under a prefix in the existing
S3 bucket and expose that prefix through CloudFront.

Recommended object layout:

```text
s3://YOUR_KPRSS_BUCKET/
  reader/
    site/
      index.html
      assets/
      data/
        manifest.json
        latest.json
        YYYY-MM-DD.json
```

Set CloudFront's S3 origin path to `/reader/site` so the public URLs stay clean:

```text
https://DISTRIBUTION.cloudfront.net/
https://DISTRIBUTION.cloudfront.net/data/latest.json
```

## Terraform ownership

The hosting infrastructure should live in the `kprss` repository Terraform,
because that repository already owns the bucket, Lambda, IAM, and Terraform
state.

The Terraform in `infra/` owns these resources:

- CloudFront distribution with the existing S3 bucket as origin
- Origin Access Control for private S3 reads
- bucket policy that allows CloudFront to read only `reader/site/*`
- CloudFront Function for Basic Auth on viewer requests
- cache policies:
  - short TTL for `/`, `/index.html`, `/data/manifest.json`, `/data/latest.json`
  - long TTL for `/assets/*` and `/data/YYYY-MM-DD.json`

## Terraform apply

Set the Basic Auth credentials in ignored `infra/terraform.tfvars`:

```hcl
reader_basic_auth_username = "YOUR_USERNAME"
reader_basic_auth_password = "YOUR_PASSWORD"
```

This value is sensitive and should stay in ignored local files and local
Terraform state. Do not commit `terraform.tfvars` or `terraform.tfstate`.

From `infra/`:

```sh
terraform validate
terraform plan
terraform apply
```

After apply, copy the distribution id into `reader/.env`:

```sh
terraform output reader_cloudfront_distribution_id
terraform output reader_cloudfront_domain_name
```

## Manual deploy

Configure `.env`:

```sh
KPRSS_READER_SITE_BUCKET=YOUR_KPRSS_BUCKET
KPRSS_READER_SITE_PREFIX=reader/site
KPRSS_READER_CLOUDFRONT_DISTRIBUTION_ID=YOUR_DISTRIBUTION_ID
KPRSS_READER_CLOUDFRONT_DOMAIN_NAME=YOUR_DISTRIBUTION.cloudfront.net
```

Deploy everything from the local database:

```sh
scripts/deploy_site.sh
```

Deploy only app files without touching `data/`:

```sh
scripts/deploy_site.sh --app-only
```

Generate and deploy only `data/`:

```sh
scripts/deploy_site.sh --data-only
```

Daily `YYYY-MM-DD.json` files are uploaded without deleting older files already
in S3. `latest.json` and `manifest.json` are overwritten.

Use `--app-only` when the local database may be stale and you only want to
publish HTML/CSS/JS changes.

## Lambda JSON generation

The existing `kprss` fetch/write Lambda generates reader JSON after the SQLite
database has been updated and uploaded.

The Lambda refreshes the latest `KPRSS_READER_DAYS` dates. Existing daily JSON
files are preserved; only missing daily files and the latest date file are
uploaded. `latest.json` and `manifest.json` are overwritten on every run.

`manifest.json` is built from the S3 list of existing daily JSON files plus the
newly generated dates, so older dates remain visible after they fall outside the
latest refresh window.

For Lambda, set these as SSM parameters under `KP_SSM_PREFIX` if you need values
other than the defaults:

```text
KPRSS_READER_DAYS=10
KPRSS_READER_SITE_PREFIX=reader/site
```

The Lambda role also needs `s3:ListBucket` on the reader data prefix so it can
build `manifest.json` from the existing S3 daily JSON files. This is managed by
the Terraform IAM policy in `infra/`.
