# vSphere Module — Private Cloud VM Provisioning
# Creates VMs for self-managed Kubernetes control-plane and worker nodes.
# Used for IL5 regulated workloads (10% allocation per multicloud.toml).

terraform {
  required_providers {
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.8"
    }
  }
}

# ── Data Sources ─────────────────────────────────────────────────────────

data "vsphere_datacenter" "this" {
  name = var.datacenter
}

data "vsphere_compute_cluster" "this" {
  name          = var.compute_cluster
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_datastore" "this" {
  name          = var.datastore
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_network" "this" {
  name          = var.network_name
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_virtual_machine" "template" {
  name          = var.template_name
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_resource_pool" "this" {
  name          = var.resource_pool != null ? var.resource_pool : data.vsphere_compute_cluster.this.resource_pool_id
  datacenter_id = data.vsphere_datacenter.this.id
}

# ── Folder ───────────────────────────────────────────────────────────────

resource "vsphere_folder" "this" {
  path          = var.folder_path
  type          = "vm"
  datacenter_id = data.vsphere_datacenter.this.id
}

# ── Control Plane Nodes ──────────────────────────────────────────────────

resource "vsphere_virtual_machine" "control_plane" {
  count            = var.control_plane_count
  name             = "${var.vm_name_prefix}-cp-${count.index + 1}"
  folder           = vsphere_folder.this.path
  resource_pool_id = data.vsphere_resource_pool.this.id
  datastore_id     = data.vsphere_datastore.this.id
  num_cpus         = var.control_plane_cpu
  memory           = var.control_plane_memory_mb
  guest_id         = data.vsphere_virtual_machine.template.guest_id
  tags             = var.tags

  scsi_type = data.vsphere_virtual_machine.template.scsi_type

  network_interface {
    network_id   = data.vsphere_network.this.id
    adapter_type = data.vsphere_virtual_machine.template.network_interface_types[0]
  }

  disk {
    label            = "disk0"
    size             = var.control_plane_disk_gb
    eagerly_scrub    = var.disk_eagerly_scrub
    thin_provisioned = var.disk_thin_provision
    unit_number      = 0
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.template.id
    customize {
      linux_options {
        host_name = "${var.vm_name_prefix}-cp-${count.index + 1}"
        domain    = var.domain
      }
      network_interface {
        ipv4_address = cidrhost(var.control_plane_cidr, count.index + var.ip_offset)
        ipv4_netmask = var.netmask
      }
      dns_server_list = var.dns_servers
    }
  }
}

# ── Worker Nodes ─────────────────────────────────────────────────────────

resource "vsphere_virtual_machine" "worker" {
  count            = var.worker_count
  name             = "${var.vm_name_prefix}-worker-${count.index + 1}"
  folder           = vsphere_folder.this.path
  resource_pool_id = data.vsphere_resource_pool.this.id
  datastore_id     = data.vsphere_datastore.this.id
  num_cpus         = var.worker_cpu
  memory           = var.worker_memory_mb
  guest_id         = data.vsphere_virtual_machine.template.guest_id
  tags             = var.tags

  scsi_type = data.vsphere_virtual_machine.template.scsi_type

  network_interface {
    network_id   = data.vsphere_network.this.id
    adapter_type = data.vsphere_virtual_machine.template.network_interface_types[0]
  }

  disk {
    label            = "disk0"
    size             = var.worker_disk_gb
    eagerly_scrub    = var.disk_eagerly_scrub
    thin_provisioned = var.disk_thin_provision
    unit_number      = 0
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.template.id
    customize {
      linux_options {
        host_name = "${var.vm_name_prefix}-worker-${count.index + 1}"
        domain    = var.domain
      }
      network_interface {
        ipv4_address = cidrhost(var.worker_cidr, count.index + var.ip_offset)
        ipv4_netmask = var.netmask
      }
      dns_server_list = var.dns_servers
    }
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────

output "control_plane_ips" {
  value = vsphere_virtual_machine.control_plane[*].guest_ip_addresses
}

output "worker_ips" {
  value = vsphere_virtual_machine.worker[*].guest_ip_addresses
}

output "control_plane_count" {
  value = var.control_plane_count
}

output "worker_count" {
  value = var.worker_count
}

output "datacenter" {
  value = var.datacenter
}
