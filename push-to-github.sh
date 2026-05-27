#!/usr/bin/env bash
# JobPilot v1.0.0 — 一键推送到 GitHub
# 使用方法: bash push-to-github.sh <你的GitHub用户名>
# 示例: bash push-to-github.sh JXJ

set -euo pipefail

GITHUB_USER="${1:-}"
if [ -z "$GITHUB_USER" ]; then
  echo "用法: bash push-to-github.sh <你的GitHub用户名>"
  echo "示例: bash push-to-github.sh JXJ"
  exit 1
fi

REPO_URL="https://github.com/${GITHUB_USER}/jobpilot.git"

echo "=========================================="
echo "  JobPilot v1.0.0 — GitHub Push Script"
echo "=========================================="
echo ""
echo "Remote: ${REPO_URL}"
echo "Branch: master"
echo ""

# Step 1: 添加 remote（如果还没有）
if git remote get-url origin >/dev/null 2>&1; then
  CURRENT=$(git remote get-url origin)
  if [ "$CURRENT" != "$REPO_URL" ]; then
    echo "[1/4] 更新 origin remote..."
    git remote set-url origin "$REPO_URL"
  else
    echo "[1/4] origin 已配置: $REPO_URL"
  fi
else
  echo "[1/4] 添加 origin remote..."
  git remote add origin "$REPO_URL"
fi

# Step 2: 推送
echo "[2/4] 推送 master 分支..."
git push -u origin master

# Step 3: 创建 tag 并推送
echo "[3/4] 创建 v1.0.0 tag..."
git tag -f v1.0.0
git push origin v1.0.0

# Step 4: 完成
echo "[4/4] 完成!"
echo ""
echo "=========================================="
echo "  推送成功!"
echo "=========================================="
echo ""
echo "GitHub Actions 工作流:"
echo "  CI:              https://github.com/${GITHUB_USER}/jobpilot/actions/workflows/ci.yml"
echo "  全栈验证:         https://github.com/${GITHUB_USER}/jobpilot/actions/workflows/full-verification.yml"
echo ""
echo "手动触发全栈验证:"
echo "  https://github.com/${GITHUB_USER}/jobpilot/actions/workflows/full-verification.yml"
echo "  点击 'Run workflow' → 'Run workflow'"
echo ""
echo "项目文档:"
echo "  README:           https://github.com/${GITHUB_USER}/jobpilot"
echo "  交付清单:          https://github.com/${GITHUB_USER}/jobpilot/blob/master/FINAL_DELIVERY.md"
echo "  部署指南:          https://github.com/${GITHUB_USER}/jobpilot/blob/master/docs/DEPLOY.md"
