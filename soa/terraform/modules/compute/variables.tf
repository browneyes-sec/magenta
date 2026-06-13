# Compute Module Variables

variable "subnet_ids" {
  description = "Subnet IDs for AWS VPC"
  type        = list(string)
  default     = []
}

variable "iam_role_arn" {
  description = "IAM role ARN for EKS cluster"
  type        = string
  default     = ""
}

variable "node_role_arn" {
  description = "IAM role ARN for EKS node group"
  type        = string
  default     = ""
}
