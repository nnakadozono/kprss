# kprss Terraform import guide

This directory is intended to adopt the existing manually-created AWS resources.
Do not run `terraform apply` until `terraform plan` shows no unexpected create,
replace, or destroy actions.

## First pass

```sh
terraform init
cp terraform.tfvars.example terraform.tfvars
terraform plan
```

Edit `terraform.tfvars` with the existing AWS resource names before importing.
The first plan will show resources to create because the state is empty. Import
the existing resources below, then run `terraform plan` again and adjust
`terraform.tfvars` until the plan is clean.

## Required imports

Replace placeholder values with the names and ARNs from the existing AWS account.

```sh
terraform import aws_s3_bucket.kp_data <bucket-name>

terraform import aws_iam_role.lambda_exec <lambda-exec-role-name>

terraform import aws_iam_role_policy_attachment.logs_attach \
  <lambda-exec-role-name>/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

terraform import aws_iam_policy.kprss_policy \
  arn:aws:iam::<account-id>:policy/<kprss-policy-name>

terraform import aws_iam_role_policy_attachment.attach_kprss_policy \
  <lambda-exec-role-name>/arn:aws:iam::<account-id>:policy/<kprss-policy-name>

terraform import aws_lambda_function.kprss <lambda-function-name>

terraform import aws_iam_role.scheduler_exec <scheduler-exec-role-name>

terraform import aws_iam_policy.scheduler_invoke_lambda \
  arn:aws:iam::<account-id>:policy/<scheduler-policy-path-without-leading-slash>/<scheduler-policy-name>

terraform import aws_iam_role_policy_attachment.attach_scheduler_policy \
  <scheduler-exec-role-name>/arn:aws:iam::<account-id>:policy/<scheduler-policy-path-without-leading-slash>/<scheduler-policy-name>

terraform import aws_scheduler_schedule.kprss_every_day <scheduler-group-name>/<scheduler-schedule-name>
```

If the existing S3/SSM permissions are an inline role policy instead of a
customer-managed IAM policy, do not import `aws_iam_policy.kprss_policy` or
`aws_iam_role_policy_attachment.attach_kprss_policy` as-is. Replace those
resources with `aws_iam_role_policy`, then import it with:

```sh
terraform import aws_iam_role_policy.kprss_policy \
  <lambda-exec-role-name>:<inline-policy-name>
```

## Values to verify before import

- `lambda_function_name`: existing Lambda function name.
- `lambda_exec_role_name`: existing Lambda execution role name.
- `lambda_exec_role_path`: existing Lambda execution role path.
- `kprss_policy_name`: existing customer-managed IAM policy name.
- `kp_s3_bucket`: existing S3 bucket name.
- `lambda_s3_key`: S3 object key used by the existing Lambda code package.
- `ssm_prefix`: Parameter Store prefix used by `KP_SSM_PREFIX`.
- `scheduler_schedule_name`: existing EventBridge Scheduler schedule name.
- `scheduler_schedule_group_name`: existing EventBridge Scheduler schedule group.
- `scheduler_schedule_expression`: existing schedule expression.
- `scheduler_schedule_timezone`: existing schedule timezone.

SSM parameters are intentionally not managed here, so secrets stay outside the
Terraform state. CloudWatch log groups are also left unmanaged unless you decide
to manage retention explicitly later.

## Useful AWS CLI lookups

```sh
aws lambda get-function --function-name <lambda-function-name>
aws lambda get-policy --function-name <lambda-function-name>
aws events list-rule-names-by-target --target-arn arn:aws:lambda:<region>:<account-id>:function:<lambda-function-name>
aws scheduler get-schedule --name <scheduler-schedule-name>
aws iam get-role --role-name <lambda-exec-role-name>
aws iam list-attached-role-policies --role-name <lambda-exec-role-name>
aws iam list-role-policies --role-name <lambda-exec-role-name>
aws iam get-role --role-name <scheduler-exec-role-name>
aws iam list-attached-role-policies --role-name <scheduler-exec-role-name>
aws ssm get-parameters-by-path --path <ssm-prefix> --with-decryption
aws sts get-caller-identity
```

## Safety notes

Several core resources use `prevent_destroy = true` to avoid accidental deletion
during adoption. If the first clean plan still wants to change live settings,
prefer updating these `.tf` files to match AWS before allowing Terraform to make
changes.
