# dbt + DuckDB over parquet files

dbt transforms parquet files in place. DuckDB reads them with `read_parquet()`
via dbt-duckdb's `meta.external_location` source pattern -- no copy or load
step. Default target reads the local files in `../data`; the S3 variant below
reads the same files straight out of the bucket.

## Run

From this directory:

```
python3 -m dbt.cli.main build --profiles-dir .
```

Note: use `python3 -m dbt.cli.main`, not the bare `dbt` on PATH (that binary
is dbt-fusion, a different tool).

This builds:

- `stg_customers`, `stg_products`, `stg_orders` (views over the parquet files)
- `fct_daily_revenue` (table: order_date x category x region, shipped/delivered only)

and runs the schema tests (unique/not_null keys, accepted status values,
relationships from orders to both dimensions).

Results land in `parquet_demo.duckdb` in this directory. Inspect:

```
python3 -c "import duckdb; print(duckdb.connect('parquet_demo.duckdb').sql('select * from fct_daily_revenue order by gross_revenue desc limit 10'))"
```

## S3 variant: read the parquet directly from the bucket

The same files live at `s3://jason-chletsos-parquet-dbt-demo/raw/{customers,products,orders}/*.parquet`
(us-east-1). DuckDB's `httpfs` extension reads them in place; a DuckDB secret
of type `s3` with `PROVIDER credential_chain` picks up credentials from the
`pokemon-app` AWS profile (SSO). Substitute your own profile name in
`profiles.yml` if you are not Jason.

The `s3` target is already defined in `profiles.yml` (httpfs extension plus a
`credential_chain` secret with `chain: sso`). The source location default is
target-aware: the `s3` target reads the bucket, every other target reads the
local files, so `--target s3` cannot silently fall back to local data. Use
`--vars '{data_root: ...}'` only to point at a different location.

1. Sign in: `aws sso login --profile pokemon-app`

2. Run against the bucket:

```
python3 -m dbt.cli.main build --profiles-dir . --target s3
```

Verified 2026-08-18: 15/15 models and tests pass reading straight from S3.

The engine scans the parquet in S3 directly; nothing is staged or copied into
a warehouse first. The default target stays on local files so the demo runs
offline.
