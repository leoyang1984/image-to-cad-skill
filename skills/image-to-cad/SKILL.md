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
| 建筑平面 | 读原图，记录墙轴、墙厚、所属墙及开口位置，需要时另记楼梯。用程序合并墙体、切开洞口、绘制标准门窗图块与踏步。 |
| 景观平面 | 先建议保留范围和可辨认程度。按确认范围记录主体轮廓、通行边线、场地分区和主要造型，再分层重绘。 |
| 透视线稿或效果图 | 整理成清晰、略带手绘感的钢笔稿。将确认后的笔画转成带孔洞的分层实心 HATCH，保留粗细与深浅。 |

建筑和景观平面可以直接读原图。线条密集或图面杂乱时，可借助简化图提高可读性。透视输入已有用户明确认可的干净钢笔稿时，直接用该稿。

脚本只做确定性绘制：读图、判断构件和整理布局由助手完成。不提供自动识别，不做文字与尺寸，平面路线不输出填充。

**先问范围，再选执行方式。** 读图后集中问一次这次要表达什么（建筑：墙体与门窗、是否含楼梯设备家具；景观：外缘、步道、分区、构筑物、台阶；透视：保留与省略的构件），每题给出默认值，用户可以只回「按默认」。确认结果写进布局的 `omitted` 与 `regularization`。问题清单、提示词模板与验收清单见 [范围确认与简化图交接](references/scope.md)。

| 当前环境 | 做法 |
| --- | --- |
| 能直接生成或编辑图片 | 生成简化稿 → 与原图逐区对照 → 单独发给用户确认 → 确认后加 `--approved` 导出 |
| 不能生图，用户愿意跑一次外部工具 | 交出提示词与源图 → 用户生成并存回 `simplified.png` → 助手逐区验收 → 用户确认后加 `--approved` |
| 不能生图，用户不想折腾 | 直接从原图整理布局，跳过简化稿；建筑与景观都适用 |
| 透视路线，且没有可用的确认稿 | 不能导出 DXF；先按第一或第二行拿到确认稿 |

**不要假装能力。** 判断依据是当前环境能否真的调用生图工具，不是猜测，也不要反过来问用户「你有没有生图工具」。简化稿只帮助读图，几何一律回原图核对；尺寸与源图不一致时叠合页会拉伸，报告记 `simplified_frame_match: false`，不能据此判断位置。

执行前读 [运行方式和布局格式](references/runtime.md)。命令入口为 [scripts/convert.py](scripts/convert.py)。读图、范围选择、布局整理和用户确认由助手在对话中完成，编译脚本从结构化布局或已确认的钢笔稿开始。

回读实际落盘的 DXF，检查主要几何、开口或留白，交付 DXF 和导出 PNG。平面同时交付可切换底图和构件层的单画布页面。透视交付从 DXF 回读得到的 SVG，放大时查看矢量几何。用户在对话中给修改意见。

## English

Aim for a visually similar, clean drawing that is easy to reuse. Read the source image first to identify the main objects, connections, and occlusions. Choose the route that matches the intended use. Use uncalibrated pixel units when there is no reliable scale. Ask about ambiguities that affect reuse.

| Input | Workflow |
| --- | --- |
| Architectural plan | Interpret the source and record wall axes, wall thicknesses, openings with their host walls, and any stairs. Compile the walls, cut the openings, and draw standard blocks and stair treads. |
| Landscape plan | Recommend what to retain and explain what can be identified reliably. After the user agrees on scope, record the main outlines, path edges, site zones, and defining forms. Redraw them by layer. |
| Perspective line art or rendering | Prepare a clean pen drawing with a lightly hand-drawn character. Convert the approved strokes to layered solid DXF HATCH entities with cutouts to preserve their weight and tone. |

Architectural and landscape plans can be interpreted directly from the source. Use a simplification when dense or messy line work obscures the layout. If the user has already approved a clean perspective pen drawing, use that drawing.

The scripts only draw deterministically: the agent reads the image and prepares the layout. There is no automatic recognition, no text or dimension extraction, and plan routes emit no fills.

**Agree on scope, then use the mode you can actually run.** Ask once what the drawing should emphasise (walls and openings, stairs, fixtures and furniture for plans; site outline, walks, zones, structures and stairs for landscapes; retained and omitted elements for perspectives), with a recommended default for every item, so "use the defaults" is a valid answer. Record the answer in `omitted` and `regularization`. Question sets, the prompt template and the acceptance checklist are in [scope and handoff](references/scope.md).

| Environment | What to do |
| --- | --- |
| Can generate or edit images | Generate the simplification → compare region by region → send it for approval on its own → export with `--approved` after approval |
| No image tool, user will run an external one | Hand over the prompt and the source → user generates and saves `simplified.png` → you verify it region by region → export with `--approved` after approval |
| No image tool, user does not want a round trip | Build the layout from the source and skip the simplification; valid for plans |
| Perspective route without an approved drawing | No DXF export; obtain one via row 1 or row 2 first |

**Never claim a capability you cannot invoke.** Decide from the tools actually available, not from
guesswork, and do not bounce the question back to the user. A simplification is a reading aid:
check geometry against the source. When its size differs, the review page stretches it and the
report records `simplified_frame_match: false`; do not judge positions from it.

Read the [runtime guide and layout schemas](references/runtime.en.md) before running [scripts/convert.py](scripts/convert.py). The agent interprets images, agrees on scope, prepares layouts, and obtains approval in conversation. The scripts take a structured layout or an approved pen drawing as input.

Read back the saved DXF and check the main geometry, openings, or cutouts. Deliver the DXF and its PNG export. For plans, also deliver a single-canvas review page with source and layer toggles. For perspectives, deliver the SVG generated from the saved DXF so users can zoom into the vectors. Collect revision requests in conversation.
