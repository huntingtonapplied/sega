# Emits the inventory in the exact format SwarmDeployer._read_inventory expects:
#   <role> <ssh-target> <tailscale-fqdn> <node-label>
# so the swarm/deploy stages need zero ec2 special-casing — same code path as
# the mini-net inventory file.

output "inventory" {
  description = "role ssh-target fqdn label, one node per line"
  value = join("\n", [
    for i, node in aws_instance.node :
    format("%s %s@%s %s intel_role=%s",
      i == 0 ? "head" : "worker",
      var.ssh_user,
      "${node.tags["Name"]}.${var.tailnet}",
      "${node.tags["Name"]}.${var.tailnet}",
      i == 0 ? "head" : "worker",
    )
  ])
}

output "head_fqdn" {
  value = "${aws_instance.node[0].tags["Name"]}.${var.tailnet}"
}

output "efs_id" {
  value = var.use_efs ? aws_efs_file_system.drop[0].id : ""
}

output "node_private_ips" {
  value = [for n in aws_instance.node : n.private_ip]
}
