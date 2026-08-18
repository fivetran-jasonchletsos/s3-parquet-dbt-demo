select
    product_id::number         as product_id,
    product_name::varchar      as product_name,
    category::varchar          as category,
    unit_price::float          as unit_price
from {{ source('raw_parquet', 'products') }}
