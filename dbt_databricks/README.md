# parquet_databricks_demo

dbt project that transforms parquet files sitting in
`s3://jason-chletsos-parquet-dbt-demo/raw/` without copying them into
Databricks first. Staging views read the files in place with
`read_files(..., format => 'parquet')`; only the final aggregate
(`fct_daily_revenue`) is persisted, as a Delta table.

## Models

- `stg_customers`, `stg_products`, `stg_orders` — views over the raw S3
  parquet, typed columns; `stg_orders` adds `is_cancelled`.
- `fct_daily_revenue` — table, grain order_date x category x region,
  shipped/delivered orders only, gross_revenue = sum(quantity * unit_price).
- `models/staging/sources.yml` — documents the S3 origin. It is
  documentation-only until the external tables described in
  `setup/databricks_setup.md` are created (see the comment in that file).

## Prerequisites

1. Unity Catalog storage credential + external location for the bucket —
   see `setup/databricks_setup.md`. Required on serverless SQL warehouses;
   on classic warehouses an instance profile is an alternative.
2. Target schema exists (default `main.jason_chletsos_parquet_demo`).

## Runbook

All commands from this directory. `profiles.yml` lives here; always pass
`--profiles-dir .`. Do not use the bare `dbt` binary on PATH (it is
dbt-fusion); invoke dbt-core through python.

```sh
cd dbt_databricks

export DATABRICKS_HOST=<workspace-host, no https://>
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse-id>
export DATABRICKS_TOKEN=<pat>
# optional overrides (defaults shown)
export DATABRICKS_CATALOG=main
export DATABRICKS_SCHEMA=jason_chletsos_parquet_demo

python3 -m dbt.cli.main debug --profiles-dir .
python3 -m dbt.cli.main run --profiles-dir .
python3 -m dbt.cli.main test --profiles-dir .
```

Offline sanity check (no credentials needed; env vars have placeholder
defaults):

```sh
python3 -m dbt.cli.main parse --profiles-dir .
```

Known issue on this machine: the installed pandas 2.2.1 is binary-incompatible
with numpy 2.5.1, and databricks-sql-connector imports pandas at module load,
so any dbt command against this project fails at import time until that pair
is fixed. Workaround for offline parse only (parse never opens a connection,
so the stub is inert):

```sh
python3 -c "
import sys, types
sys.modules['pandas'] = types.ModuleType('pandas')
from dbt.cli.main import dbtRunner
raise SystemExit(0 if dbtRunner().invoke(['parse', '--profiles-dir', '.']).success else 1)
"
```

A live run needs a working pandas (for example pandas >= 2.2.2, which supports
numpy 2.x) or a separate virtualenv.
