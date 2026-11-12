# 范围、简化稿与验收 / Scope and simplification

## 先确定意图和范围

Reconstruct 用于建筑平面、建筑剖面与景观设计底图。优先保留主要构件、关键开口及空间连接。允许拉直抖动、统一接近的墙板厚度、适度移动端点和简化复杂材料或门窗线。依据原图核对开口、支承和通行关系，避开没有图面依据的设计补全。Trace 用于 Logo、插画和钢笔画。优先保留轮廓、曲线、线重、留白与笔触。

| 输入 | 建议默认保留 | 按任务省略 |
| --- | --- | --- |
| 建筑平面 | 墙、门窗与通行开口，必要楼梯 | 家具、设备、文字与材质线 |
| 建筑剖面 | 墙、板、梁、柱、门窗洞口、楼梯、坡道及相邻平台，可辨认的基础 | 地下土方和材料填充、人物、洁具、装饰、无关标注 |
| 景观平面 | 场地外缘、主步道两侧、分区、构筑物轮廓、必要台阶 | 铺装纹理、杂散标识 |
| 透视线稿 | 轮廓、关键开口、分格、线重、留白 | 随任务选择背景、车辆、倒影 |

沿用用户已经确认的范围。必要时集中询问对交付有实质影响的取舍。剖面里有的密线是踏步、玻璃分格或基础边缘，应按对象意义判断。记录 `omitted`、`regularization` 和待确认问题。保留看不清的必要开口或构件线，用待确认状态表达。

## 三条输入路线

| 路线 | 何时使用 | 做法 |
| --- | --- | --- |
| A 原图 | 构件与连接清楚 | 原图 → 助手布局 JSON → 编译 → 回读与对照。 |
| B 简化图 | 填充、纹理或构造细部遮住主体 | 原图 → 整理保留范围 → 生成或交接简化稿 → 查关键关系 → 用户确认同一版本 → 布局和导出。 |
| C 现成线稿 | 画面已干净且需要普通可编辑路径 | `section --input-route linework` 自动提取到 `S-LINEWORK`，检查留白、线宽和轮廓。需要建筑语义时补写布局再编译。保留画面笔触时走已确认输入的 `pen`。 |

能实际调用生图工具时可以生成 B 稿。没有工具时，交接原图和提示词给愿意操作的用户，或对建筑和景观回到 A。透视描摹可以直接使用用户已确认的白底钢笔稿。将 PDF 先按页和 DPI 导出基准图。发 B 稿前逐区校核并单独展示该稿。收到明确确认后用 `--approved` 导出，带 `--approved-sha256` 可以校验精确文件。报告记录确认稿哈希。如果尺寸不同，叠合页面按画框缩放，只作视觉比较。

## 简化图提示词

```text
Redraw this architectural section as a clean line drawing for an editable CAD
working base. Keep the crop, orientation and overall proportions. Keep the main
walls, slabs, beams, columns, openings, stairs, ramp, adjoining landings and
readable foundation outlines, as specified for this drawing.

Straighten slight wobble, unify similar thicknesses and simplify incidental
details where the source supports it. Preserve component counts, key openings,
wall/slab/column connections, and the stair and ramp direction and landing
relationships. Do not invent components, dimensions or uncertain connections.
A thick stroke may be one boundary rather than two separate components.

Use clear black lines on a white background. Omit earth and material hatching,
people, fixtures, decorative details and unrelated text. Preserve dense lines
when they express a needed feature such as treads or glazing divisions.
```

建筑平面与景观按范围替换构件列表。Trace 改用外观优先的提示，要求保留原有轮廓、自由曲线、笔触和视觉层次。对明确不需要的背景纹理另列省略项。

## 视觉验收

- 先检查构件数量和空间关系。逐区核对墙板柱、宿主洞口、楼梯与坡道起终点。遮挡端点进入待确认清单。
- 比较规整前后。轻微位置调整可以接受，重要开口消失、通路改变或凭空出现结构需要重做。
- 检查实际落盘 DXF 的图层、可选图元、闭合、重复和碎线。图面整洁与开口通行优先于像素重合率。
- 标明助手解读、人工准备、模型辅助与程序线条提取的边界。输出未校准像素单位，未知尺寸由使用者另行校准。
