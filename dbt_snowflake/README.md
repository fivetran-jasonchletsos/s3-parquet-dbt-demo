# dbt on Snowflake, parquet in S3

dbt project that transforms parquet files sitting in
`s3://jason-chletsos-parquet-dbt-demo/raw/` without copying them into
Snowflake. External tables (created by the `dbt_external_tables` package,
version 0.12.3) expose the parquet in place; the staging views and the
`fct_daily_revenue` table are built on top of them.

Database defaults to `JASON_CHLETSOS_PARQUET_DEMO`, schema to `RAW`; override
with the env vars below. `profiles.yml` lives in this directory, so every dbt
command takes `--profiles-dir .` and nothing touches `~/.dbt`.

## Environment variables

`profiles.yml` reads these (all have parse-safe defaults; set real values
before any live run):

- `SNOWFLAKE_ACCOUNT` — account locator, e.g. `myorg-my_account` (required for
  a live run; the checked-in default is a placeholder)
- `SNOWFLAKE_USER`
- `SNOWFLAKE_AUTHENTICATOR` (default `externalbrowser` — SSO via browser
  popup; no password is stored or read anywhere)
- `SNOWFLAKE_ROLE` (default `SALES_DEMO_ROLE`)
- `SNOWFLAKE_WAREHOUSE` (default `DEMO_WH`)
- `SNOWFLAKE_DATABASE` (default `JASON_CHLETSOS_PARQUET_DEMO`)
- `SNOWFLAKE_SCHEMA` (default `RAW`)

## Runbook (exact order)

1. Provision AWS: from `../terraform`, run `terraform apply` (creates the S3
   bucket, the parquet objects' home, and the IAM role Snowflake assumes;
   note the `snowflake_role_arn` output).
2. One-time Snowflake setup: run `setup/snowflake_setup.sql` as ACCOUNTADMIN,
   substituting the role ARN from step 1. Complete the two-step trust
   handshake: `DESC INTEGRATION` returns `STORAGE_AWS_IAM_USER_ARN` and
   `STORAGE_AWS_EXTERNAL_ID`, which go back into the IAM role trust policy on
   the AWS side before the stage can read the bucket.
3. Install packages:

       PYTHONPATH=tools/pandas_disabled python3 -m dbt.cli.main deps --profiles-dir .

4. Create/refresh the external tables over the S3 parquet:

       PYTHONPATH=tools/pandas_disabled python3 -m dbt.cli.main run-operation stage_external_sources --profiles-dir .

   Pass `--vars "ext_full_refresh: true"` to force recreation after schema
   changes.
5. Build models and run tests:

       PYTHONPATH=tools/pandas_disabled python3 -m dbt.cli.main build --profiles-dir .

## Notes for this machine

- `dbt` on PATH is dbt-fusion; always use `python3 -m dbt.cli.main`.
- The installed pandas is binary-incompatible with numpy and crashes on
  import; snowflake-connector-python imports it eagerly and only tolerates
  ImportError. `PYTHONPATH=tools/pandas_disabled` shadows pandas with a stub
  that raises ImportError, which the connector handles by disabling its
  optional pandas features (not needed for SQL models). On a machine with a
  healthy pandas install, drop the `PYTHONPATH` prefix.

## Layout

- `models/sources.yml` — external table definitions (one per entity) over
  subpaths of `@<db>.RAW.PARQUET_STAGE`; columns declared explicitly to match
  the data contract. Snowflake could instead derive them with `INFER_SCHEMA`.
- `models/staging/` — `stg_customers`, `stg_products`, `stg_orders` (views;
  `stg_orders` adds `is_cancelled`).
- `models/marts/fct_daily_revenue.sql` — table at order_date x category x
  region grain, shipped/delivered orders only.
- `models/schema.yml` — unique/not_null on primary keys, accepted_values on
  status, relationships from orders to both dimensions.
- `setup/snowflake_setup.sql` — storage integration, file format, stage,
  database, warehouse, grants.
