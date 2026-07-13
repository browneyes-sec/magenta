# AWS CloudTrail Module Outputs

output "s3_bucket_name" {
  description = "S3 bucket name for CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.cloudtrail.arn
}

output "trail_name" {
  description = "CloudTrail trail name"
  value       = aws_cloudtrail.main.name
}

output "collector_role_arn" {
  description = "IAM role ARN for Magenta collector to read S3"
  value       = aws_iam_role.collector.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group ARN"
  value       = aws_cloudwatch_log_group.trail.arn
}
