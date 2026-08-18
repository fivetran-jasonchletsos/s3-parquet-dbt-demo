select
    cast(order_id as bigint) as order_id,
    cast(customer_id as bigint) as customer_id,
    cast(product_id as bigint) as product_id,
    cast(quantity as integer) as quantity,
    cast(order_ts as timestamp with time zone) as order_ts,
    cast(status as varchar) as status,
    status = 'cancelled' as is_cancelled
from {{ source('raw_parquet', 'orders') }}
