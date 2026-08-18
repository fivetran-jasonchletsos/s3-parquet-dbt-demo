select
    cast(customer_id as bigint) as customer_id,
    cast(customer_name as varchar) as customer_name,
    cast(region as varchar) as region,
    cast(signup_date as date) as signup_date
from {{ source('raw_parquet', 'customers') }}
