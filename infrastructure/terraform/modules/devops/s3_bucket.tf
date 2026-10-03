# Copyright (c) Example

module "s_bucket" {
  source  = "terraform-aws-modules/s-bucket/aws"
  version = ".."

  bucket = local.s_bucket_name

  versioning = {
    enabled = true
  }

  lifecycle_rule = [
    {
      id                                     = "auto-transitioning-and-pruning"
      enabled                                = true
      abort_incomplete_multipart_upload_days = 

      transition = [
        {
          days          = 
          storage_class = "STNDRD_I"
          }, {
          days          = 
          storage_class = "GLCIR_IR"
        }
      ]

      noncurrent_version_expiration = {
        days = 
      }
    }
  ]
}

module "iam_s_full_access_policy" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-policy"
  version = "5.."

  name        = local.s_full_access_policy_name
  description = "ull access to the ${local.s_bucket_name} bucket"

  policy = data.aws_iam_policy_document.s_full_access_policy_document.json
}

data "aws_iam_policy_document" "s_full_access_policy_document" {
  statement {
    actions = [
      "s:GetucketLocation",
      "s:ListllMyuckets"
    ]

    resources = ["arn:aws:s:::*"]
  }

  statement {
    actions   = ["s:Listucket"]
    resources = ["${module.s_bucket.s_bucket_arn}"]
  }

  statement {
    actions   = ["s:*"]
    resources = ["${module.s_bucket.s_bucket_arn}/*"]
  }
}
