# kprss integration

This project has been moved into the `kprss` repository as `reader/`.

Suggested target layout:

```text
kprss/
  reader/
    public/
    scripts/
      generate_site.py
      deploy_site.sh
    docs/
    dist/        # ignored
```

Before future integration work, inspect and settle any uncommitted changes in
the `kprss` repository. Do not mix unrelated changes into the same working tree.

Integration checklist:

1. Keep `public/`, `scripts/`, `docs/`, `README.md`, `.env.sample`,
   `.gitignore`, and `AGENT.md` under `kprss/reader/`.
2. Use paths like `reader/scripts/...` if the
   scripts are run from the `kprss` repository root.
3. Keep `reader/dist/` ignored.
4. Add hosting infrastructure to the existing `kprss` Terraform, not to this
   reader project.
5. Deploy reader app files to `s3://$KPRSS_READER_SITE_BUCKET/$KPRSS_READER_SITE_PREFIX/`.
6. Generate reader JSON from the existing `kprss` fetch/write Lambda after the
   SQLite database update succeeds.

Manual deploy modes after integration:

```sh
reader/scripts/deploy_site.sh --app-only
reader/scripts/deploy_site.sh --data-only
reader/scripts/deploy_site.sh --full
```

Use `--app-only` for UI-only changes when the local database may be stale.
