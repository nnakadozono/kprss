output "lambda_function_name" {
  value = aws_lambda_function.kprss.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.kprss.arn
}

output "s3_bucket" {
  value = aws_s3_bucket.kp_data.bucket
}

output "iam_role_arn" {
  value = aws_iam_role.lambda_exec.arn
}

output "scheduler_schedule_arn" {
  value = aws_scheduler_schedule.kprss_every_day.arn
}

output "reader_cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.reader.id
}

output "reader_cloudfront_domain_name" {
  value = aws_cloudfront_distribution.reader.domain_name
}

output "reader_site_s3_uri" {
  value = "s3://${aws_s3_bucket.kp_data.bucket}/${local.reader_site_prefix}"
}
