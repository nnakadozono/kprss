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
