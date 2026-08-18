variable "aws_profile" {
  description = "AWS CLI profile to use (SSO)."
  type        = string
  default     = "pokemon-app"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket that holds the raw parquet files."
  type        = string
  default     = "jason-chletsos-parquet-dbt-demo"
}

# --- Snowflake storage integration (two-phase apply) ---
# Phase 1: leave these at the placeholder defaults and apply. The role must
# exist before Snowflake can be pointed at it. The placeholder principal is
# this same AWS account so the trust policy is valid but unusable by Snowflake.
# Phase 2: in Snowflake run
#   CREATE STORAGE INTEGRATION ... STORAGE_AWS_ROLE_ARN = '<snowflake_role_arn output>';
#   DESC INTEGRATION <name>;
# then copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID into
# terraform.tfvars and apply again.
variable "snowflake_iam_user_arn" {
  description = "STORAGE_AWS_IAM_USER_ARN from DESC INTEGRATION in Snowflake. Placeholder until phase 2."
  type        = string
  default     = "PLACEHOLDER"
}

variable "snowflake_external_id" {
  description = "STORAGE_AWS_EXTERNAL_ID from DESC INTEGRATION in Snowflake. Placeholder until phase 2."
  type        = string
  default     = "PLACEHOLDER_EXTERNAL_ID"
}

# --- Databricks Unity Catalog storage credential (same two-phase pattern) ---
# Phase 1: apply with defaults. Phase 2: create the storage credential in
# Databricks pointing at the role ARN, copy the External ID it reports
# (usually the Databricks account ID) into terraform.tfvars, and apply again.
variable "databricks_aws_account_id" {
  description = "AWS account Databricks uses to assume Unity Catalog roles. 414351767826 is the standard Databricks-on-AWS account."
  type        = string
  default     = "414351767826"
}

variable "databricks_external_id" {
  description = "External ID for the Unity Catalog storage credential (typically the Databricks account ID). Placeholder until phase 2."
  type        = string
  default     = "PLACEHOLDER_EXTERNAL_ID"
}
