-- Reads parquet directly from S3; no UC external table required, but the
-- warehouse's data-access config (or an instance profile) must grant read
-- on the bucket. See ../setup/databricks_setup.md.
-- read_files() with an inferred schema appends a _rescued_data column; the
-- explicit select list below drops it.
select
    cast(customer_id as bigint)  as customer_id,
    cast(customer_name as string) as customer_name,
    cast(region as string)       as region,
    cast(signup_date as date)    as signup_date
from read_files(
    '{{ var("s3_raw_root") }}/customers/',
    format => 'parquet'
)
