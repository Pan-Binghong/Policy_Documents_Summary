#!/bin/bash
set -e

docker load -i policy-summary.tar

mkdir -p /home/erpuser/policy-summary/outputs
mkdir -p /home/erpuser/policy-summary/uploads

docker run -d \
  --name policy-summary \
  --restart unless-stopped \
  -p 9012:8000 \
  -v /home/erpuser/policy-summary/outputs:/app/outputs \
  -v /home/erpuser/policy-summary/uploads:/app/uploads \
  -v "$(pwd)/.env:/app/.env:ro" \
  policy-summary:20260302

echo "服务已启动：http://localhost:9012"
