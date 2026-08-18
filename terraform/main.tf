data "aws_caller_identity" "current" {}

locals {
  # During phase 1 the Snowflake IAM user ARN is unknown. Trusting this
  # account's root keeps the trust policy valid (IAM rejects fake ARNs)
  # while granting Snowflake nothing until phase 2 swaps in the real ARN.
  snowflake_principal_arn = (
    var.snowflake_iam_user_arn == "PLACEHOLDER"
    ? "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
    : var.snowflake_iam_user_arn
  )
}

# --- S3 bucket ---

resource "aws_s3_bucket" "parquet_demo" {
  bucket        = var.bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "parquet_demo" {
  bucket = aws_s3_bucket.parquet_demo.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Shared read policy document for both engines ---

data "aws_iam_policy_document" "bucket_read" {
  statement {
    sid    = "ListBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.parquet_demo.arn]
  }

  statement {
    sid    = "ReadObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]
    resources = ["${aws_s3_bucket.parquet_demo.arn}/*"]
  }
}

# --- Snowflake storage integration role ---

data "aws_iam_policy_document" "snowflake_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [local.snowflake_principal_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.snowflake_external_id]
    }
  }
}

resource "aws_iam_role" "snowflake_integration" {
  name               = "jason-chletsos-parquet-demo-snowflake"
  description        = "Assumed by the Snowflake storage integration to read demo parquet from S3."
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust.json
}

resource "aws_iam_role_policy" "snowflake_read" {
  name   = "s3-read-parquet-demo"
  role   = aws_iam_role.snowflake_integration.id
  policy = data.aws_iam_policy_document.bucket_read.json
}

# --- Databricks Unity Catalog storage credential role ---

data "aws_iam_policy_document" "databricks_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.databricks_aws_account_id}:root"]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.databricks_external_id]
    }
  }
}

resource "aws_iam_role" "databricks_uc" {
  name               = "jason-chletsos-parquet-demo-databricks"
  description        = "Assumed by a Databricks Unity Catalog storage credential to read demo parquet from S3."
  assume_role_policy = data.aws_iam_policy_document.databricks_trust.json
}

resource "aws_iam_role_policy" "databricks_read" {
  name   = "s3-read-parquet-demo"
  role   = aws_iam_role.databricks_uc.id
  policy = data.aws_iam_policy_document.bucket_read.json
}
