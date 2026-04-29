#!/bin/bash
# run_episode.sh — All In Podcast 字幕下载 + 翻译（自动化前三步）
#
# 职责：下载字幕 → VTT清洗 → Doubao翻译，输出 bilingual.json
# AI 分析（Haiku/Sonnet/Opus）和飞书写入由 Claude Code 主会话负责（见 SKILL.md）
#
# 用法：
#   export ARK_API_KEY=your_key
#   ./run_episode.sh <YouTube_URL> <record_id>
#
# 输出：/tmp/allin_<VIDEO_ID>/bilingual.json
# 中间文件：subtitles.en.vtt, segments.json

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
YOUTUBE_URL="$1"
RECORD_ID="$2"
SEGMENT_MINUTES="${SEGMENT_MINUTES:-15}"

# 解析可选参数
for arg in "${@:3}"; do
  case $arg in
    --segment-minutes=*) SEGMENT_MINUTES="${arg#*=}" ;;
  esac
done

if [ -z "$YOUTUBE_URL" ] || [ -z "$RECORD_ID" ]; then
  echo "用法: $0 <YouTube_URL> <record_id> [--segment-minutes=N]"
  exit 1
fi

if [ -z "$ARK_API_KEY" ]; then
  echo "❌ 缺少 ARK_API_KEY 环境变量"
  echo "   运行: export ARK_API_KEY=your_key_here"
  exit 1
fi

# 提取视频 ID（支持 ?v=xxx 和 youtu.be/xxx 两种格式）
VIDEO_ID=$(echo "$YOUTUBE_URL" | grep -oP '(?<=v=)[^&]+' 2>/dev/null || \
           echo "$YOUTUBE_URL" | grep -oP '(?<=youtu.be/)[^?]+' 2>/dev/null || \
           echo "unknown")
WORK_DIR="/tmp/allin_${VIDEO_ID}"
mkdir -p "$WORK_DIR"

VTT_FILE="$WORK_DIR/subtitles.en.vtt"
SEGMENTS_FILE="$WORK_DIR/segments.json"
BILINGUAL_FILE="$WORK_DIR/bilingual.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All In Podcast 字幕下载 + 翻译"
echo "  视频 ID : $VIDEO_ID"
echo "  Record  : $RECORD_ID"
echo "  工作目录: $WORK_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: 下载字幕
if [ -f "$VTT_FILE" ]; then
  echo "[Step 1/3] 字幕已存在，跳过下载"
else
  echo "[Step 1/3] 下载英文字幕..."
  yt-dlp --write-auto-sub --sub-lang en --sub-format vtt --skip-download \
    --output "$WORK_DIR/subtitles" "$YOUTUBE_URL"
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
  echo "[Step 2/3] 分段文件已存在，跳过清洗"
else
  echo "[Step 2/3] 清洗 VTT，按 ${SEGMENT_MINUTES} 分钟分段..."
  python3 "$SCRIPT_DIR/vtt_clean.py" "$VTT_FILE" "$SEGMENTS_FILE" \
    --segment-minutes "$SEGMENT_MINUTES"
fi

# Step 3: Doubao 翻译（支持断点续传）
echo "[Step 3/3] 调用 Doubao-Seed-2.0-pro 翻译..."
python3 "$SCRIPT_DIR/translate_bilingual.py" "$SEGMENTS_FILE" "$BILINGUAL_FILE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 翻译完成！bilingual.json 已生成"
echo "  路径: $BILINGUAL_FILE"
echo ""
echo "  下一步：在 Claude Code 中执行 AI 分析"
echo "  触发词：allin逐字稿 分析 $RECORD_ID $BILINGUAL_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
