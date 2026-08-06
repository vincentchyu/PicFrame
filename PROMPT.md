# 摄影信息卡生成约束

本文档定义 `generate_photo_cards.py` 的设计和实现约束。英文版见 [PROMPT.en.md](/Users/vincent/Developer/code/python_code/PicFrame/PROMPT.en.md)。

项目受到 Guizang social card workflow 的启发：成品应该是一张完整、克制、可发布的社交媒体图片，而不是原始 EXIF 数据表。当前目录中的 `template.png` 只能作为布局参考，不是必须逐像素复刻的模板。

## 目标

遍历用户选择的源目录中的图片，为每张图片在该目录的 `PicFrame/` 中生成一张摄影信息卡。

成品应满足：

- 突出展示照片本身。
- 保持照片原始比例。
- 清晰展示相机、曝光、镜头、GPS、海拔、版权信息。
- 使用照片自动生成柔和背景色。
- 风格安静、精确，接近摄影产品信息卡。
- 避免文字重叠、溢出和无意义装饰。
- 器材文字是辅助信息，不能喧宾夺主。

## 平台

- 目标平台：小红书 / Xiaohongshu / Rednote
- 默认输出比例：`3:4`
- 默认输出尺寸：`1080 x 1440`
- 当源图为竖图（宽度小于高度）且选择 `landscape` 时，输出比例为 `4:3`，输出尺寸为 `1440 x 1080`
- 输出格式：PNG cards plus a JPEG contact sheet

## 目录约定

默认源目录结构：

```text
<source>/
├── DSC_0001.jpg
├── DSC_0002.png
└── PicFrame/
```

如果 `PicFrame/` 不存在，脚本应自动创建。

默认可执行入口行为：

- 运行 `python3 generate_photo_cards.py` 时打开终端 TUI，用于选择源目录。
- 运行 `python3 generate_photo_cards.py --source <source>` 时不打开 TUI，直接处理该源目录。
- 运行 `python3 generate_photo_cards.py --source <source> --layout landscape` 时，仅对源图宽度小于高度的竖图使用横版展示。
- 运行 `python3 generate_photo_cards.py --legacy-task <task>` 时使用旧兼容行为：读取 `<task>/src/`，写入 `<task>/result/`。

支持的源文件格式：

- `.jpg`
- `.jpeg`
- `.png`
- `.tif`
- `.tiff`

## 展示方案约定

展示方案和方案内布局是两层概念：

- `scheme1` 是当前已有的摄影信息卡视觉体系。
- `portrait` / `landscape` 是 `scheme1` 内部的布局选项，不代表独立展示方案。
- 方案注册统一维护在 `config/presentation_schemes.json`。
- 每个批次选择一个展示方案，再选择该方案支持的 layout；同一批次不混用多个方案。
- 新方案应新增配置项和独立 renderer，不应把方案差异继续堆叠到 `portrait` / `landscape` 分支中。
- 方案配置只表达 ID、名称、支持的 layout、默认 layout 和 renderer ID；具体坐标、字体和绘制细节留在 Python renderer 中。
- `scheme2` 为右侧 Logo 水印带布局 (`watermark_right_logo`)；配置位于 `config/schemes/scheme2/config.yaml`，字体和品牌 Logo 在 `assets/scheme2/`。其保留照片原始比例并在底部拼接包含曝光参数、镜头型号、品牌 Logo、日期与版权的水印栏。
- 方案2保留原图比例，在底部追加水印信息带；方案2自己的 GPS、Logo 和版权信息不再叠加方案1的顶部/底部胶囊。

## 素材

相机和镜头产品 PNG 按以下顺序查找：

1. 任务文件夹的 `assets/gear/`
2. 任务文件夹
3. 所选方案的内置素材目录，例如 `assets/scheme1/gear/`
4. 脚本所在文件夹

当前内置素材：

