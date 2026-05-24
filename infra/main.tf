provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  ssm_parameter_prefix = trimprefix(var.ssm_prefix, "/")
}

# S3 bucket for application data and function.zip.
resource "aws_s3_bucket" "kp_data" {
  bucket = var.kp_s3_bucket

  lifecycle {
    prevent_destroy = true
  }
}

# IAM role for Lambda.
resource "aws_iam_role" "lambda_exec" {
  name = var.lambda_exec_role_name
  path = var.lambda_exec_role_path

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

# CloudWatch Logs permissions managed by AWS.
resource "aws_iam_role_policy_attachment" "logs_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "kprss_policy" {
  name = var.kprss_policy_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowReadWriteS3Kprss"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]
        Resource = "${aws_s3_bucket.kp_data.arn}/*"
      },
      {
        Sid    = "AllowReadSSMParameters"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${local.ssm_parameter_prefix}/*",
        ]
      },
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role_policy_attachment" "attach_kprss_policy" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.kprss_policy.arn
}

# IAM role used by EventBridge Scheduler to invoke the Lambda.
resource "aws_iam_role" "scheduler_exec" {
  name = var.scheduler_exec_role_name
  path = var.scheduler_exec_role_path

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_policy" "scheduler_invoke_lambda" {
  name = var.scheduler_policy_name
  path = var.scheduler_policy_path
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
        ]
        Resource = [
          "${aws_lambda_function.kprss.arn}:*",
          aws_lambda_function.kprss.arn,
        ]
      },
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role_policy_attachment" "attach_scheduler_policy" {
  role       = aws_iam_role.scheduler_exec.name
  policy_arn = aws_iam_policy.scheduler_invoke_lambda.arn
}

# Lambda function. The zip is still produced by the existing deployment script.
resource "aws_lambda_function" "kprss" {
  function_name = var.lambda_function_name
  s3_bucket     = aws_s3_bucket.kp_data.bucket
  s3_key        = var.lambda_s3_key
  handler       = "kprss.lambda_handler"
  runtime       = "python3.12"
  architectures = ["arm64"]
  role          = aws_iam_role.lambda_exec.arn

  memory_size = 512
  timeout     = 300

  environment {
    variables = {
      KP_SSM_PREFIX = var.ssm_prefix
    }
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      publish,
      s3_bucket,
      s3_key,
      source_code_hash,
    ]
  }
}

# Existing EventBridge Scheduler schedule.
resource "aws_scheduler_schedule" "kprss_every_day" {
  name        = var.scheduler_schedule_name
  group_name  = var.scheduler_schedule_group_name
  description = ""
  state       = "ENABLED"

  schedule_expression          = var.scheduler_schedule_expression
  schedule_expression_timezone = var.scheduler_schedule_timezone

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 15
  }

  target {
    arn      = aws_lambda_function.kprss.arn
    role_arn = aws_iam_role.scheduler_exec.arn

    retry_policy {
      maximum_event_age_in_seconds = 86400
      maximum_retry_attempts       = 0
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
