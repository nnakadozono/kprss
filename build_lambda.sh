#!/bin/bash
set -e

source ./myenv.sh

IMAGE="public.ecr.aws/lambda/python:3.12"
PLATFORM="linux/arm64" # "linux/amd64" for x86_64
WORK_DIR="/var/task"
LAMBDA_FILE="kprss.py"
OUTPUT_ZIP="function.zip"

echo "🐳 Building in Docker image: $IMAGE"

docker run --rm \
  --platform $PLATFORM \
  -v "$PWD":$WORK_DIR \
  -w $WORK_DIR \
  --entrypoint /bin/bash \
  "$IMAGE" \
  -c "
    set -e
    dnf install -y zip
    rm -rf build && mkdir build
    pip install -r requirements.txt -t build
    cp $LAMBDA_FILE build/
    mkdir -p build/reader
    cp reader/__init__.py reader/generator.py build/reader/
    cd build
    zip -r ../$OUTPUT_ZIP .
  "

echo "🎉 Built $OUTPUT_ZIP"

aws s3 cp $OUTPUT_ZIP s3://$KP_S3_BUCKET/$OUTPUT_ZIP
echo "🚀 Uploaded to S3 bucket $KP_S3_BUCKET"

aws lambda update-function-code \
  --function-name kprss \
  --s3-bucket $KP_S3_BUCKET \
  --s3-key $OUTPUT_ZIP
echo "🚀 Updated Lambda function code"

echo "✅ Done"
