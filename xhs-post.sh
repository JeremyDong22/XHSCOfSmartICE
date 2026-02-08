#!/bin/bash
# v1.0 - 小红书自动发帖 CLI 入口
# 自动加载 xhs-poster plugin，支持 headless 模式
# 用法:
#   ./xhs-post.sh "桌访AI 焦虑型"
#   ./xhs-post.sh "智能库存 干货型"

cd "$(dirname "$0")"

if [ -z "$1" ]; then
  echo "用法: ./xhs-post.sh \"[主题] [类型:焦虑型|噱头型|干货型|故事型]\""
  echo "示例: ./xhs-post.sh \"桌访AI 焦虑型\""
  exit 1
fi

claude --plugin-dir .claude/plugins/xhs-poster -p "/xhs-post $1"
