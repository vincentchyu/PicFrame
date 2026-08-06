# PicFrame - 摄影信息卡与水印框架生成器

把一个文件夹里的照片批量生成精致的摄影信息卡与水印框架。脚本会读取 EXIF 数据，匹配相机和镜头产品 PNG，提取品牌 Logo，从照片中衍生柔和背景色，保留主图原始比例与无损像素细节，支持原始分辨率无损导出与社交平台（如小红书、朋友圈）输出压缩，并自动生成单张成品卡片和汇总预览图。

这个项目的设计原则来源于 Guizang social card workflow 和本项目的 [PROMPT.md](/Users/vincent/Developer/code/python_code/PicFrame/PROMPT.md)，但最终形态是一个独立、可复用的摄影信息卡与水印渲染 Python 工具。

英文版见 [README.en.md](/Users/vincent/Developer/code/python_code/PicFrame/README.en.md)。

## 项目预览

<p align="center">
  <img src="img/34-1.png" alt="PicFrame 3:4 摄影信息卡示例 1" width="30%">
  <img src="img/34-2.png" alt="PicFrame 3:4 摄影信息卡示例 2" width="30%">
  <img src="img/34-3.png" alt="PicFrame 3:4 摄影信息卡示例 3" width="30%">
</p>

<p align="center">
  <img src="img/43-1.png" alt="PicFrame 4:3 横版摄影信息卡示例" width="72%">
</p>

<p align="center">
  <img src="img/scheme2.jpg" alt="scheme2 摄影信息卡示例 4" width="72%">
</p>

## 功能

- 支持可配置的展示方案：当前 `scheme1` 是现有视觉体系，`portrait` / `landscape` 是方案1内部的布局选项。
- 已接入 `scheme2`（右侧 Logo 水印带方案 `watermark_right_logo`）：保持照片原始比例，在底部拼接专属水印栏。展示曝光参数（焦距/光圈/快门/ISO）、镜头型号、相机品牌 Logo、拍摄日期及版权文字，并支持可选的白边边框拓展。
- 竖图源文件可选择 `portrait` 3:4 展示或 `landscape` 4:3 横版展示。
- 使用 `exiftool` 读取照片 EXIF。
- 主图保持原始比例，不拉伸、不强行裁切填满。
- 支持横图和竖图，使用 contain-fit 展示。
- 根据照片自动生成柔和背景色。
- 相机区域和镜头区域固定，曝光参数不会把镜头信息挤下去。
- 曝光参数过多时会用 ` | ` 合并行。
- 镜头信息会从 `LensModel` / `LensID` / `Lens` 中解析型号和参数。
- 长镜头名称会自动换行或截断。
- 有 GPS 时，在顶部显示浅胶囊坐标；有海拔时追加海拔。
- 底部显示版权胶囊：`© <year> Vincent Chyu PHOTOGRAPHY - All rights reserved`。
- 年份优先从 EXIF 拍摄时间读取。
- 保留原图 ICC；sRGB 输入会写入 `sRGB IEC61966-2.1`。
- 自动生成方案/布局/格式隔离的输出目录、`contact-sheet.jpg` 和 `manifest.json`。

## 环境要求

- 推荐 macOS，因为脚本使用系统字体和 ColorSync profile。
- Python 3
- `exiftool`
- `requirements.txt` 中的 Python 包。

安装 `exiftool`：

```bash
brew install exiftool
```

创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## 目录结构

把照片放进任意源目录中，程序会直接读取该目录下的图片，并把结果写入同目录的 `PicFrame/`。下面的 `20260707/` 只是示例名称。

```text
.
├── generate_photo_cards.py
├── core/
│   ├── cli.py
│   ├── tui.py
│   ├── batch.py
│   ├── presentation.py
│   ├── renderer.py
│   ├── context.py
│   ├── output.py
│   ├── renderers/
│   │   ├── scheme1/
│   │   │   ├── renderer.py
│   │   │   ├── cards.py
│   │   │   └── assets.py
│   │   └── scheme2/
│   │       ├── renderer.py
│   │       └── watermark.py
│   ├── rendering.py
│   ├── metadata.py
│   ├── fonts.py
│   ├── config.py
│   └── utils.py
├── requirements.txt
├── config/
│   ├── presentation_schemes.json
│   └── schemes/
│       ├── scheme1/
│       │   └── gear_assets.json
│       └── scheme2/
│           └── config.yaml
├── assets/
│   ├── scheme1/
│   │   └── gear/
│   │       ├── default-camera.png
│   │       ├── default-lens.png
│   │       ├── Z6III.png
│   │       ├── NIKKOR Z 24-120mm f4 S.png
│   │       └── NIKKOR Z 35mm f1.8 S.png
│   └── scheme2/
│       ├── fonts/
│       └── logos/
└── 20260707/
    ├── DSC_0001.jpg
    ├── DSC_0002.png
    └── PicFrame/
```

