# AWS CloudTrail → Event Hubs Module
# Creates S3 bucket + EventBridge rule to forward CloudTrail logs
# to Event Hubs via partner integration or direct S3 pull.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

# ── S3 Bucket for CloudTrail ─────────────────────────────────────────────

resource "aws_s3_bucket" "cloudtrail" {
  bucket = "${var.resource_prefix}-${var.environment}-cloudtrailogtrail"
  force_destroy = false
  tags = var.common_tags
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── CloudTrail Trail ──────────────────────────────────────────────────────

resource "aws_cloudtrail" "main" {
  name                          = "${var.resource_prefix}-${var.environment}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  enable_logging                = true
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  cloud_watch_logs_role_arn     = aws_iam_role.cloudwatch_logs.arn
  cloud_watch_logs_group_arn    = aws_cloudwatch_log_group.trail.arn
  kms_key_id                    = var.kms_key_id

  event_selector {
    read_write_type                 = "All"
    include_management_events       = true
    exclude_management_event_sources = ["kms.amazonaws.com", "rds.amazonaws.com"]
  }

  tags = var.common_tags
}

resource "aws_cloudwatch_log_group" "trail" {
  name              = "/aws/cloudtrail/${var.resource_prefix}-${var.environment}"
  retention_in_days = 90
  tags              = var.common_tags
}

# ── IAM for CloudWatch Logs ───────────────────────────────────────────────

resource "aws_iam_role" "cloudwatch_logs" {
  name = "${var.resource_prefix}-${var.environment}-cloudtrail-cloudwatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "cloudwatch_logs" {
  role = aws_iam_role.cloudwatch_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Effect   = "Allow"
      Resource = aws_cloudwatch_log_group.trail.arn
    }]
  })
}

# ── EventBridge Rule → Partner Event Hub (optional) ──────────────────────

resource "aws_cloudwatch_event_rule" "cloudtrail_to_partner" {
  count         = var.enable_partner_eventhub ? 1 : 0
  name          = "${var.resource_prefix}-${var.environment}-cloudtrail-eventhub"
  description   = "Forward CloudTrail events to Azure Event Hubs partner integration"
  event_pattern = jsonencode({
    source      = ["aws.cloudtrail"]
    detail_type = ["AWS API Call via CloudTrail"]
  })
}

resource "aws_cloudwatch_event_target" "eventhub" {
  count  = var.enable_partner_eventhub ? 1 : 0
  rule   = aws_cloudwatch_event_rule.cloudtrail_to_partner[0].name
  arn    = var.partner_eventhub_arn
  role_arn = aws_iam_role.eventbridge_target.arn
}

resource "aws_iam_role" "eventbridge_target" {
  count  = var.enable_partner_eventhub ? 1 : 0
  name   = "${var.resource_prefix}-${var.environment}-eventbridge-eventhub-target"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_target" {
  count  = var.enable_partner_eventhub ? 1 : 0
  role   = aws_iam_role.eventbridge_target[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "events:PutEvents"
      Effect   = "Allow"
      Resource = var.partner_eventhub_arn
    }]
  })
}

# ── S3 Access for Magenta Collector (read-only) ──────────────────────────

resource "aws_iam_policy" "collector_s3_read" {
  name   = "${var.resource_prefix}-${var.environment}-collector-s3-read"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetObjectVersion"
      ]
      Effect   = "Allow"
      Resource = [
        aws_s3_bucket.cloudtrail.arn,
        "${aws_s3_bucket.cloudtrail.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_role" "collector" {
  name = "${var.resource_prefix}-${var.environment}-cloudtrail-collector"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { AWS = var.collector_role_arn }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "collector_s3" {
  role       = aws_iam_role.collector.name
  policy_arn = aws_iam_policy.collector_s3_read.arn
}
