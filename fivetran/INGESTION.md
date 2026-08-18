# How the parquet gets into S3

This repo demonstrates dbt transforming parquet files in S3 without copying them into a
warehouse first. That only works if the parquet is in S3 to begin with. There are two ways
that happens, and they lead to the same transform pattern.

Target layout for this demo:

```
s3://jason-chletsos-parquet-dbt-demo/raw/customers/*.parquet
s3://jason-chletsos-parquet-dbt-demo/raw/products/*.parquet
s3://jason-chletsos-parquet-dbt-demo/raw/orders/*.parquet
```

Region us-east-1.

## Path 1: Files already land in S3 (what this repo simulates)

Plenty of teams already have parquet arriving in S3 from an existing process: application
exports, an upstream vendor drop, a Spark job, a Kinesis Firehose sink. This repo stands in
for that world with two scripts:

1. `data_generator/generate_parquet.py` writes the customers, products, and orders parquet
   files locally under `data/` (pyarrow, fixed schemas, referentially consistent keys).
2. The upload script in `upload/` copies `data/` to
   `s3://jason-chletsos-parquet-dbt-demo/raw/` using an AWS profile with write
   access to the bucket.

From there, each of the three dbt projects (`dbt_duckdb`, `dbt_snowflake`,
`dbt_databricks`) reads the parquet in place — see each project's README for the
engine-specific mechanism (DuckDB `read_parquet` over `s3://` paths, Snowflake external
stage/tables, Databricks reading the S3 path through its catalog). The staging models and
`fct_daily_revenue` are identical across all three. No COPY INTO, no ingestion step inside
the warehouse: the files are the source, the engine is the compute.

The limitation of this path is that everything upstream of S3 is your problem: extraction
from source systems, incremental logic, schema drift, small-file buildup, retries. The
generator script papers over all of that because it is a demo.

## Path 2: Fivetran-managed landing (Managed Data Lake Service)

Fivetran can own the entire left side of the diagram. Instead of pointing a connector at a
warehouse, you point it at an S3-based data lake destination. Fivetran's Managed Data Lake
Service writes connector data to your S3 bucket as parquet-backed Iceberg tables and
maintains them: it handles the initial sync, incremental updates, schema evolution as the
source changes, and table maintenance such as compaction. You get governed Iceberg tables
in your own bucket rather than a pile of raw files.

The query engines then read those tables in place:

- Snowflake queries the Iceberg tables through a catalog integration (external Iceberg
  tables pointing at the catalog Fivetran maintains). Confirm the exact catalog integration
  type for your setup against current Fivetran and Snowflake docs before demoing — the
  supported catalog options have changed over time.
- Databricks reads them through Unity Catalog.

The dbt projects do not change. The staging models select from the Iceberg tables instead
of raw parquet paths, and everything downstream (`fct_daily_revenue`, the schema tests) is
identical. Same pattern as Path 1: the data is transformed where it lands, zero warehouse
copy. The difference is that Fivetran replaces the generator and upload scripts with real
connectors, and replaces "a directory of parquet files" with maintained Iceberg tables.

Both engines only ever read what Fivetran wrote — one copy of the data in S3 serves
Snowflake, Databricks, and DuckDB-style engines alike.

### What to verify before presenting

These are the claims in this doc that should be re-checked against the Fivetran dashboard
or current docs rather than asserted from memory:

- Exact current name and packaging of the Managed Data Lake Service and which destinations
  it covers (S3 with Iceberg is the relevant one here).
- Which Iceberg catalog Fivetran exposes and the exact Snowflake catalog integration type
  it pairs with.
- Unity Catalog setup steps on the Databricks side (whether tables surface automatically or
  require a one-time catalog/external location configuration).
- Compaction and other table-maintenance behavior — confirm scope and defaults in current
  docs before stating specifics to a customer.
