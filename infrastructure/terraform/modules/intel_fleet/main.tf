terraform {
  required_providers {
    aws    = { source = "hashicorp/aws", version = ">= 5.0" }
    random = { source = "hashicorp/random", version = ">= 3.0" }
  }
}

# per-apply suffix so each run's nodes get a UNIQUE tailscale hostname. Without it,
# a re-run collides with a prior (now-offline) node still in the tailnet, Tailscale
# appends "-1", and the inventory's un-suffixed FQDN then resolves to the DEAD node.
resource "random_id" "run" {
  byte_length = 2
}

provider "aws" {
  region = var.region
}

locals {
  # index 0 = head (runs redis + shared-store + aggregator); rest = workers
  node_count = 1 + var.worker_count
  # unique per-run node names (tailscale hostname == tags.Name == inventory FQDN base)
  node_names = [for i in range(1 + var.worker_count) :
    i == 0
    ? "${var.name_prefix}-head-${random_id.run.hex}"
  : "${var.name_prefix}-w${i}-${random_id.run.hex}"]
}

locals {
  # ubuntu AMI arch token: x86_64 -> amd64, arm64 -> arm64
  ami_arch = var.cpu_arch == "arm64" ? "arm64" : "amd64"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-${local.ami_arch}-server-*"]
  }
  filter {
    name   = "architecture"
    values = [var.cpu_arch]
  }
}

# --- flat network: cluster placement group (single-AZ, low-latency) ----------
# Optional: burstable t-series don't support cluster PGs, so cheap tests set
# use_placement_group=false. count-gated so nodes below reference it safely.
resource "aws_placement_group" "fleet" {
  count    = var.use_placement_group ? 1 : 0
  name     = "${var.name_prefix}-pg"
  strategy = "cluster"
}

# --- self-referencing SG: all node<->node ports open, closed to the world -----
resource "aws_security_group" "fleet" {
  name        = "${var.name_prefix}-sg"
  description = "swarm fleet - intra-cluster open, ssh in, egress out"
  vpc_id      = var.vpc_id
}

resource "aws_security_group_rule" "intra" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.fleet.id
  source_security_group_id = aws_security_group.fleet.id # self-reference
}

resource "aws_security_group_rule" "ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  security_group_id = aws_security_group.fleet.id
  cidr_blocks       = ["100.64.0.0/10"] # tailscale CGNAT range only
}

resource "aws_security_group_rule" "egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.fleet.id
  cidr_blocks       = ["0.0.0.0/0"]
}

# --- shared store: EFS mounted at drop_path on every node --------------------
# Gated by use_efs. Managed EFS needs elasticfilesystem:* on the deploy IAM user;
# where that isn't granted (or for a cheap plumbing smoke) set use_efs=false and
# each node uses a local dir at drop_path (no cross-node shared FS — see cloud-init).
resource "aws_efs_file_system" "drop" {
  count          = var.use_efs ? 1 : 0
  creation_token = "${var.name_prefix}-drop"
  encrypted      = true
  tags           = { Name = "${var.name_prefix}-drop" }
}

resource "aws_efs_mount_target" "drop" {
  count           = var.use_efs ? 1 : 0
  file_system_id  = aws_efs_file_system.drop[0].id
  subnet_id       = var.subnet_id
  security_groups = [aws_security_group.fleet.id]
}

# --- the nodes ---------------------------------------------------------------
resource "aws_instance" "node" {
  count                       = local.node_count
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = count.index == 0 ? var.head_type : var.worker_type
  subnet_id                   = var.subnet_id
  availability_zone           = var.availability_zone
  placement_group             = var.use_placement_group ? aws_placement_group.fleet[0].id : null
  vpc_security_group_ids      = [aws_security_group.fleet.id]
  key_name                    = var.ssh_key_name != "" ? var.ssh_key_name : null
  # Egress for cloud-init (docker + tailscale install) needs EITHER a NAT gateway on a
  # private subnet OR a public IP on a public subnet. The prod design assumes private +
  # NAT (public_ip=false); the cheap test targets a public subnet with no NAT, so it must
  # set associate_public_ip=true. Inbound stays locked by the SG regardless.
  associate_public_ip_address = var.associate_public_ip

  # TTL backstop: terminate (not stop) on the cloud-init `shutdown` so a forgotten
  # teardown or a dead orchestrator can't leave instances billing indefinitely.
  # NOTE: spot instances reject setting this attribute (UnsupportedOperation) — but
  # they already DEFAULT to terminate-on-shutdown, so leave it null for spot and the
  # TTL `shutdown -h` still terminates. Only set it explicitly for on-demand.
  instance_initiated_shutdown_behavior = var.use_spot ? null : (var.ttl_minutes > 0 ? "terminate" : "stop")

  # spot for cost (sim pool + all testing): one-time request, no auto-replace on
  # interruption — fine for stateless workers / short tests.
  dynamic "instance_market_options" {
    for_each = var.use_spot ? [1] : []
    content {
      market_type = "spot"
    }
  }

  root_block_device {
    volume_size = var.root_volume_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    hostname      = local.node_names[count.index]
    ts_authkey    = var.ts_authkey
    debug_ssh_key = var.debug_ssh_key
    use_efs       = var.use_efs
    efs_id      = var.use_efs ? aws_efs_file_system.drop[0].id : ""
    region      = var.region
    drop_path   = var.drop_path
    ttl_minutes = var.ttl_minutes
  })

  tags = {
    Name       = local.node_names[count.index]
    intel_role = count.index == 0 ? "head" : "worker"
  }

  depends_on = [aws_efs_mount_target.drop]
}
