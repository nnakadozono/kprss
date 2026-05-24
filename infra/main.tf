provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  ssm_parameter_prefix = trimprefix(var.ssm_prefix, "/")
  reader_site_prefix   = trim(var.reader_site_prefix, "/")
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

resource "aws_cloudfront_origin_access_control" "reader" {
  name                              = var.reader_cloudfront_oac_name
  description                       = "OAC for kprss reader S3 origin"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "reader_basic_auth" {
  name    = var.reader_basic_auth_function_name
  runtime = "cloudfront-js-2.0"
  comment = "Basic Auth for kprss reader"
  publish = true
  code = templatefile("${path.module}/reader_basic_auth.js.tftpl", {
    basic_auth_header = "Basic ${base64encode("${var.reader_basic_auth_username}:${var.reader_basic_auth_password}")}"
  })
}

resource "aws_cloudfront_cache_policy" "reader_short" {
  name        = var.reader_short_cache_policy_name
  comment     = "Short TTL cache policy for kprss reader HTML and fresh data"
  default_ttl = 60
  max_ttl     = 300
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }

    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
  }
}

resource "aws_cloudfront_cache_policy" "reader_long" {
  name        = var.reader_long_cache_policy_name
  comment     = "Long TTL cache policy for immutable kprss reader assets"
  default_ttl = 31536000
  max_ttl     = 31536000
  min_ttl     = 86400

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }

    headers_config {
      header_behavior = "none"
    }

    query_strings_config {
      query_string_behavior = "none"
    }

    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
  }
}

resource "aws_cloudfront_distribution" "reader" {
  enabled             = true
  comment             = "kprss reader"
  default_root_object = "index.html"
  price_class         = var.reader_cloudfront_price_class

  origin {
    domain_name              = aws_s3_bucket.kp_data.bucket_regional_domain_name
    origin_id                = "kprss-reader-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.reader.id
    origin_path              = "/${local.reader_site_prefix}"
  }

  default_cache_behavior {
    target_origin_id       = "kprss-reader-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.reader_short.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.reader_basic_auth.arn
    }
  }

  ordered_cache_behavior {
    path_pattern           = "assets/*"
    target_origin_id       = "kprss-reader-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.reader_long.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.reader_basic_auth.arn
    }
  }

  ordered_cache_behavior {
    path_pattern           = "data/manifest.json"
    target_origin_id       = "kprss-reader-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.reader_short.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.reader_basic_auth.arn
    }
  }

  ordered_cache_behavior {
    path_pattern           = "data/latest.json"
    target_origin_id       = "kprss-reader-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.reader_short.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.reader_basic_auth.arn
    }
  }

  ordered_cache_behavior {
    path_pattern           = "data/*.json"
    target_origin_id       = "kprss-reader-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = aws_cloudfront_cache_policy.reader_long.id
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.reader_basic_auth.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

data "aws_iam_policy_document" "reader_bucket_policy" {
  statement {
    sid    = "AllowCloudFrontReadReaderSite"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = [
      "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.kp_data.arn}/${local.reader_site_prefix}/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values = [
        aws_cloudfront_distribution.reader.arn,
      ]
    }
  }
}

resource "aws_s3_bucket_policy" "reader_cloudfront" {
  bucket = aws_s3_bucket.kp_data.id
  policy = data.aws_iam_policy_document.reader_bucket_policy.json
}