```text
assets/scheme1/gear/default-camera.png
assets/scheme1/gear/default-lens.png
assets/scheme1/gear/Z6III.png
assets/scheme1/gear/NIKKOR Z 24-120mm f4 S.png
assets/scheme1/gear/NIKKOR Z 35mm f1.8 S.png
```

方案1的相机和镜头匹配维护在 `config/schemes/scheme1/gear_assets.json` 中。当前配置：

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

无法匹配相机或镜头时：

- 输出 warning。
- 相机使用默认相机 PNG。
- 使用默认镜头 PNG。
- 不要中断整个批处理。
- 后续支持更多机型时，优先扩展 `config/schemes/scheme1/gear_assets.json` 并把 PNG 放进 `assets/scheme1/gear/`，不要把型号映射写死在 Python 代码里。
- iPhone 的 `LensModel` / `LensID` 可能是 `iPhone 14 Pro back triple camera 6.86mm f/1.78`；素材匹配时应额外尝试 `iPhone 14 Pro back triple camera` 这种模组级 key，但镜头文字显示仍保留完整焦段和光圈。

## 布局

布局必须是确定性的，不应因为文字长短而改变整体结构。

画布：

```text
default: 1080 x 1440
portrait source + landscape layout: 1440 x 1080
```

主图：

- 默认固定在顶部照片区域。
- 仅当源图是竖图且选择 `landscape` 时，主图固定在左侧照片区域，信息栏在右侧。
- 保持源图比例。
- 使用 contain-fit。
- 不拉伸。
- 不为了填满区域而裁切。
- 默认主图顶部圆角。
- 竖图横版展示时，主图四个角都使用圆角。

外层卡片：

- 浅色页面背景上的圆角卡片。
- 柔和阴影。
- 卡片背景色由照片生成。

信息区域：

- 位于主图下方。
- 拆成两个固定区域：相机区域、镜头区域。
- 相机产品图、镜头产品图位置固定。
- 相机文字、镜头文字起点固定。
- 曝光参数绝不能把镜头区域往下推。
- 器材文字字号要克制，不能变成主标题。

## 相机区域

右侧内容：

```text
Camera model
Exposure parameters
```

相机型号示例：

```text
Nikon Z6III
iPhone 13 Pro
```

曝光参数可包含：

- Format, when useful and not redundant
- Aperture
- Shutter speed
- ISO
- Focal length
- Exposure compensation
- White balance

规则：

- 缺失字段自动隐藏。
- 参数过多时压缩成更少行。
- 使用 ` | ` 把短参数合并到同一行。
- 相机型号应比参数略强，但仍是辅助层级。

示例：

```text
F5.6 | 1/30
ISO 6400 | 34mm
Auto
```

## 镜头区域

右侧内容：

```text
Lens family
Lens parameters
```

镜头字段优先级：

1. `LensModel`
2. `LensID`
3. `Lens`

镜头文字解析硬约束：

- 不要把镜头型号硬编码为 `Nikon`。
- 不要粗暴删除 `NIKKOR Z`。
- 在完整镜头字符串中找到 `mm` 之前的焦段数字。
- 焦段数字之前的部分是镜头型号，显示在型号行。
- 从焦段数字开始到结尾的部分是镜头参数，显示在参数行。
- 如果参数里有独立的 `S`，`S` 应加粗显示，因为它代表 Nikon S-Line 高质量镜头。

示例：

```text
LensID: iPhone 13 Pro back triple camera 9mm f/2.8
镜头型号：iPhone 13 Pro back triple camera
镜头参数：9mm f/2.8

LensID: NIKKOR Z 24-120mm f/4 S
镜头型号：NIKKOR Z
镜头参数：24-120mm f/4 S
```

布局规则：

- 镜头文字要和镜头产品图所在区域对齐。
- 长镜头名要换行。
- 控制最大行数。
- 不允许溢出右侧文本列。
- 镜头型号字号应小于相机型号，避免抢主图注意力。

## GPS 胶囊

如果 EXIF 中有 GPS，在画布顶部居中显示一个轻量胶囊。

