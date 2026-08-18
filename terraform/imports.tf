# The bucket was created ahead of the first apply (aws s3 mb on 2026-08-18)
# so the parquet could be uploaded immediately. This import block makes
# `terraform apply` adopt it instead of failing on BucketAlreadyOwnedByYou.
import {
  to = aws_s3_bucket.parquet_demo
  id = "jason-chletsos-parquet-dbt-demo"
}
