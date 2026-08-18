-- One-time Snowflake setup for the S3 parquet external-table demo.
-- Run as ACCOUNTADMIN.
-- Prerequisite: `terraform apply` in ../terraform has created the S3 bucket
-- and the IAM role for Snowflake. Substitute its output for the placeholder:
--   <SNOWFLAKE_S3_ROLE_ARN>  = terraform output snowflake_role_arn
--                              (e.g. arn:aws:iam::<AWS_ACCOUNT_ID>:role/jason-chletsos-snowflake-s3)

use role ACCOUNTADMIN;

--------------------------------------------------------------------------------
-- 1. Storage integration over the raw/ prefix of the demo bucket.
--    This is a TWO-STEP IAM trust handshake:
--    step 1: create the integration with the IAM role ARN you intend Snowflake
--            to assume (the role's trust policy can start with a placeholder).
--------------------------------------------------------------------------------
create storage integration if not exists JASON_CHLETSOS_PARQUET_DEMO_S3_INT
  type = external_stage
  storage_provider = 'S3'
  enabled = true
  storage_aws_role_arn = '<SNOWFLAKE_S3_ROLE_ARN>'
  storage_allowed_locations = ('s3://jason-chletsos-parquet-dbt-demo/raw/');

--------------------------------------------------------------------------------
--    step 2: ask Snowflake which AWS principal it will use, then update the
--    IAM role's trust policy in AWS (terraform variables) with these values:
--      STORAGE_AWS_IAM_USER_ARN -> the trust policy Principal
--      STORAGE_AWS_EXTERNAL_ID  -> the sts:ExternalId condition
--    Until the trust policy carries both values, the stage below cannot list
--    or read the bucket.
--------------------------------------------------------------------------------
desc integration JASON_CHLETSOS_PARQUET_DEMO_S3_INT;

--------------------------------------------------------------------------------
-- 2. Database, schemas, warehouse.
--------------------------------------------------------------------------------
create database if not exists JASON_CHLETSOS_PARQUET_DEMO;
create schema if not exists JASON_CHLETSOS_PARQUET_DEMO.RAW;

create warehouse if not exists DEMO_WH
  warehouse_size = 'XSMALL'
  auto_suspend = 60
  auto_resume = true
  initially_suspended = true;

--------------------------------------------------------------------------------
-- 3. Parquet file format and external stage over s3://.../raw/.
--    The dbt sources point at subpaths of this stage (customers/, products/,
--    orders/), so one stage covers all three entities.
--------------------------------------------------------------------------------
create file format if not exists JASON_CHLETSOS_PARQUET_DEMO.RAW.PARQUET_FORMAT
  type = parquet;

create stage if not exists JASON_CHLETSOS_PARQUET_DEMO.RAW.PARQUET_STAGE
  url = 's3://jason-chletsos-parquet-dbt-demo/raw/'
  storage_integration = JASON_CHLETSOS_PARQUET_DEMO_S3_INT
  file_format = JASON_CHLETSOS_PARQUET_DEMO.RAW.PARQUET_FORMAT;

-- Sanity check once the IAM trust handshake is complete; should list the
-- parquet files under customers/, products/, orders/.
list @JASON_CHLETSOS_PARQUET_DEMO.RAW.PARQUET_STAGE;

--------------------------------------------------------------------------------
-- 4. Grants to the role dbt runs as. SALES_DEMO_ROLE matches the default
--    SNOWFLAKE_ROLE in profiles.yml (and the grants in
--    setup/run_snowflake_setup.py); if dbt runs as a different role, grant
--    that role instead. The role must already exist.
--------------------------------------------------------------------------------
grant usage on integration JASON_CHLETSOS_PARQUET_DEMO_S3_INT to role SALES_DEMO_ROLE;
grant usage on warehouse DEMO_WH to role SALES_DEMO_ROLE;
grant usage on database JASON_CHLETSOS_PARQUET_DEMO to role SALES_DEMO_ROLE;
grant usage, create table, create view, create external table
  on schema JASON_CHLETSOS_PARQUET_DEMO.RAW to role SALES_DEMO_ROLE;
grant usage on file format JASON_CHLETSOS_PARQUET_DEMO.RAW.PARQUET_FORMAT to role SALES_DEMO_ROLE;
grant usage on stage JASON_CHLETSOS_PARQUET_DEMO.RAW.PARQUET_STAGE to role SALES_DEMO_ROLE;
grant create schema on database JASON_CHLETSOS_PARQUET_DEMO to role SALES_DEMO_ROLE;
