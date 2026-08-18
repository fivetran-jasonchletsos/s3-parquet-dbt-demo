select
    -- Date in UTC so the daily grain matches the snowflake and databricks
    -- projects regardless of the local session timezone.
    cast(o.order_ts at time zone 'UTC' as date) as order_date,
    p.category,
    c.region,
    count(*) as order_count,
    sum(o.quantity) as total_quantity,
    sum(o.quantity * p.unit_price) as gross_revenue
from {{ ref('stg_orders') }} o
join {{ ref('stg_customers') }} c on o.customer_id = c.customer_id
join {{ ref('stg_products') }} p on o.product_id = p.product_id
where o.status in ('shipped', 'delivered')
group by 1, 2, 3
