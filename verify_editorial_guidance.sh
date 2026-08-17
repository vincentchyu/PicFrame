#!/usr/bin/env bash
set -e

# ==============================================================================
# 🏛️ Scheme 4 多题材精选照片批量验证脚本
# 支持可选参数：
#   --layout <name>   (默认: editorial_guidance)
#   --debug           (默认: 关闭)
#   --compression <c> (默认: jpeg)
# ==============================================================================

# 默认参数
LAYOUT="editorial_guidance"
DEBUG_FLAG=""
COMPRESSION="jpeg"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --layout|-l)
      LAYOUT="$2"
      shift 2
      ;;
    --debug|-d)
      DEBUG_FLAG="--debug"
      shift
      ;;
    --compression|-c)
      COMPRESSION="$2"
      shift 2
      ;;
    --help|-h)
      echo "用法: $0 [选项]"
      echo ""
      echo "选项:"
      echo "  -l, --layout <name>      指定布局 (默认: editorial_guidance, 可选: editorial_diptych 等)"
      echo "  -d, --debug              开启 Debug 模式，保存全流程中间分析与矢量图层"
      echo "  -c, --compression <fmt>  压缩格式 (默认: jpeg, 可选: none, jpeg)"
      echo "  -h, --help               显示帮助信息"
      echo ""
      echo "示例:"
      echo "  $0                       # 默认精工细线草图风"
      echo "  $0 --debug               # 开启 Debug 输出"
      echo "  $0 -l editorial_diptych  # 切换为 200 晶格几何肌理风"
      echo "  $0 -l editorial_guidance --debug"
      exit 0
      ;;
    *)
      # 兼容位置参数传入 layout
      if [[ "$1" != -* ]]; then
        LAYOUT="$1"
        shift
      else
        echo "⚠️ 未知参数: $1 (使用 --help 查看用法)"
        exit 1
      fi
      ;;
  esac
done

echo ""
echo "══════════════════════════════════════════════════════════════════════"
echo "🚀 开始批量执行 Scheme 4 验证"
echo "📐 选用布局 (Layout): $LAYOUT"
echo "🗂️ 压缩格式 (Compression): $COMPRESSION"
if [[ -n "$DEBUG_FLAG" ]]; then
  echo "🐞 Debug 模式: 已开启 (中间图层将保存至各照片的 _debug 目录)"
else
  echo "🐞 Debug 模式: 未开启 (仅输出最终卡片)"
fi

# 从 test 目录中自动寻找所有照片并随机选取 10 张
NUM_SAMPLES=10
SELECTED_PHOTOS=($(python3 -c '
import os, random
valid_exts = {".jpg", ".jpeg", ".png"}
photos = [
    os.path.join("test", f)
    for f in os.listdir("test")
    if os.path.isfile(os.path.join("test", f)) and os.path.splitext(f.lower())[1] in valid_exts
]
count = min(10, len(photos))
sample = random.sample(photos, count) if photos else []
for p in sample:
    print(p)
'))

TOTAL=${#SELECTED_PHOTOS[@]}

if [[ $TOTAL -eq 0 ]]; then
  echo "⚠️ 未在 test/ 目录下找到任何图片文件！"
  exit 1
fi

echo "📸 已从 test/ 目录下随机挑选 $TOTAL 张照片进行验证:"
for p in "${SELECTED_PHOTOS[@]}"; do
  echo "  - $p"
done
echo "══════════════════════════════════════════════════════════════════════"
echo ""

INDEX=1
START_TIME=$(date +%s)

for PHOTO_PATH in "${SELECTED_PHOTOS[@]}"; do
  FILENAME=$(basename "$PHOTO_PATH")
  echo "----------------------------------------------------------------------"
  echo "[$INDEX/$TOTAL] 正在渲染: $FILENAME ($PHOTO_PATH)"
  echo "----------------------------------------------------------------------"
  
  # 执行卡片生成
  python3 generate_photo_cards.py \
    --source test \
    --scheme scheme4 \
    --layout "$LAYOUT" \
    --compression "$COMPRESSION" \
    $DEBUG_FLAG \
    --photo "$PHOTO_PATH"
    
  INDEX=$((INDEX + 1))
done

END_TIME=$(date +%s)
COST=$((END_TIME - START_TIME))

echo ""
echo "══════════════════════════════════════════════════════════════════════"
echo "🎉 批量验证全部完成！共渲染 $TOTAL 张卡片，总耗时: ${COST}s"
echo "📁 生成产物目录: test/PicFrame/scheme4/${LAYOUT}/${COMPRESSION}/"
echo "🖼️ 索引大图: test/PicFrame/scheme4/${LAYOUT}/${COMPRESSION}/contact-sheet.jpg"
echo "══════════════════════════════════════════════════════════════════════"
echo ""
