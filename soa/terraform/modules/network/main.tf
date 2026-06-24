# Network Module — Hub-and-Spoke Multi-Cloud Networking
# Creates VPCs/VNets across Azure, AWS, and GCP and peers them
# into a hub-spoke topology using Azure Virtual WAN, AWS Transit Gateway,
# and GCP VPC Peering.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# ── Variables ────────────────────────────────────────────────────────────

variable "environment" { type = string }
variable "region"       { type = string }
variable "tags"         { type = map(string) }

# Azure Hub VNet
variable "azure_hub_cidr"    { type = string   }
variable "azure_hub_subnets" { type = map(string) }

# AWS Hub VPC
variable "aws_hub_cidr"         { type = string }
variable "aws_hub_subnet_cidrs" { type = list(string) }

# GCP Hub VPC
variable "gcp_hub_cidr"       { type = string }
variable "gcp_project_id"     { type = string }

# ── Azure Hub ────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "network" {
  name     = "magenta-network-${var.environment}"
  location = var.region
  tags     = var.tags
}

resource "azurerm_virtual_network" "hub" {
  name                = "magenta-hub-vnet-${var.environment}"
  location            = azurerm_resource_group.network.location
  resource_group_name = azurerm_resource_group.network.name
  address_space       = [var.azure_hub_cidr]
  tags                = var.tags
}

resource "azurerm_subnet" "hub" {
  for_each             = var.azure_hub_subnets
  name                 = each.key
  resource_group_name  = azurerm_resource_group.network.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [each.value]
}

resource "azurerm_virtual_network_peering" "hub_to_spokes" {
  for_each = var.spoke_vnets

  name                      = "hub-to-${each.key}"
  resource_group_name       = azurerm_resource_group.network.name
  virtual_network_name      = azurerm_virtual_network.hub.name
  remote_virtual_network_id = each.value
  allow_forwarded_traffic   = true
  allow_gateway_transit     = true
  use_remote_gateways       = false
}

# ── AWS Hub ──────────────────────────────────────────────────────────────

resource "aws_vpc" "hub" {
  cidr_block           = var.aws_hub_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = "magenta-hub-vpc-${var.environment}" })
}

resource "aws_subnet" "hub" {
  count      = length(var.aws_hub_subnet_cidrs)
  vpc_id     = aws_vpc.hub.id
  cidr_block = var.aws_hub_subnet_cidrs[count.index]
  tags       = merge(var.tags, { Name = "magenta-hub-subnet-${count.index}" })
}

resource "aws_internet_gateway" "hub" {
  vpc_id = aws_vpc.hub.id
  tags   = merge(var.tags, { Name = "magenta-hub-igw" })
}

# ── AWS Transit Gateway ──────────────────────────────────────────────────

resource "aws_ec2_transit_gateway" "hub" {
  description                     = "Magenta multi-cloud transit gateway - ${var.environment}"
  amazon_side_asn                 = 64512
  auto_accept_shared_attachments  = "enable"
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  tags                            = merge(var.tags, { Name = "magenta-tgw-${var.environment}" })
}

resource "aws_ec2_transit_gateway_vpc_attachment" "hub" {
  subnet_ids         = aws_subnet.hub[*].id
  transit_gateway_id = aws_ec2_transit_gateway.hub.id
  vpc_id             = aws_vpc.hub.id
  tags               = merge(var.tags, { Name = "magenta-tgw-attach-hub" })
}

resource "aws_ec2_transit_gateway_route" "hub_default" {
  destination_cidr_block         = "0.0.0.0/0"
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.hub.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway.hub.association_default_route_table_id
}

# ── GCP Hub ──────────────────────────────────────────────────────────────

resource "google_compute_network" "hub" {
  project                 = var.gcp_project_id
  name                    = "magenta-hub-vpc-${var.environment}"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "hub" {
  project       = var.gcp_project_id
  name          = "magenta-hub-subnet-${var.environment}"
  network       = google_compute_network.hub.id
  region        = var.region
  ip_cidr_range = var.gcp_hub_cidr
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "azure_hub_vnet_id" {
  value = azurerm_virtual_network.hub.id
}

output "azure_resource_group" {
  value = azurerm_resource_group.network.name
}

output "aws_hub_vpc_id" {
  value = aws_vpc.hub.id
}

output "aws_transit_gateway_id" {
  value = aws_ec2_transit_gateway.hub.id
}

output "gcp_hub_network_id" {
  value = google_compute_network.hub.id
}

output "gcp_hub_subnet_id" {
  value = google_compute_subnetwork.hub.id
}
