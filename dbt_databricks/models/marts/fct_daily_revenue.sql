-- Grain: order_date x category x region.
-- Materialized as a Delta table (adapter default) so the aggregate is the
-- only thing persisted in the metastore; the raw parquet stays in S3.
select
    -- Date in UTC so the daily grain matches the duckdb and snowflake
    -- projects (Databricks session timezone defaults to UTC; to_utc_timestamp
    -- guards against workspaces that override it).
    cast(to_utc_timestamp(o.order_ts, current_timezone()) as date) as order_date,
    p.category,
    c.region,
    count(*)                         as order_count,
    sum(o.quantity)                  as total_quantity,
    sum(o.quantity * p.unit_price)   as gross_revenue
from {{ ref('stg_orders') }} o
join {{ ref('stg_customers') }} c
    on o.customer_id = c.customer_id
join {{ ref('stg_products') }} p
    on o.product_id = p.product_id
where o.status in ('shipped', 'delivered')
group by 1, 2, 3
