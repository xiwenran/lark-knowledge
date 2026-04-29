#!/bin/bash
# run_episode.sh — All In Podcast 一键处理脚本
#
# 用法：
#   ./run_episode.sh <YouTube_URL> <record_id>
#   ./run_episode.sh https://youtube.com/watch?v=xxx recXXXXXX
#
# 环境变量（必须）：
#   ARK_API_KEY — 火山引擎 API Key
#
# 可选参数：
#   --segment-minutes N   每段时长，默认 15
#   --skip-checks         跳过 Haiku/Opus 核查
#   --dry-run             只生成预览，不写入飞书

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
YOUTUBE_URL="$1"
RECORD_ID="$2"
SEGMENT_MINUTES="${SEGMENT_MINUTES:-15}"

# 解析可选参数
SKIP_CHECKS=""
DRY_RUN=""
for arg in "${@:3}"; do
  case $arg in
    --skip-checks) SKIP_CHECKS="--skip-checks" ;;
    --dry-run) DRY_RUN="--dry-run" ;;
    --segment-minutes=*) SEGMENT_MINUTES="${arg#*=}" ;;
  esac
done

if [ -z "$YOUTUBE_URL" ] || [ -z "$RECORD_ID" ]; then
  echo "用法: $0 <YouTube_URL> <record_id> [--skip-checks] [--dry-run]"
  exit 1
fi

if [ -z "$ARK_API_KEY" ]; then
  echo "❌ 缺少 ARK_API_KEY 环境变量"
  echo "   运行: export ARK_API_KEY=your_key_here"
  exit 1
fi

# 提取视频 ID
VIDEO_ID=$(echo "$YOUTUBE_URL" | grep -oP '(?<=v=)[^&]+' || echo "$YOUTUBE_URL" | grep -oP '(?<=youtu.be/)[^?]+')
WORK_DIR="/tmp/allin_${VIDEO_ID}"
mkdir -p "$WORK_DIR"

VTT_FILE="$WORK_DIR/subtitles.en.vtt"
SEGMENTS_FILE="$WORK_DIR/segments.json"
BILINGUAL_FILE="$WORK_DIR/bilingual.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All In Podcast 处理流水线"
echo "  视频 ID : $VIDEO_ID"
echo "  Record  : $RECORD_ID"
echo "  工作目录: $WORK_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: 下载字幕
if [ -f "$VTT_FILE" ]; then
  echo "[Step 1/4] 字幕已存在，跳过下载"
else
  echo "[Step 1/4] 下载英文字幕..."
  yt-dlp --write-auto-sub --sub-lang en --sub-format vtt --skip-download \
    --output "$WORK_DIR/subtitles" "$YOUTUBE_URL"
  # yt-dlp 输出文件名含语言后缀，重命名
  mv "$WORK_DIR/subtitles.en.vtt" "$VTT_FILE" 2>/dev/null || \
    mv "$WORK_DIR"/subtitles*.vtt "$VTT_FILE" 2>/dev/null || true
  if [ ! -f "$VTT_FILE" ]; then
    echo "❌ 字幕下载失败，请检查 YouTube URL 或手动提供 .vtt 文件"
    exit 1
  fi
  echo "   ✅ 字幕已下载: $VTT_FILE"
fi

# Step 2: VTT 清洗
if [ -f "$SEGMENTS_FILE" ]; then
  echo "[Step 2/4] 分段文件已存在，跳过清洗"
else
  echo "[Step 2/4] 清洗 VTT，按 ${SEGMENT_MINUTES} 分钟分段..."
  python3 "$SCRIPT_DIR/vtt_clean.py" "$VTT_FILE" "$SEGMENTS_FILE" \
    --segment-minutes "$SEGMENT_MINUTES"
fi

# Step 3: Doubao 翻译（支持断点续传）
echo "[Step 3/4] 调用 Doubao-Seed-2.0-pro 翻译..."
python3 "$SCRIPT_DIR/translate_bilingual.py" "$SEGMENTS_FILE" "$BILINGUAL_FILE"

# Step 4: 组装页面 + 写入飞书
echo "[Step 4/4] 组装飞书页面..."
python3 "$SCRIPT_DIR/build_feishu_page.py" "$BILINGUAL_FILE" \
  --record-id "$RECORD_ID" \
  $SKIP_CHECKS \
  $DRY_RUN

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 全部完成"
echo "  临时文件保留在: $WORK_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
