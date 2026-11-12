---
name: image-to-cad
description: 将建筑平面、建筑剖面和景观图重构为可编辑的分层 DXF，或从已确认的钢笔线稿描摹笔触。用于把扫描图、图纸和参考图片变成可继续设计的 CAD 底图。
---

# 图片转 CAD · Image to CAD

先明确交付意图，再选择转换命令。没有尺寸依据时使用未校准像素单位。

| 意图 | 输入与命令 | 验收重点 |
| --- | --- | --- |
| Reconstruct 重构 | 建筑平面 `building`、建筑剖面 `section`、景观设计图 `landscape` | 开口、连接和空间关系保留。几何适度规整，构件与图层可编辑。 |
| Trace 描摹 | 钢笔画、插画、Logo 或需要保留原始视觉特征的线稿，用确认后的白底图运行 `pen` | 保留曲线、轮廓、粗细、纹理与留白，用分层 HATCH 表达。 |

## 执行

1. **读原图并确定范围。** 已明确的范围直接沿用。只有影响交付的分歧才集中确认，并提供建议默认值。剖面先辨认墙、板、梁、柱、洞口、坡道与楼梯。保留必要基础轮廓，省略土方和材料填充、人物、洁具及无关装饰。辨别笔画线宽与真实构件双边界。参见[范围、提示词与验收清单](references/scope.md)。
2. **选输入路线。** 清晰图直接整理布局。密集图可生成简化稿，或把提示词交接给用户，也可回到原图整理。Reconstruct 简化允许拉直、统一接近的厚度和适度移动端点。逐区对照源图核查开口、坡道方向、墙板柱连接与构件数量。生成稿经用户确认同一版本后才传 `--approved`，可用 `--approved-sha256` 固定版本。已有干净线稿可以先用 `section --input-route linework` 提取普通线条，再按原图判断语义。程序提取的线条先留在未分类层。
3. **表达可编辑构件。** 保护真实开口和楼梯踏步。对不明类型保留可见边界和疑问，避免补画没有图像依据的墙、柱或楼层。剖面用构件 ID、宿主和坡道端点关系写布局，规则见[剖面规范](references/section.md)。其他命令见[运行说明](references/runtime.md)或 [English runtime guide](references/runtime.en.md)。
4. **回读和交付。** 查看原图与实际 DXF 对照，核查关系、几何、可编辑性和图面整洁。交付 DXF、预览、布局、报告和对照页，列出需要人工确认的问题。说明布局是助手读图、人工准备、模型辅助还是程序提取。主要关系够用且底图便于继续设计即可交付。

For editable architectural plans, sections and landscapes, use Reconstruct and preserve topology while regularizing geometry. For appearance-sensitive artwork, use Trace and retain the existing layered HATCH workflow. See the [English runtime guide](references/runtime.en.md) for commands.