方案资源按方案隔离：`scheme1` 的相机和镜头产品 PNG 放在 `assets/scheme1/gear/`，映射配置放在 `config/schemes/scheme1/gear_assets.json`；`scheme2` 的字体和 Logo 放在 `assets/scheme2/`，配置放在 `config/schemes/scheme2/config.yaml`。任务专属素材仍可放在任务文件夹的 `assets/gear/` 或任务文件夹根目录，优先级高于内置素材。

展示方案注册在 `config/presentation_schemes.json`。每个方案同时声明方案 ID、支持的 layout、输出目录、renderer import path、专属 config、resources 和 dependencies。批处理只依赖 `PresentationRenderer` 抽象基类；renderer import path 会动态加载独立方案包，因此新增方案不需要修改批处理、输出或 TUI。

例如：

```json
{
  "renderer": "core.renderers.scheme2:Scheme2Renderer",
  "config": "config/schemes/scheme2/config.yaml",
  "resources": {
    "fonts": "assets/scheme2/fonts",
    "logos": "assets/scheme2/logos"
  },
  "dependencies": ["PyYAML"]
}
```

方案2的原始配置迁移为 `config/schemes/scheme2/config.yaml`，字体和 Logo 资源迁移到 `assets/scheme2/`。方案2会保留原图比例，在底部追加水印信息带，按 EXIF 厂商匹配 Logo，并使用配置中的四个文字区域、颜色、粗体和版权设置。

## 使用方法

激活环境：

```bash
source .venv/bin/activate
```

打开 TUI 选择照片源目录：

```bash
python3 generate_photo_cards.py
```

脚本本身也可以作为可执行文件运行：

```bash
./generate_photo_cards.py
```

也可以直接指定源目录，适合批处理：

```bash
python3 generate_photo_cards.py --source 20260707
```

显式选择展示方案：

```bash
python3 generate_photo_cards.py --source 20260707 --scheme scheme1 --layout portrait
```

使用方案2：

```bash
python3 generate_photo_cards.py --source 20260707 --scheme scheme2
```

方案2当前只有 `watermark_right_logo` layout；未指定 layout 时自动使用该默认值。

选择输出压缩方式：

```bash
python3 generate_photo_cards.py --source 20260707 --compression none
python3 generate_photo_cards.py --source 20260707 --compression jpeg
```

`none` 输出无损 PNG，`jpeg` 输出 JPEG 卡片。未指定时默认为 `none`。

`--scheme` 默认是 `scheme1`，因此不传该参数时保持现有行为。`--layout` 表示所选方案内部的布局；如果照片为横图，仍按当前规则回落到方案的默认布局。

只有当原图是竖图，也就是宽度小于高度时，`--layout` 才会改变输出版式。竖图想使用横版信息卡时：

```bash
python3 generate_photo_cards.py --source 20260707 --layout landscape
```

这种竖图横版输出为 `1440 x 1080`，主图在左侧，信息栏在右侧，主图展示图四个角保留圆角。横图源文件不受这个选项影响，继续使用默认卡片布局。

不激活环境也可以直接运行：

```bash
.venv/bin/python3 generate_photo_cards.py --source 20260707
```

兼容旧任务结构时可以显式使用：

```bash
python3 generate_photo_cards.py --legacy-task 20260707
```

旧模式会读取 `20260707/src/`，并写入 `20260707/result/`。

如果需要把新模式输出到自定义目录：

```bash
python3 generate_photo_cards.py --source 20260707 --output 20260707-cards
```

新模式输出位置：

```text
20260707/PicFrame/<scheme>/<layout>/<format>/
```

每张源照片会生成：

```text
<photo_stem>_card.png 或 <photo_stem>_card.jpg
```

脚本还会生成汇总图：

```text
20260707/PicFrame/<scheme>/<layout>/<format>/contact-sheet.jpg
```

每个输出目录还会写入 `manifest.json`，记录 scheme、renderer、layout、compression、格式、源目录、输出目录和文件清单。`--legacy-task` 仍使用 `<task>/src/` 到 `<task>/result/` 的兼容路径。

## 素材匹配

`config/schemes/scheme1/gear_assets.json` 是方案1自己的 gear 配置文件，包含默认相机/镜头图，以及相机型号、镜头 ID 到 PNG 文件的映射。当前默认配置：

```json
{
  "defaults": {
    "camera": "../../../assets/scheme1/gear/default-camera.png",
    "lens": "../../../assets/scheme1/gear/default-lens.png"
  },
  "cameras": {
    "NIKON Z6_3": "../../../assets/scheme1/gear/Z6III.png",
    "Nikon Z6III": "../../../assets/scheme1/gear/Z6III.png"
  },
  "lenses": {
    "NIKKOR Z 24-120mm f/4 S": "../../../assets/scheme1/gear/NIKKOR Z 24-120mm f4 S.png",
    "NIKKOR Z 35mm f/1.8 S": "../../../assets/scheme1/gear/NIKKOR Z 35mm f1.8 S.png"
  }
}
```

