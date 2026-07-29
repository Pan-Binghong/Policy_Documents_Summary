#!/usr/bin/env bash
set -euo pipefail

# ── 配置区（根据生产环境修改） ─────────────────────────────────────
IMAGE_NAME="policy-summary"
IMAGE_TAG="20260417"          # 与上传的 tar 文件名日期保持一致
CONTAINER_NAME="policy-summary"
HOST_PORT=9012
CONTAINER_PORT=8000
DEPLOY_DIR="/home/erpuser/policy-summary"
# ──────────────────────────────────────────────────────────────────

FULL_TAG="${IMAGE_NAME}:${IMAGE_TAG}"
TAR_FILE="${DEPLOY_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar"
ENV_FILE="${DEPLOY_DIR}/.env"

[ -f "$TAR_FILE" ] || { echo "ERROR: 镜像包不存在: $TAR_FILE"; exit 1; }
[ -f "$ENV_FILE" ] || { echo "ERROR: 环境配置不存在: $ENV_FILE"; exit 1; }

mkdir -p "${DEPLOY_DIR}/outputs" "${DEPLOY_DIR}/uploads"

echo "[1/3] Loading image: $FULL_TAG"
docker load -i "$TAR_FILE"

echo "[2/3] Stopping old container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

echo "[3/3] Starting: $CONTAINER_NAME"
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --env-file "$ENV_FILE" \
    -p "${HOST_PORT}:${CONTAINER_PORT}" \
    -v "${DEPLOY_DIR}/outputs:/app/outputs" \
    -v "${DEPLOY_DIR}/uploads:/app/uploads" \
    "$FULL_TAG"

echo ""
echo "Started: http://<server-ip>:${HOST_PORT}"
echo "Logs:    docker logs -f $CONTAINER_NAME"
