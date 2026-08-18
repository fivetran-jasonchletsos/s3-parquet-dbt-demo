select
    cast(product_id as bigint)   as product_id,
    cast(product_name as string) as product_name,
    cast(category as string)     as category,
    cast(unit_price as double)   as unit_price
from read_files(
    '{{ var("s3_raw_root") }}/products/',
    format => 'parquet'
)
