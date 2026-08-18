# Can dbt transform parquet files stored in S3?

Yes. dbt does not move data — it compiles SQL and hands it to an engine, so
any engine that can read parquet in S3 can be the dbt backend, with no load
step into a warehouse. Snowflake does it with external tables over a storage
integration (created here by the `dbt_external_tables` package), Databricks
reads the S3 paths with `read_files(..., format => 'parquet')` through a Unity
Catalog external location, and DuckDB reads `s3://` paths directly via its
`httpfs` extension — that last one is the zero-infrastructure local proof.

Same data contract, same four models, same tests, three engines.

## Verified results

Live-tested 2026-08-18. Three runs, identical models, 15 of 15 build steps
passing on each (3 staging views, 1 fact table, 11 schema tests):

- DuckDB over the local files in `data/`
- DuckDB reading `s3://` directly via `httpfs`
- Snowflake via storage integration + external tables (`dbt_external_tables`)

Every run produced the same `fct_daily_revenue`: 3,005 rows, 735,258.78 gross
revenue, identical to the cent. The Databricks project is built and
parse-validated; its live run is pending a workspace with a Unity Catalog
external location (the IAM role it assumes is already provisioned in
Terraform).

Write-ups: the rendered site at
[fivetran-jasonchletsos.github.io/s3-parquet-dbt-demo](https://fivetran-jasonchletsos.github.io/s3-parquet-dbt-demo/),
the one-page PDF at `docs/dbt-parquet-s3-summary.pdf`, and the Slack drafts in
`deliverables/`.

## Architecture

```
data_generator/generate_parquet.py          (or a Fivetran connector — see fivetran/INGESTION.md)
        |
        v
s3://jason-chletsos-parquet-dbt-demo/raw/{customers,products,orders}/*.parquet
        |
        v
dbt on { DuckDB | Snowflake | Databricks }   -- engine reads the parquet in place
        |
        v
stg_customers, stg_products, stg_orders      (views, typed columns)
        |
        v
fct_daily_revenue                            (table: order_date x category x region,
                                              shipped/delivered only)
```

Where the outputs land: the raw parquet is never loaded anywhere, but model
outputs materialize in whatever the engine considers a table — the staging
views are stored SQL, and `fct_daily_revenue` is a native table (DuckDB file,
Snowflake table, Delta on Databricks). Writing model outputs back to S3 as
parquet or Iceberg is the natural follow-on pattern (dbt-duckdb can do it
today via external materializations; on Snowflake and Databricks, Iceberg
table materializations); it is not part of this demo.

## Repo map

- `data_generator/` — writes the sample parquet locally under `data/` (stdlib + pyarrow, deterministic seed).
- `data/` — the generated parquet: 500 customers, 50 products, 5,000 orders across 5 files (one each for customers and products, three for orders).
- `terraform/` — S3 bucket plus the IAM roles Snowflake and Databricks assume (two-phase apply for the trust handshakes).
- `upload/` — `upload_to_s3.sh`, syncs `data/` to the bucket's `raw/` prefix.
- `dbt_duckdb/` — dbt project on DuckDB; default target reads local files, `s3` variant reads the bucket.
- `dbt_snowflake/` — dbt project on Snowflake; external tables via `dbt_external_tables` + `setup/snowflake_setup.sql`.
- `dbt_databricks/` — dbt project on Databricks; `read_files` over S3 + `setup/databricks_setup.md` for Unity Catalog wiring.
- `fivetran/` — `INGESTION.md`, how the parquet gets into S3 (existing drops vs. Fivetran Managed Data Lake Service).

Each dbt project keeps its own `profiles.yml` and is run with `--profiles-dir .`,
so nothing touches `~/.dbt`. On this machine, always invoke dbt-core as
`python3 -m dbt.cli.main` — the bare `dbt` on PATH is dbt-fusion, a different
tool.

## Quickstart

### 1. Local proof, zero cloud setup

The data is already generated and checked in; the DuckDB project's default
target reads it from `data/` on disk:

```sh
cd dbt_duckdb
python3 -m dbt.cli.main build --profiles-dir .
```

Expected: 15 successes (3 staging views, 1 fact table, 11 tests). Inspect the
result in `parquet_demo.duckdb` per `dbt_duckdb/README.md`. To regenerate the
data first: `python3 data_generator/generate_parquet.py`.

### 2. Same files in S3

```sh
aws sso login --profile pokemon-app   # Jason's SSO profile; substitute your own
cd terraform && terraform init && terraform apply   # bucket + IAM roles
../upload/upload_to_s3.sh                           # data/ -> s3://.../raw/
```

Then run any engine against the bucket:

- DuckDB over S3: the `s3` target is already in `dbt_duckdb/profiles.yml`; build with `--target s3` (the source location defaults to the bucket on that target) per `dbt_duckdb/README.md`.
- Snowflake: follow the runbook in `dbt_snowflake/README.md` (one-time `setup/snowflake_setup.sql`, then `deps`, `stage_external_sources`, `build`).
- Databricks: follow `dbt_databricks/README.md` and `dbt_databricks/setup/databricks_setup.md` (Unity Catalog storage credential + external location, then `run` and `test`).

The Snowflake and Databricks runbooks include a documented workaround for this
machine's broken pandas install; it does not affect the DuckDB path.

## Data quality

Each project carries the same 11 schema tests, run as part of `dbt build`:

- Key integrity (8 tests): `unique` and `not_null` on `stg_customers.customer_id`,
  `stg_products.product_id`, and `stg_orders.order_id`; `not_null` on
  `fct_daily_revenue.order_date` and `fct_daily_revenue.gross_revenue`.
- Accepted values (1 test): `stg_orders.status` must be one of `placed`,
  `shipped`, `delivered`, `cancelled` — the fact table's shipped/delivered
  filter depends on this domain holding.
- Referential integrity (2 tests): every `stg_orders.customer_id` exists in
  `stg_customers` and every `stg_orders.product_id` exists in `stg_products`,
  so the fact table's inner joins cannot silently drop orders.

These tests validate the data after an engine can already read it. The natural
next layer is Great Expectations (GX Core) applying file-level expectations to
the raw parquet in S3 — row counts, column presence and types, value ranges —
before dbt runs at all; that is not implemented here, it is the honest next
step.

## Operating notes

Refreshing the data:

1. Regenerate: `python3 data_generator/generate_parquet.py` (deterministic seed;
   edit the generator to change volumes).
2. Upload: `upload/upload_to_s3.sh` syncs `data/` to `s3://.../raw/`.
3. Pick up the new files per engine:
   - DuckDB and Databricks read the files at query time — just rebuild.
   - Snowflake external tables track file metadata and must be refreshed:
     either re-run `stage_external_sources` per the Snowflake runbook, or run
     `ALTER EXTERNAL TABLE <db>.RAW.<CUSTOMERS or PRODUCTS or ORDERS> REFRESH;`
     for each table (auto-refresh is disabled because the account is not
     hosted on AWS).

Incremental models: this demo full-rebuilds because the volume is trivial, but
dbt incremental materializations work unchanged over these sources — the
engine owns the SQL, so an incremental `fct_daily_revenue` filtering on
`order_ts` compiles and runs the same way. The external-table refresh caveat
above still applies on Snowflake: new files must be visible to the external
table before an incremental run can see them.

Cost posture: the parquet is stored once in S3 (5,550 rows, negligible).
Snowflake external tables store no data — every query scans S3 — and the demo
warehouse is `DEMO_WH`, XSMALL with 60-second auto-suspend. Databricks would
bill SQL warehouse time the same way once a workspace runs it. DuckDB is free.

Teardown:

```sh
cd terraform && terraform destroy   # bucket (force_destroy handles objects) + both IAM roles
```

```sql
-- Snowflake, as ACCOUNTADMIN. Dropping the database removes the external
-- tables, stage, and file format with it.
drop database if exists JASON_CHLETSOS_PARQUET_DEMO;
drop warehouse if exists DEMO_WH;
drop integration if exists JASON_CHLETSOS_PARQUET_DEMO_S3_INT;
```

Local DuckDB artifacts are just files: delete `dbt_duckdb/parquet_demo.duckdb`
and `dbt_duckdb/parquet_demo_s3.duckdb`.

## Scale and limits

5,550 rows proves the mechanism, not the economics. Honest limits of the
raw-parquet-external-table pattern at volume:

- Every query rescans the files. External tables and `read_files` carry no
  micro-partitions, clustering, or table statistics, so there is no pruning
  beyond what the parquet footers and the path layout give you.
- Mitigations, in order: partition the S3 paths (e.g. by date) so engines can
  prune whole prefixes; move to Iceberg (what Fivetran MDLS lands), which adds
  file-level statistics, snapshots, and compaction; and past meaningful
  volume, materialize hot marts as native tables — which this demo already
  does for `fct_daily_revenue`.
- The pattern fits landing and staging zones best: raw data stays in one
  S3 copy, dbt reads it in place, and only curated aggregates take on
  warehouse-native storage.

## The Fivetran angle

The generator and upload script simulate parquet that already lands in S3.
In production, Fivetran's Managed Data Lake Service replaces both: connectors
write to your S3 bucket as maintained, parquet-backed Iceberg tables (initial
sync, incrementals, schema evolution, compaction), and Snowflake and Databricks
read those tables in place through their catalogs. The dbt projects are
unchanged — staging models point at the Iceberg tables instead of raw paths,
and everything downstream is identical. One copy of the data in S3 serves
every engine. With MDLS the Iceberg catalog also removes the manual refresh
step: engines reading through the catalog see new files as new table
snapshots. Details and the claims to verify before presenting are in
`fivetran/INGESTION.md`.

### When an SE reaches for this

Point at a lake destination when:

- The customer wants one copy of the data that multiple engines (or future
  engines) query, without re-ingesting to switch.
- Data ownership or residency requires the data to live in the customer's own
  bucket, not inside a vendor's storage.
- The architecture is warehouse-optional or warehouse-later: transform in
  place now, choose or change compute afterward.

The warehouse destination is still right when:

- One warehouse serves all workloads and its native storage features
  (clustering, micro-partitions, zero-copy clones) carry the query load.
- The team wants no lake-side moving parts: no catalogs, external tables, or
  IAM trust handshakes to operate.
- Interactive latency on large scans matters more than storage flexibility —
  native tables prune; raw external files do not.

Talk track: Fivetran lands governed Iceberg in the customer's bucket, and dbt
transforms it in place on whatever engine they already pay for. The data is
theirs, in their account, and the compute is swappable.
