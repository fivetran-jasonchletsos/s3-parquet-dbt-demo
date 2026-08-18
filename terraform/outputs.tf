output "bucket_name" {
  description = "S3 bucket holding the raw parquet files."
  value       = aws_s3_bucket.parquet_demo.bucket
}

output "snowflake_role_arn" {
  description = "Role ARN for STORAGE_AWS_ROLE_ARN in the Snowflake storage integration."
  value       = aws_iam_role.snowflake_integration.arn
}

output "databricks_role_arn" {
  description = "Role ARN for the Databricks Unity Catalog storage credential."
  value       = aws_iam_role.databricks_uc.arn
}
