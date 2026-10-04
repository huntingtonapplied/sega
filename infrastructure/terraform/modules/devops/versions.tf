# Copyright (c) Example

terraform {
  required_version = "~> .."
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.."
    }
  }
}
