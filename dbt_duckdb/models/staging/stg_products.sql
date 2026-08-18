select
    cast(product_id as bigint) as product_id,
    cast(product_name as varchar) as product_name,
    cast(category as varchar) as category,
    cast(unit_price as double) as unit_price
from {{ source('raw_parquet', 'products') }}
