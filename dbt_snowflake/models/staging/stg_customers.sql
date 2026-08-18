select
    customer_id::number        as customer_id,
    customer_name::varchar     as customer_name,
    region::varchar            as region,
    signup_date::date          as signup_date
from {{ source('raw_parquet', 'customers') }}
