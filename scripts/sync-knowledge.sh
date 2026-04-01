#!/bin/bash
# 知识库字段规范月度同步
# 每月1日自动运行，将 config.json 字段定义推送到飞书规范文档

cd /Users/xili/lark-knowledge

/Users/xili/.local/bin/claude \
  --print \
  --allowedTools "Bash,Read,Edit,Write,Glob,Grep" \
  "请执行 /同步规范，将 ~/.agents/skills/lark-knowledge-config/config.json 的字段定义同步到飞书规范文档。按照 skills/lark-knowledge-sync/SKILL.md 的完整流程执行，包括更新 03_字段与状态机规范 和追加系统变更记录。" \
  >> /Users/xili/lark-knowledge/logs/sync.log 2>&1