格式：

```text
23°09'N 113°16'E
23°09'N 113°16'E · 1018m
```

规则：

- 转成度/分格式。
- 使用 `N/S/E/W`。
- 不显示纯小数。
- 如果存在 `GPSAltitude` 或 `Altitude`，追加海拔，单位为 `m`。
- 海拔显示为整数米，例如 `1018m`。
- 支持海平面以下的高度为负值。
- 不放在主图内容上。
- 胶囊背景从卡片背景色浅化得到。
- 要和底部版权胶囊呼应，但不能喧宾夺主。
- 没有 GPS 时完全省略。

## 版权胶囊

底部居中显示版权胶囊：

```text
© <year> Vincent Chyu PHOTOGRAPHY - All rights reserved
```

规则：

- `<year>` 优先从 EXIF 拍摄时间读取。
- 字段优先级：
  - `DateTimeOriginal`
  - `CreateDate`
  - `SubSecDateTimeOriginal`
  - `ModifyDate`
- 没有年份时使用保守兜底。
- 胶囊背景从卡片背景色浅化得到。
- 和顶部 GPS 胶囊保持视觉关系。
- 不要贴边或被裁切。

## EXIF

使用：

```bash
exiftool -json <image>
```

相机字段：

- `CameraModelName`
- `Model`
- `Make`

镜头字段：

- `LensModel`
- `LensID`
- `Lens`

曝光字段：

- `Format`
- `FNumber`
- `Aperture`
- `ExposureTime`
- `ShutterSpeed`
- `ISO`
- `FocalLength`
- `ExposureCompensation`
- `WhiteBalance`

GPS 字段：

- `GPSLatitude`
- `GPSLongitude`
- `GPSLatitudeRef`
- `GPSLongitudeRef`
- `GPSPosition`
- `GPSAltitude`
- `GPSAltitudeRef`
- `Altitude`

日期字段：

- `DateTimeOriginal`
- `CreateDate`
- `SubSecDateTimeOriginal`
- `ModifyDate`

## 背景颜色

根据源照片生成卡片背景色。

算法：

1. 以 RGB 打开照片。
2. 缩小图片提高速度。
3. 忽略四周 5%。
4. 对采样像素做少量聚类。
5. 选择占比最高的颜色组。
6. 转为 HLS。
7. 提高亮度到柔和 UI 范围。
8. 降低饱和度。
9. 作为卡片背景色。

背景应与照片有关，但不能直接使用刺眼的原始主色。

## 色彩管理

保留源图的颜色行为。

规则：

- 如果源图嵌入 ICC profile，输出图也使用该 ICC profile。
- 如果源图标记为 sRGB 但没有嵌入 ICC，则写入系统 sRGB profile。
- macOS 优先使用：

```text
/System/Library/ColorSync/Profiles/sRGB Profile.icc
```

期望 sRGB 输出描述：

```text
sRGB IEC61966-2.1
```

汇总图继承第一张成品图的 ICC profile。

## 字体

必须显式指定 `.ttc` 字体 face index，不要依赖默认第一个 face。

首选 macOS 字体：

```text
Avenir Next.ttc
```

Face indices:

```text
Regular -> index 7
Medium  -> index 5
```

Fallbacks:

- Helvetica Neue
- SFNS
- Arial
- DejaVu Sans

原因：

某些 `.ttc` 默认加载 Bold face，会导致卡片太粗、太挤。显式 index 可以保证字体稳定。

风格：

- 相机型号和镜头型号可用 Medium，但字号要克制。
- 参数使用 Regular。
- 参数里的独立 `S` 可以用 Medium 强调。
- 不使用等宽英文字体。
- 保持安静、清晰、可读。
- 器材信息必须服务照片，不要比照片更抢眼。

## 文本安全

硬约束：

- 不允许文字重叠。
- 不允许文字进入另一个固定区域。
- 不允许贴边。
- 长镜头名必须换行或截断。
- 曝光字段先压缩，再考虑其它布局调整。
- 底部版权胶囊不能和阴影或画布边缘冲突。

