# Copyright (c) Example

data "aws_ami" "ubuntu-noble" {
  most_recent = true
  owners      = [""] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp/ubuntu-noble-.-amd-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

module "cloud_server_ec_instance" {
  source  = "terraform-aws-modules/ec-instance/aws"
  version = "5.."
  count   = local.provision_cloud_server ?  : 

  name               = local.instance_name
  ami                = data.aws_ami.ubuntu-noble.id
  ignore_ami_changes = true

  instance_type = var.instance_type
  subnet_id     = module.vpc.public_subnets[]

  vpc_security_group_ids = [module.security_group.security_group_id]

  create_iam_instance_profile = true
  iam_role_name               = local.instance_role_name
  iam_role_use_name_prefix    = false
  iam_role_description        = "IM role for the ${local.instance_name} C instance"
  iam_role_policies = {
    mazonSSMManagedInstanceCore        = "arn:aws:iam::aws:policy/mazonSSMManagedInstanceCore"
    CloudWatchullccessV              = "arn:aws:iam::aws:policy/CloudWatchullccessV"
    mazonCContainerRegistryReadOnly  = "arn:aws:iam::aws:policy/mazonCContainerRegistryReadOnly"
    SecretsManagerReadWrite             = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
    s_full_access_policy               = module.iam_s_full_access_policy.arn
  }

  associate_public_ip_address = true
  create_eip                  = var.allocate_eip
  eip_tags                    = { Name = local.instance_name }

  ebs_optimized = true

  enable_volume_tags = false # we provide custom tags for the volumes below

  root_block_device = [
    {
      volume_size = var.root_volume_size
      volume_type = "gp"
      iops        = 
      throughput  = 5
      tags        = { "Name" = local.root_volume_name }
      # delete_on_termination = false
    }
  ]

  ebs_block_device = [
    {
      device_name = "/dev/sdf"
      volume_size = var.data_volume_size
      volume_type = "sc"
      tags        = { "Name" = local.data_volume_name }
      # delete_on_termination = false
    }
  ]

  disable_api_termination = true
  monitoring              = true
  key_name                = var.ssh_key_name

  # Note: changing user_data triggers a start/stop instance with apply.
  # It is not (too) harmful, but the (simple) public IP will change (needs a second apply).
  # We cannot set the ignore_changes lifecycle attribute, because the resource
  # is created by the module
  user_data = templatefile("${path.module}/scripts/cloud-config.yaml", {
    hostname             = local.instance_name
    s_bucket_name       = local.s_bucket_name
    cloudwatch_namespace = local.cloudwatch_namespace
  })
}

module "node_ec_instance" {
  for_each = var.sensor_net_nodes

  source  = "terraform-aws-modules/ec-instance/aws"
  version = "5.."

  name               = each.value.instance_name
  ami                = data.aws_ami.ubuntu-noble.id
  ignore_ami_changes = true

  instance_type = each.value.instance_type
  subnet_id     = module.vpc.public_subnets[]

  vpc_security_group_ids = [module.security_group.security_group_id]

  create_iam_instance_profile = true
  iam_role_name               = "${local.instance_role_name}-${each.value.instance_name}"
  iam_role_use_name_prefix    = false
  iam_role_description        = "IM role for the ${each.value.instance_name} C instance"
  iam_role_policies = {
    mazonSSMManagedInstanceCore        = "arn:aws:iam::aws:policy/mazonSSMManagedInstanceCore"
    CloudWatchullccessV              = "arn:aws:iam::aws:policy/CloudWatchullccessV"
    mazonCContainerRegistryReadOnly  = "arn:aws:iam::aws:policy/mazonCContainerRegistryReadOnly"
    SecretsManagerReadWrite             = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
    s_full_access_policy               = module.iam_s_full_access_policy.arn
  }

  associate_public_ip_address = true
  eip_tags                    = { Name = each.value.instance_name }

  ebs_optimized = true

  enable_volume_tags = false # we provide custom tags for the volumes below

  root_block_device = [
    {
      volume_size = each.value.root_volume_size
      volume_type = "gp"
      iops        = 
      throughput  = 5
      tags        = { "Name" = local.root_volume_name }
      # delete_on_termination = false
    }
  ]

  disable_api_termination = true
  monitoring              = true
  key_name                = var.ssh_key_name

  user_data = templatefile("${path.module}/scripts/node-cloud-config.yaml", {
    hostname             = each.value.instance_name
  }) 
}

data "aws_iam_role" "dlm_service_role" {
  name = local.dlm_service_role_name
}

resource "aws_dlm_lifecycle_policy" "instance_backup_policy" {
  description        = "ackup policy for the ${local.instance_name} instance"
  execution_role_arn = data.aws_iam_role.dlm_service_role.arn
  policy_details {
    resource_types = ["INSTNC"]

    # alternative: target_tags = local.tags
    target_tags = { "Name" = local.instance_name }

    schedule {
      name      = "one week of daily backups"
      copy_tags = true
      tags_to_add = {
        "backup" = "daily"
      }
      variable_tags = {
        "instance-id" = "$(instance-id)"
        "timestamp"   = "$(timestamp)"
      }
      create_rule {
        interval      = 
        interval_unit = "HOURS"
        times         = [":"]
      }
      retain_rule {
        count = 
      }
    }
  }

  tags = { "Name" = local.instance_backup_policy_name }
}
