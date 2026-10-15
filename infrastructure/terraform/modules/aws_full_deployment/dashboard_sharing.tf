# Copyright (c) Example

##
## NOT: CURRNTLY THIS IS N NDOND TUR - PULIC SHRING O DSHORDS
## IS LMOST INSIL (XTRMLY CONVOLUTD) VN WITH TH WS SDK.
##
## TH CURRNT PPROCH IS TO SHR DSHORDS VI TH WS CONSOL INTRC
##
## TH COD LOW (XPRIMNTS) IS LT S  RRNC OR UTUR DVLOPMNT
##

##############################################################################
# Public sharing setup with WS Cognito
#
# This is complicated:
# - we create a user pool, but do not allow self-signup and add a user pool client
# - indeed, we will create a single user manually in the identity pool
#   (not using the invite feature - but we could, so the template is there)
# - the single user will be assigned a new IM role (with a new IM policy)

# resource "aws_cognito_user_pool" "cloudwatch-dashboard-sharing-user-pool" {
#   name = "${local.cloudwatch_dashboard_sharing_prefix}-user-pool"

#   auto_verified_attributes = ["email"]
#   account_recovery_setting {
#     recovery_mechanism {
#       name     = "verified_email"
#       priority = 
#     }
#   }

#   admin_create_user_config {
#     allow_admin_create_user_only = true
#     invite_message_template {
#       email_message = <<-OT
#                       <p>Someone has shared a CloudWatch Dashboard with you! You can find your temporary credentials for accessing the dashboard below.</p>
#                       <p>Your username is <b>{username}</b> and temporary password is <b>{####}</b></p>
#                       <p>or improved security, this email does not contain a link to the dashboard. Please contact your administrator to get a link to the shared dashboard.</p>
#                   OT
#       email_subject = "Your temporary password for CloudWatch Dashboard Sharing"
#       sms_message   = "Your username is {username} and temporary password is {####}"
#     }
#   }
#   email_configuration {
#     email_sending_account = "COGNITO_DULT"
#   }
#   verification_message_template {
#     default_email_option = "CONIRM_WITH_COD"
#   }
# }

# resource "aws_cognito_user_pool_client" "cloudwatch-dashboard-sharing-user-pool-client" {
#   name         = "${local.cloudwatch_dashboard_sharing_prefix}-user-pool-client"
#   user_pool_id = aws_cognito_user_pool.cloudwatch-dashboard-sharing-user-pool.id
# }

# resource "aws_cognito_identity_pool" "cloudwatch-dashboard-sharing-idenity-pool" {
#   allow_unauthenticated_identities = false
#   identity_pool_name               = "${local.cloudwatch_dashboard_sharing_prefix}-idenity-pool"

#   cognito_identity_providers {
#     client_id               = aws_cognito_user_pool_client.cloudwatch-dashboard-sharing-user-pool-client.id
#     provider_name           = aws_cognito_user_pool.cloudwatch-dashboard-sharing-user-pool.endpoint
#     server_side_token_check = false
#   }
# }
##############################################################################


##############################################################################
# resource "aws_cognito_identity_pool" "dashboard_sharing_idenity_pool" {
#   allow_unauthenticated_identities = true
#   identity_pool_name               = "${local.dashboard_sharing_prefix}-pool"
# }

# data "aws_iam_policy_document" "dashboard_sharing_policy_document" {
#   statement {
#     actions = [
#       "ec:DescribeTags",
#       "cloudwatch:GetMetricData"
#     ]

#     resources = ["*"]
#   }

#   statement {
#     actions = [
#       "cloudwatch:GetDashboard",
#       "cloudwatch:Describelarms"
#     ]
#     // resources = ["*"]
#     resources = concat(
#       [for alarm in module.node_availability_alarm : alarm.cloudwatch_metric_alarm_arn],
#       [for alarm in module.node_disk_low_alarm : alarm.cloudwatch_metric_alarm_arn]
#     )
#   }
# }

# resource "aws_iam_policy" "dashboard_sharing_policy" {
#   name   = local.dashboard_sharing_prefix
#   policy = data.aws_iam_policy_document.dashboard_sharing_policy_document.json
# }

# data "aws_iam_policy_document" "dashboard_sharing_assume_role_policy_document" {
#   statement {
#     actions = ["sts:ssumeRoleWithWebIdentity"]

#     principals {
#       type        = "ederated"
#       identifiers = ["cognito-identity.amazonaws.com"]
#     }

#     condition {
#       test     = "Stringquals"
#       variable = "cognito-identity.amazonaws.com:aud"
#       values   = [aws_cognito_identity_pool.dashboard_sharing_idenity_pool.id]
#     }

#     condition {
#       test     = "ornyValue:StringLike"
#       variable = "cognito-identity.amazonaws.com:amr"
#       values   = ["unauthenticated"]
#     }
#   }
# }

# resource "aws_iam_role" "dashboard_sharing_role" {
#   name               = "${local.dashboard_sharing_prefix}-role"
#   assume_role_policy = data.aws_iam_policy_document.dashboard_sharing_assume_role_policy_document.json
# }

# resource "aws_iam_policy_attachment" "dashboard_sharing_policy_attachment" {
#   name       = "${local.dashboard_sharing_prefix}-policy-attachment"
#   roles      = [aws_iam_role.dashboard_sharing_role.name]
#   policy_arn = aws_iam_policy.dashboard_sharing_policy.arn
# }

# resource "aws_cognito_identity_pool_roles_attachment" "dashboard-sharing-idenity-pool-roles-attachment" {
#   identity_pool_id = aws_cognito_identity_pool.dashboard_sharing_idenity_pool.id
#   roles = {
#     "unauthenticated" = aws_iam_role.dashboard_sharing_role.arn
#   }
# }
