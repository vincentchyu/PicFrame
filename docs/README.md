# 📚 PicFrame 摄影信息卡与艺术排版方案体系索引 (Presentation Schemes Overview)

PicFrame 是一套专业的摄影艺术卡片生成与微喷排版引擎，支持多方案（Scheme）、多布局（Layout）与多模态 AI 视觉解构。本文档作为所有方案设计与技术文档的总索引。

---

## 🎨 四大展示方案总览

| 方案编号 | 方案名称 | 设计灵感与核心定位 | 默认布局 | 专属文档 |
| :--- | :--- | :--- | :--- | :--- |
| **Scheme 1** | **小红书相机镜头卡片** | 社交平台分享卡片、相机/镜头拟物化剪影与柔和主色调底色 | `portrait` (3:4) | [`docs/scheme1_architecture_and_workflow.md`](scheme1_architecture_and_workflow.md) |
| **Scheme 2** | **品牌极简水印带** | 原始画幅无损输出、底部双层参数水印栏与品牌官方 Logo | `watermark_right_logo` | [`docs/scheme2_architecture_and_workflow.md`](scheme2_architecture_and_workflow.md) |
| **Scheme 3** | **黑客终端与ASCII解构** | 极客计算机终端艺术装裱、1:1 正方形画幅自适应、等宽字符矩阵与沉底遥测仪表舱 | `gallery_ascii_terminal` | [`docs/scheme3_architecture_and_workflow.md`](scheme3_architecture_and_workflow.md) |
| **Scheme 4** | **抽象艺术编辑双联** | VLM 4阶段视觉解构、艺术造型理论提取、200 晶格退火拟合/精工手稿与诗性大标题 | `editorial_diptych` | [`docs/scheme4_architecture_and_workflow.md`](scheme4_architecture_and_workflow.md) |

---

## 🧭 文档快速导航

- 📷 **[Scheme 1: 小红书相机镜头卡片技术规范](scheme1_architecture_and_workflow.md)**：包含 3:4 / 4:3 比例自适应、相机/镜头 PNG 检索优先级与柔和背景色算法。
- 🏷️ **[Scheme 2: 品牌极简水印带技术规范](scheme2_architecture_and_workflow.md)**：包含水印栏四象限结构、品牌 Logo 自动匹配与白边装裱。
- 🖥️ **[Scheme 3: 黑客终端与 ASCII 结构解构技术规范](scheme3_architecture_and_workflow.md)**：包含自适应黑客终端 HUD 仪表舱（`gallery_ascii_terminal`）与原色 ASCII 字符解构双联（`gallery_ascii_diptych`），1:1 正方形画幅与沉底防溢出排版。
- 🏛️ **[Scheme 4: 抽象艺术编辑双联技术规范](scheme4_architecture_and_workflow.md)**：包含几何肌理双联（`editorial_diptych`）、精工手稿空间引导（`editorial_guidance`）、非对称与极简画册。
