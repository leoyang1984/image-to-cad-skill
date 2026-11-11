---
name: image-to-cad
description: 将建筑平面、景观平面或建筑透视线稿转成分层 DXF。 Convert architectural plans, landscape plans, and approved perspective pen drawings into layered DXF.
---

# 图片转 CAD · Image to CAD

[中文](#中文) · [English](#english)

## 中文

以视觉相似、图面清晰和方便复用为目标。先读原图，识别主要对象、连接和遮挡，按用途选择路线。无尺寸依据时使用未校准像素单位。只有影响复用的疑问才集中向用户确认。

| 输入 | 处理方式 |
| --- | --- |
| 建筑平面 | 读原图，记录墙轴、墙厚、所属墙及开口位置。用程序合并墙体、切开洞口、绘制标准门窗图块。 |
| 景观平面 | 先建议保留范围和可辨认程度。按确认范围记录主体轮廓、通行边线、场地分区和主要造型，再分层重绘。 |
| 透视线稿或效果图 | 整理成清晰、略带手绘感的钢笔稿。将确认后的笔画转成带孔洞的分层实心 HATCH，保留粗细与深浅。 |

建筑和景观平面可以直接读原图。纹理密集时，可用内置 ImageGen 辅助简化。透视输入已有用户明确认可的干净钢笔稿时，直接用该稿。

脚本只做确定性绘制：读图、判断构件和整理布局由助手完成。不提供自动识别，不做文字与尺寸，平面路线不输出填充。

**生成式简化稿的确认关口。** 先与原图逐区对照，检查关键构筑物、开口、遮挡和轮廓。单独发简化稿给用户确认，本轮停在预览。用户要求修改时，发新稿再确认。得到对该版本的明确确认后，才执行带 `--approved` 的 DXF 命令。用户明确确认了同一版本时可继续执行。平面重绘仍以原图为依据。

执行前读 [运行方式和布局格式](references/runtime.md)。命令入口为 [scripts/convert.py](scripts/convert.py)。读图、范围选择、布局整理和用户确认由助手在对话中完成，编译脚本从结构化布局或已确认的钢笔稿开始。

回读实际落盘的 DXF，检查主要几何、开口或留白，交付 DXF 和导出 PNG。平面同时交付可切换底图和构件层的单画布页面。透视交付从 DXF 回读得到的 SVG，放大时查看矢量几何。用户在对话中给修改意见。

## English

Aim for a visually similar, clean drawing that is easy to reuse. Read the source image first to identify the main objects, connections, and occlusions. Choose the route that matches the intended use. Use uncalibrated pixel units when there is no reliable scale. Ask about ambiguities that affect reuse.

| Input | Workflow |
| --- | --- |
| Architectural plan | Interpret the source and record wall axes, wall thicknesses, and openings with their host walls. Compile the walls, cut the openings, and draw standard door and window blocks. |
| Landscape plan | Recommend what to retain and explain what can be identified reliably. After the user agrees on scope, record the main outlines, path edges, site zones, and defining forms. Redraw them by layer. |
| Perspective line art or rendering | Prepare a clean pen drawing with a lightly hand-drawn character. Convert the approved strokes to layered solid DXF HATCH entities with cutouts to preserve their weight and tone. |

Architectural and landscape plans can be interpreted directly from the source. Use the built-in ImageGen tool when dense textures obscure the layout. If the user has already explicitly approved a clean perspective pen drawing, use that drawing.

The scripts only draw deterministically: the agent reads the image and prepares the layout. There is no automatic recognition, no text or dimension extraction, and plan routes emit no fills.

**Approval before DXF export.** Compare a generated simplification against the original, checking the main structures, openings, occlusions, and outlines. Deliver the simplification on its own and stop for approval. If the user requests changes, show the revised version and ask again. Run the DXF command with `--approved` only after the user explicitly approves that exact version. Use the original image as the reference for plan geometry.

Read the [runtime guide and layout schemas](references/runtime.en.md) before running [scripts/convert.py](scripts/convert.py). The agent interprets images, agrees on scope, prepares layouts, and obtains approval in conversation. The scripts take a structured layout or an approved pen drawing as input.

Read back the saved DXF and check the main geometry, openings, or cutouts. Deliver the DXF and its PNG export. For plans, also deliver a single-canvas review page with source and layer toggles. For perspectives, deliver the SVG generated from the saved DXF so users can zoom into the vectors. Collect revision requests in conversation.
