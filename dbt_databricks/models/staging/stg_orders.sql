-- The trailing slash on the prefix makes read_files pick up all three
-- orders_00*.parquet files as one relation.
select
    cast(order_id as bigint)      as order_id,
    cast(customer_id as bigint)   as customer_id,
    cast(product_id as bigint)    as product_id,
    cast(quantity as int)         as quantity,
    cast(order_ts as timestamp)   as order_ts,
    cast(status as string)        as status,
    status = 'cancelled'          as is_cancelled
from read_files(
    '{{ var("s3_raw_root") }}/orders/',
    format => 'parquet'
)
