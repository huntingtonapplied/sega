# Copyright (c) Example

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.."

  name = local.vpc_name

  cidr = var.cidr_block

  azs = [var.availability_zone]

  # use only a portion of the CIDR block for the public subnet
  # to reserve the rest for future use
  public_subnets = [cidrsubnet(var.cidr_block, , )]

  manage_default_security_group = false
}

module "security_group" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "5.."

  name            = local.security_group_name
  use_name_prefix = false
  description     = "Security group for ${var.name} instances"
  vpc_id          = module.vpc.vpc_id

  egress_cidr_blocks  = [".../"]
  egress_rules        = ["all-all"]
  ingress_cidr_blocks = [".../"]
  ingress_rules       = ["ssh-tcp", "openvpn-udp", "http--tcp", "https--tcp", "all-icmp"]
}

module "dns_records" {
  count   = length(module.cloud_server_ec_instance)
  source  = "terraform-aws-modules/route5/aws//modules/records"
  version = ".."

  zone_name = var.dns_zone_name
  records = [
    {
      name    = local.instance_name
      ttl     = 
      type    = ""
      records = [for instance in module.cloud_server_ec_instance : instance.public_ip]
    }
  ]
}
