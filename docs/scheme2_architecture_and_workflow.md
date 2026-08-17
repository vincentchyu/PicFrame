# 🏷️ Scheme 2 品牌极简水印带 (Semi-Utils Watermark) 技术方案与交互流程规范

本文档详细记录 **Scheme 2（Semi-Utils 风格水印带方案）** 的设计原则、水印布局结构、品牌 Logo 映射机制与配置规范。

---

## 1. 核心设计哲学与定位

Scheme 2 采用极简暗房水印带风格，专为**无损保持照片原始比例与高精度输出**而设计：
- **核心原则**：不裁剪、不变形照片本身的像素，在照片底部无缝扩展一条高质感的纯白/纯黑水印栏；
- **视觉平衡**：左侧展示机身/镜头型号与核心曝光参数，右侧展示品牌专属 Logo、地理信息与摄影师签名，实现左右对称与视觉稳定。

---

## 2. 水印栏布局结构 (watermark_right_logo)

水印栏高度自适应于照片总高度的约 8%~12%，内部划分为四大信息象限：

```
+------------------------------------------------------------------------+
|                                                                        |
|                          照片主画幅 (100% 原比例)                       |
|                                                                        |
+------------------------------------+-----------------------------------+
| [左上] 镜头型号 / 机身型号          | [右上] 拍摄地理坐标 (GeoInfo)     |
| [左下] 焦距 · 光圈 · 快门 · ISO     | [右下] 摄影师签名 (Vincent Chyu)  |
|                                    | [Logo] 品牌图标 (NIKON / DJI 等)  |
+------------------------------------+-----------------------------------+
```

- **左上 (left_top)**：LensMake_LensModel（如 NIKKOR Z 24-120mm f/4 S）；
- **左下 (left_bottom)**：Param（如 24mm  f/4.0  1/125s  ISO 100）；
- **右上 (right_top)**：GeoInfo 或拍摄日期；
- **右下 (right_bottom)**：Custom 摄影师签名；
- **品牌 Logo**：依据 EXIF 制造商字段（Make）自动匹配对应的官方高清矢量/透明 Logo 图标（位于 assets/scheme2/logos/）。

---

## 3. 配置文件与字体规范 (config/schemes/scheme2/config.yaml)

- **排版字体**：
  - 中文/西文常规体：AlibabaPuHuiTi-2-45-Light.otf / Roboto-Regular.ttf
  - 西文中粗体：AlibabaPuHuiTi-2-85-Bold.otf / Roboto-Medium.ttf
- **Logo 映射表**：
  - NIKON / Canon / SONY / DJI / Apple / FUJIFILM
- **白边控制 (white_margin)**：
  - enable: true，四周带有极细画廊白边留白，增强装裱立体感。

---

## 4. 产物与 CLI 调用指南

```bash
# 1. 批量处理源目录
python3 generate_photo_cards.py --source test --scheme scheme2 --layout watermark_right_logo --compression jpeg

# 2. 单张照片处理
python3 generate_photo_cards.py --source test --scheme scheme2 --layout watermark_right_logo --photo test/DSC_2026-02-21_4182_edit_nx.JPG
```
