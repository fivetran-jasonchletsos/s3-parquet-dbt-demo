#!/usr/bin/env python3
"""Adaptive runner for setup/snowflake_setup.sql.

Runs the one-time Snowflake-side setup over a single SSO connection
(one browser popup), adapting to whatever privileges the session has:

  SNOWFLAKE_ACCOUNT=<account-locator> \
  PYTHONPATH=tools/pandas_disabled python3 setup/run_snowflake_setup.py \
      --role-arn arn:aws:iam::<AWS_ACCOUNT_ID>:role/jason-chletsos-parquet-demo-snowflake

After it prints STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID it also
writes ../terraform/terraform.tfvars so `terraform apply` completes the IAM
trust handshake. Re-run with --verify once the trust policy is updated; it
then just lists the stage to prove Snowflake can read the bucket.
"""
import argparse
import os
import sys

import snowflake.connector

ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT")  # account locator, e.g. myorg-my_account
USER = os.environ.get("SNOWFLAKE_USER", "jason.chletsos@fivetran.com")
INTEGRATION = "JASON_CHLETSOS_PARQUET_DEMO_S3_INT"
DB = "JASON_CHLETSOS_PARQUET_DEMO"
SCHEMA = "RAW"
STAGE = f"{DB}.{SCHEMA}.PARQUET_STAGE"
FILE_FORMAT = f"{DB}.{SCHEMA}.PARQUET_FORMAT"
BUCKET_URL = "s3://jason-chletsos-parquet-dbt-demo/raw/"
DBT_ROLE = "SALES_DEMO_ROLE"
TFVARS_PATH = "../terraform/terraform.tfvars"


def run(cur, sql, ok_msg=None, fatal=False):
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        print(f"OK   {ok_msg or sql.strip().splitlines()[0][:80]}")
        return rows
    except snowflake.connector.errors.Error as e:
        msg = str(e).splitlines()[0][:160]
        print(f"FAIL {sql.strip().splitlines()[0][:80]} -> {msg}")
        if fatal:
            sys.exit(1)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role-arn", help="terraform output snowflake_role_arn")
    ap.add_argument("--verify", action="store_true",
                    help="only LIST the stage (run after the IAM trust update)")
    args = ap.parse_args()
    if not args.verify and not args.role_arn:
        ap.error("--role-arn is required unless --verify")
    if not ACCOUNT:
        sys.exit("Set SNOWFLAKE_ACCOUNT to the account locator (e.g. myorg-my_account).")

    con = snowflake.connector.connect(
        account=ACCOUNT, user=USER, authenticator="externalbrowser",
        client_store_temporary_credential=True,
    )
    cur = con.cursor()

    if args.verify:
        rows = run(cur, f"list @{STAGE}", "stage listing", fatal=True)
        for r in rows:
            print(f"     {r[0]}  {r[1]} bytes")
        expected = {"customers", "orders", "products"}
        seen = {r[0].split("/raw/")[-1].split("/")[0] for r in rows}
        if expected <= seen:
            print("OK   all three entity prefixes visible; handshake complete")
        else:
            print(f"WARN missing prefixes: {sorted(expected - seen)}")
            sys.exit(1)
        return

    # Storage integrations usually need ACCOUNTADMIN; fall back gracefully.
    elevated = run(cur, "use role ACCOUNTADMIN", "using ACCOUNTADMIN") is not None
    if not elevated:
        run(cur, f"use role {DBT_ROLE}", f"using {DBT_ROLE}")

    run(cur, f"""create storage integration if not exists {INTEGRATION}
        type = external_stage storage_provider = 'S3' enabled = true
        storage_aws_role_arn = '{args.role_arn}'
        storage_allowed_locations = ('{BUCKET_URL}')""",
        "storage integration", fatal=True)

    desc = run(cur, f"desc integration {INTEGRATION}", "desc integration", fatal=True)
    props = {r[0]: r[2] for r in desc}
    iam_user = props.get("STORAGE_AWS_IAM_USER_ARN", "")
    ext_id = props.get("STORAGE_AWS_EXTERNAL_ID", "")
    print(f"     STORAGE_AWS_IAM_USER_ARN = {iam_user}")
    print(f"     STORAGE_AWS_EXTERNAL_ID = {ext_id}")
    with open(TFVARS_PATH, "w") as f:
        f.write(f'snowflake_iam_user_arn = "{iam_user}"\n'
                f'snowflake_external_id  = "{ext_id}"\n')
    print(f"OK   wrote {TFVARS_PATH}")

    run(cur, f"create database if not exists {DB}", "database")
    run(cur, f"create schema if not exists {DB}.{SCHEMA}", "schema")
    if run(cur, """create warehouse if not exists DEMO_WH
            warehouse_size='XSMALL' auto_suspend=60 auto_resume=true
            initially_suspended=true""", "warehouse DEMO_WH") is None:
        whs = run(cur, "show warehouses", "existing warehouses") or []
        print(f"     use one of: {[w[0] for w in whs][:5]} via SNOWFLAKE_WAREHOUSE")
    run(cur, f"create file format if not exists {FILE_FORMAT} type = parquet",
        "file format")
    run(cur, f"""create stage if not exists {STAGE}
        url = '{BUCKET_URL}'
        storage_integration = {INTEGRATION}
        file_format = {FILE_FORMAT}""", "stage", fatal=True)

    if elevated:
        for g in (f"grant usage on integration {INTEGRATION} to role {DBT_ROLE}",
                  f"grant usage on warehouse DEMO_WH to role {DBT_ROLE}",
                  f"grant usage on database {DB} to role {DBT_ROLE}",
                  f"grant create schema on database {DB} to role {DBT_ROLE}",
                  f"grant usage, create table, create view, create external table "
                  f"on schema {DB}.{SCHEMA} to role {DBT_ROLE}",
                  f"grant usage on file format {FILE_FORMAT} to role {DBT_ROLE}",
                  f"grant usage on stage {STAGE} to role {DBT_ROLE}"):
            run(cur, g)

    print("\nNext: update the IAM trust policy with the two values above "
          "(terraform apply, or aws iam update-assume-role-policy), then "
          "re-run with --verify.")


if __name__ == "__main__":
    main()