## 汇总图

生成所有卡片后，同时创建：

```text
PicFrame/contact-sheet.jpg
```

规则：

- 使用小缩略图。
- 显示文件名标签。
- 便于快速检查。
- 尽可能保留 ICC profile。

## 借鉴的 Guizang Social Card 原则

这里只采用与本工具相关的原则：

- 表达优先，一眼能看懂。
- 使用真实照片作为证据，不用装饰填充。
- 不添加随机贴纸、色块、圆点、blob。
- 不使用嵌套卡片。
- 不允许文字溢出或碰撞。
- 3:4 卡片要充分利用画布。
- 先给可视输出，再根据视觉反馈迭代。

本项目不复制 Guizang skill 模板，只吸收其社交卡设计纪律，并保留 Python 图片生成工具的实现形态。

## 代码结构

`generate_photo_cards.py` 只作为可执行入口，不能继续堆叠制图、EXIF 或 TUI 逻辑。核心实现放在 `core/` 包中：

- `core/cli.py`：命令行参数、默认 TUI 启动、错误出口。
- `core/tui.py`：标准库 `curses` 目录选择、布局选择、进度和错误显示。
- `core/presentation.py`：展示方案配置、方案/layout 校验和解析。
- `core/renderer.py`：方案 renderer 抽象、动态加载，以及所选方案的 config/resources/dependencies 校验。
- `core/renderers/scheme1/`：方案1独立包，包含 renderer (`renderer.py`)、原始分辨率 3:4/4:3 卡片绘制 (`cards.py`) 和器材素材查找 (`assets.py`)。
- `core/renderers/scheme2/`：方案2独立包，包含 renderer (`renderer.py`) 和原始分辨率水印带绘制 (`watermark.py`)。
- `core/batch.py`：源目录扫描、输出目录、批量生成、旧任务结构兼容。
- `core/renderer.py`：方案 renderer 抽象。
- `core/output.py`：PNG/JPEG 输出策略与编码。
- `core/rendering.py`：公共 Pillow 图像 primitive、renderer 调用入口、统一卡片输出压缩 (`apply_card_compression`) 和 contact sheet。
- `core/metadata.py`：EXIF、GPS、海拔、镜头名解析、ICC profile。
- `core/fonts.py`：字体查找、`.ttc` face index 和 `font()`。
- `core/config.py`：项目路径、画布尺寸、扩展名、布局常量。
- `core/utils.py`：无领域状态的通用小工具。

修改原则：

- 改 CLI/TUI 时不要碰制图核心。
- 改某个方案的布局或图像生成时优先在对应的 `core/renderers/` 模块内完成。
- 改 EXIF、GPS、ICC、镜头解析时优先在 `metadata.py` 内完成。
- 改素材搜索或型号映射读取时优先在对应方案的 renderer 资源模块和 `config/schemes/` 配置内完成。
- 保持 `generate_photo_cards.py` 为薄入口，避免重新变成千行脚本。

## 验证清单

修改完成前检查：

- 用真实目录运行脚本。
- 至少打开一张横图结果。
- 如有竖图，至少打开一张竖图结果。
- 确认输出尺寸为 `1080 x 1440`。
- 确认主图比例未改变。
- 确认相机和镜头区域固定。
- 确认长曝光参数用 ` | ` 合并。
- 确认长镜头文本安全换行。
- 确认 LensID 示例能正确拆分为型号和参数。
- 确认参数里的独立 `S` 加粗显示。
- 确认 GPS 只在有 GPS 时出现。
- 确认有海拔时 GPS 胶囊追加海拔。
- 确认版权年份来自 EXIF。
- 确认输出 ICC 被继承或设置为 sRGB。
- 默认源目录模式确认存在 `PicFrame/contact-sheet.jpg`。
- 显式 `--legacy-task` 兼容模式确认存在 `result/contact-sheet.jpg`。
