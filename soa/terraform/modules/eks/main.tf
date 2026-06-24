# Amazon EKS Module
# Manages EKS clusters with IRSA, VPC CNI, managed node groups,
# and cost allocation tags.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

# ── EKS Cluster IAM Role ─────────────────────────────────────────────────

resource "aws_iam_role" "eks_cluster" {
  name = "${var.cluster_name}-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_iam_role_policy_attachment" "eks_service_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSServicePolicy"
  role       = aws_iam_role.eks_cluster.name
}

# ── EKS Cluster ──────────────────────────────────────────────────────────

resource "aws_eks_cluster" "this" {
  name                      = var.cluster_name
  role_arn                  = aws_iam_role.eks_cluster.arn
  version                   = var.kubernetes_version
  enabled_cluster_log_types = var.enable_audit_logging ? ["api", "audit", "authenticator", "controllerManager", "scheduler"] : []

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = var.private_cluster
    endpoint_public_access  = !var.private_cluster
    public_access_cidrs     = var.private_cluster ? [] : ["0.0.0.0/0"]
    security_group_ids      = var.security_group_ids
  }

  dynamic "kubernetes_network_config" {
    for_each = var.service_cidr != null ? [1] : []
    content {
      service_ipv4_cidr = var.service_cidr
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_service_policy,
  ]
}

# ── Node Group IAM Role ──────────────────────────────────────────────────

resource "aws_iam_role" "eks_node" {
  name = "${var.cluster_name}-node"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "eks_worker_node" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node.name
}

resource "aws_iam_role_policy_attachment" "eks_cni" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node.name
}

resource "aws_iam_role_policy_attachment" "ec2_container_registry" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node.name
}

# ── Managed Node Groups ──────────────────────────────────────────────────

resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-system"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = var.subnet_ids
  version         = var.kubernetes_version
  tags            = var.tags

  scaling_config {
    desired_size = var.system_node_count
    min_size     = var.enable_auto_scaling ? var.min_node_count : var.system_node_count
    max_size     = var.enable_auto_scaling ? var.max_node_count : var.system_node_count
  }

  instance_types = [var.system_node_sku]

  disk_size = var.os_disk_size_gb

  update_config {
    max_unavailable = 1
  }
}

resource "aws_eks_node_group" "user" {
  for_each = var.user_node_groups

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-${each.key}"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = var.subnet_ids
  version         = var.kubernetes_version
  tags            = var.tags

  scaling_config {
    desired_size = each.value.node_count
    min_size     = lookup(each.value, "min_count", each.value.node_count)
    max_size     = lookup(each.value, "max_count", each.value.node_count * 2)
  }

  instance_types = [each.value.vm_size]
  disk_size      = lookup(each.value, "os_disk_size_gb", var.os_disk_size_gb)

  dynamic "taint" {
    for_each = lookup(each.value, "taints", [])
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }

  labels = lookup(each.value, "node_labels", {})

  update_config {
    max_unavailable = 1
  }
}

# ── VPC CNI Addon ────────────────────────────────────────────────────────

resource "aws_eks_addon" "vpc_cni" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "vpc-cni"
  addon_version = var.vpc_cni_version
  tags          = var.tags
}

resource "aws_eks_addon" "coredns" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "coredns"
  addon_version = var.coredns_version
  tags          = var.tags
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "kube-proxy"
  addon_version = var.kube_proxy_version
  tags          = var.tags
}

# ── OIDC Provider for IRSA ───────────────────────────────────────────────

data "tls_certificate" "eks" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  tags            = var.tags
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "cluster_id" {
  value = aws_eks_cluster.this.id
}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_ca_certificate" {
  value     = base64decode(aws_eks_cluster.this.certificate_authority[0].data)
  sensitive = true
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.eks.arn
}

output "oidc_provider_url" {
  value = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

output "cluster_iam_role_arn" {
  value = aws_iam_role.eks_cluster.arn
}

output "node_instance_role_arn" {
  value = aws_iam_role.eks_node.arn
}
