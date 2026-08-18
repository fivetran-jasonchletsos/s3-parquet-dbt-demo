select
    order_id::number           as order_id,
    customer_id::number        as customer_id,
    product_id::number         as product_id,
    quantity::number           as quantity,
    order_ts::timestamp_ntz    as order_ts,  -- naive UTC (see sources.yml)
    status::varchar            as status,
    status = 'cancelled'       as is_cancelled
from {{ source('raw_parquet', 'orders') }}