如果相机或镜头无法匹配，脚本会打印 warning，并使用 `default-camera.png` 或 `default-lens.png`，不会中断整个批处理。后续要支持更多机型，只需要把 EXIF 中的 `Model` / `CameraModelName` 或 `LensModel` / `LensID` / `Lens` 字符串加入 `config/schemes/scheme1/gear_assets.json`，并把对应 PNG 放进 `assets/scheme1/gear/`。

iPhone 的 `LensModel` / `LensID` 会包含当前焦段和光圈，例如 `iPhone 14 Pro back triple camera 6.86mm f/1.78`。素材匹配时会额外尝试模组级 key `iPhone 14 Pro back triple camera`，因为 iPhone 不可换镜头，PNG 应代表整组摄像头模组；卡片上的镜头文字仍保留完整焦段和光圈。

## 镜头文字解析

镜头显示不再硬编码为 `Nikon`，也不会粗暴删除 `NIKKOR Z`。脚本会在完整镜头字符串中找到 `mm` 之前的焦段数字，把数字之前的内容作为镜头型号，把焦段和光圈继续放在参数位置。

示例：

```text
NIKKOR Z 24-120mm f/4 S
型号：NIKKOR Z
参数：24-120mm f/4 S

iPhone 13 Pro back triple camera 9mm f/2.8
型号：iPhone 13 Pro back triple camera
参数：9mm f/2.8
```

参数中的独立 `S` 会用更重的字重显示，因为它代表 Nikon S-Line 高质量镜头。

## 输出说明

- 主图使用 contain-fit，不裁切、不拉伸。
- 背景色每张照片单独生成，并柔化到适合 UI 阅读的范围。
- 相机和镜头区域固定，文字不会互相侵入。
- 顶部 GPS 胶囊只在照片有 EXIF GPS 时显示；如果有海拔，格式类似 `43°48'N 87°34'E · 1018m`。
- ICC profile 会尽量继承，方便 Preview/Finder 和发布流程保持颜色一致。

## 开发说明

`generate_photo_cards.py` 现在只是可执行入口，核心实现拆在 `core/` 包中：

- `core/cli.py`：命令行参数和默认 TUI 入口。
- `core/tui.py`：`curses` 目录选择、布局选择和进度显示。
- `core/presentation.py`：展示方案注册、配置、资源和依赖声明。
- `core/renderer.py`：共享 `RendererContext`、`PresentationRenderer` 抽象基类和动态加载器。
- `core/context.py`：共享 EXIF、背景色和曝光上下文，不包含具体方案布局。
- `core/renderers/scheme1/`：方案1独立包，包含 renderer (`renderer.py`)、原始分辨率 3:4/4:3 卡片布局与绘制 (`cards.py`) 及器材 PNG 查找 (`assets.py`)。
- `core/renderers/scheme2/`：方案2独立包，包含 renderer (`renderer.py`) 及原始分辨率水印带绘制 (`watermark.py`)。
- `core/output.py`：PNG/JPEG 输出策略和统一编码。
- `core/batch.py`：只负责源目录扫描、renderer/context 编排、输出文件夹和 legacy 兼容。
- `core/rendering.py`：跨方案可复用的 Pillow 图像 primitive、renderer 调用入口、统一卡片输出压缩 (`apply_card_compression`) 和 contact sheet。
- `core/metadata.py`：EXIF、GPS、海拔、镜头名、ICC profile 处理。
- `core/fonts.py`：macOS 字体查找和 `.ttc` face index。
- `core/config.py`：路径、画布尺寸、扩展名、布局常量。

展示方案和 layout 的关系是：一个批次选择一个 scheme，scheme 再选择一个 layout；输出格式由压缩策略决定。当前 `scheme1` 注册了 `portrait` 和 `landscape`。新增方案时只需在 `config/presentation_schemes.json` 声明 renderer/config/resources/dependencies，并新增继承 `PresentationRenderer` 的 renderer 模块。

布局是确定性的，不会因为文字长短改变整体结构：

- 默认画布：`1080 x 1440`
- 竖图源文件选择 `landscape` 时画布：`1440 x 1080`
- 默认主图区域：固定顶部区域
- 竖图源文件横版布局：主图在左侧，信息栏在右侧
- 信息区：固定相机区域和固定镜头区域
- 字体：显式 `.ttc` face index，避免误加载粗体
- 汇总图：生成卡片后自动创建

未来修改请先阅读 [PROMPT.md](/Users/vincent/Developer/code/python_code/PicFrame/PROMPT.md)，里面记录了设计和实现约束。
