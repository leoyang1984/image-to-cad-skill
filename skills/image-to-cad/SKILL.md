---
name: image-to-cad
description: 将建筑平面、剖面、景观和透视钢笔图转为可编辑的分层 DXF。适合从扫描图或参考图片重绘设计底图，也支持保留确认稿的灰度笔触。
---

# 图片转 CAD · Image to CAD

先明确交付意图，再选择转换命令。没有尺寸依据时使用未校准像素单位。

| 意图 | 输入与命令 | 验收重点 |
| --- | --- | --- |
| Reconstruct 重构 | 建筑平面 `building`、建筑剖面 `section`、景观设计图 `landscape` | 开口、连接和空间关系保留。几何适度规整，构件与图层可编辑。 |
| Trace 描摹 | 钢笔画、插画、Logo 或需要保留原始视觉特征的线稿，用 `pen` | 建筑透视默认直接读原图并重绘可编辑线条。需要灰度笔触时选择 `--representation hatch`。 |

## 执行

1. **读原图并确定范围。** 已明确的范围直接沿用。只有影响交付的分歧才集中确认，并提供建议默认值。剖面先辨认墙、板、梁、柱、洞口、坡道与楼梯。保留必要基础轮廓，省略土方和材料填充、人物、洁具及无关装饰。辨别笔画线宽与真实构件双边界。参见[范围、提示词与验收清单](references/scope.md)。
2. **选输入路线。** 清晰图直接整理布局。透视钢笔图默认从原图整理路径，无需先生成简化图。确有简化需求时可生成简化稿或交接提示词。Reconstruct 简化允许拉直、统一接近的厚度和适度移动端点。逐区对照源图核查开口、坡道方向、墙板柱连接与构件数量。生成稿经用户确认同一版本后才传 `--approved`，可用 `--approved-sha256` 固定版本。已有干净线稿可以先用 `section --input-route linework` 提取普通线条，再按原图判断语义。程序提取的线条先留在未分类层。
3. **表达可编辑构件与线条。** 把建筑透视图当作同一视角的着色视图来读，在二维补做类似 Rhino Make2D 的可见线稿。按[透视线稿规范](references/pen-lines.md)从图中推断主要轮廓、构件边和遮挡，再用 `pen --source … --layout …` 导出。用阴影和材质辅助识别形体，默认省略这些显示效果以及与建筑底图无关的对象。只放大影响构件连接、开口或遮挡的局部。重构路线应保护真实开口和楼梯踏步。对不明类型保留可见边界和疑问，避免补画没有图像依据的墙、柱或楼层。剖面用构件 ID、宿主和坡道端点关系写布局，规则见[剖面规范](references/section.md)。其他命令见[运行说明](references/runtime.md)或 [English runtime guide](references/runtime.en.md)。
4. **回读和交付。** 查看原图与实际 DXF 对照，核查关系、几何、可编辑性和图面整洁。按用户指定的格式交付。需要截图时用实际 DXF 的回读预览，并列出影响使用的待确认问题。说明布局是助手读图、人工准备、模型辅助还是程序提取。主要关系够用且底图便于继续设计即可交付。

For editable architectural plans, sections and landscapes, use Reconstruct and preserve topology while regularizing geometry. For architectural pen perspectives, default to native editable strokes from the source. Select layered HATCH when tonal ink is requested. See the [English runtime guide](references/runtime.en.md) for commands.
