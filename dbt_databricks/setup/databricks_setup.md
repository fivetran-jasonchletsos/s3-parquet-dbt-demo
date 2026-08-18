# Databricks setup for reading S3 parquet in place

One-time Unity Catalog wiring so a SQL warehouse can read
`s3://jason-chletsos-parquet-dbt-demo/raw/` directly. Region us-east-1.

## 1. Storage credential (IAM role)

The IAM role comes from `../../terraform` (it grants `s3:GetObject` and
`s3:ListBucket` on `jason-chletsos-parquet-dbt-demo`). Databricks needs the
role's trust policy to allow the Unity Catalog master role
(`arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL`)
with the external ID set to your Databricks account ID. Add that trust
statement to the terraform role (or a dedicated copy of it), then:

```sql
-- Run as a metastore admin (or a user with CREATE STORAGE CREDENTIAL)
CREATE STORAGE CREDENTIAL jason_chletsos_parquet_demo_cred
WITH (
  AWS_IAM_ROLE 'arn:aws:iam::<AWS_ACCOUNT_ID>:role/<role-name-from-terraform-output>'
)
COMMENT 'Read-only access to jason-chletsos-parquet-dbt-demo';
```

After creating the credential, copy the External ID Databricks shows in
Catalog Explorer back into the IAM role trust policy if it was not set
up front (the console flow requires this round trip).

## 2. External location

```sql
CREATE EXTERNAL LOCATION jason_chletsos_parquet_demo_loc
URL 's3://jason-chletsos-parquet-dbt-demo/raw'
WITH (STORAGE CREDENTIAL jason_chletsos_parquet_demo_cred)
COMMENT 'Raw parquet for the S3-in-place dbt demo';

GRANT READ FILES ON EXTERNAL LOCATION jason_chletsos_parquet_demo_loc
TO `jason.chletsos@fivetran.com`;
```

Verify:

```sql
LIST 's3://jason-chletsos-parquet-dbt-demo/raw/orders/';
SELECT count(*) FROM read_files(
  's3://jason-chletsos-parquet-dbt-demo/raw/orders/', format => 'parquet');
```

## 3. Serverless SQL warehouses

Serverless SQL warehouses have no instance profile: the ONLY way they can
reach S3 is through a Unity Catalog external location covering the path.
Steps 1-2 are therefore mandatory for serverless. On classic warehouses an
instance profile with S3 read access is an alternative, but the external
location is the recommended path either way.

## 4. Schema for the dbt project

```sql
CREATE SCHEMA IF NOT EXISTS main.jason_chletsos_parquet_demo;
```

## Alternative: external tables instead of read_files()

If you prefer catalog-registered objects (and real `{{ source() }}` lineage
in dbt), register the prefixes as external parquet tables once the external
location exists:

```sql
CREATE TABLE main.jason_chletsos_parquet_demo.customers
USING PARQUET LOCATION 's3://jason-chletsos-parquet-dbt-demo/raw/customers/';

CREATE TABLE main.jason_chletsos_parquet_demo.products
USING PARQUET LOCATION 's3://jason-chletsos-parquet-dbt-demo/raw/products/';

CREATE TABLE main.jason_chletsos_parquet_demo.orders
USING PARQUET LOCATION 's3://jason-chletsos-parquet-dbt-demo/raw/orders/';
```

This needs `CREATE EXTERNAL TABLE` on the external location. The data still
lives only in S3 (no copy); Unity Catalog just holds metadata. If you go
this route, switch the staging models from `read_files(...)` to
`{{ source('s3_raw', '<table>') }}` — the source definitions in
`models/staging/sources.yml` already describe these tables.
