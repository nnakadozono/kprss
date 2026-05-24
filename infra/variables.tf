variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}

variable "lambda_function_name" {
  type    = string
  default = "kprss"
}

variable "lambda_exec_role_name" {
  type        = string
  description = "Existing Lambda execution role name."
}

variable "lambda_exec_role_path" {
  type        = string
  description = "Existing Lambda execution role path."
}

variable "kprss_policy_name" {
  type        = string
  description = "Existing IAM policy name for kprss S3 and SSM access."
}

variable "scheduler_exec_role_name" {
  type        = string
  description = "Existing EventBridge Scheduler execution role name."
}

variable "scheduler_exec_role_path" {
  type        = string
  description = "Existing EventBridge Scheduler execution role path."
}

variable "scheduler_policy_name" {
  type        = string
  description = "Existing EventBridge Scheduler execution policy name."
}

variable "scheduler_policy_path" {
  type        = string
  description = "Existing EventBridge Scheduler execution policy path."
}

variable "kp_s3_bucket" {
  type        = string
  description = "Existing S3 bucket that holds the deployment artifact and database zip."
}

variable "lambda_s3_key" {
  type        = string
  default     = "function.zip"
  description = "S3 key for the Lambda deployment package."
}

variable "ssm_prefix" {
  type    = string
  default = "/kprss"
}

variable "scheduler_schedule_name" {
  type        = string
  description = "Existing EventBridge Scheduler schedule name."
}

variable "scheduler_schedule_group_name" {
  type        = string
  description = "Existing EventBridge Scheduler schedule group name."
}

variable "scheduler_schedule_expression" {
  type        = string
  description = "Existing EventBridge Scheduler expression."
}

variable "scheduler_schedule_timezone" {
  type        = string
  default     = "Asia/Tokyo"
  description = "Existing EventBridge Scheduler timezone."
}

variable "reader_site_prefix" {
  type        = string
  default     = "reader/site"
  description = "S3 prefix that stores the generated reader site."
}

variable "reader_basic_auth_username" {
  type        = string
  sensitive   = true
  description = "Basic Auth username for the reader CloudFront Function."
}

variable "reader_basic_auth_password" {
  type        = string
  sensitive   = true
  description = "Basic Auth password for the reader CloudFront Function."
}

variable "reader_cloudfront_oac_name" {
  type        = string
  default     = "kprss-reader-oac"
  description = "CloudFront Origin Access Control name for the reader."
}

variable "reader_basic_auth_function_name" {
  type        = string
  default     = "kprss-reader-basic-auth"
  description = "CloudFront Function name for reader Basic Auth."
}

variable "reader_short_cache_policy_name" {
  type        = string
  default     = "kprss-reader-short"
  description = "CloudFront cache policy name for short-lived reader objects."
}

variable "reader_long_cache_policy_name" {
  type        = string
  default     = "kprss-reader-long"
  description = "CloudFront cache policy name for long-lived reader objects."
}

variable "reader_cloudfront_price_class" {
  type        = string
  default     = "PriceClass_100"
  description = "CloudFront price class for the reader distribution."
}
