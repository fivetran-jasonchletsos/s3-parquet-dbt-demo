select
    -- order_ts is naive UTC, so a plain date cast is the UTC date and the
    -- daily grain matches the duckdb and databricks projects.
    o.order_ts::date                as order_date,
    p.category                      as category,
    c.region                        as region,
    count(*)                        as order_count,
    sum(o.quantity)                 as total_quantity,
    sum(o.quantity * p.unit_price)  as gross_revenue
from {{ ref('stg_orders') }} o
join {{ ref('stg_customers') }} c on o.customer_id = c.customer_id
join {{ ref('stg_products') }} p on o.product_id = p.product_id
where o.status in ('shipped', 'delivered')
group by 1, 2, 3
