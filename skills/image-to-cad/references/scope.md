# 范围确认与简化图交接 / Scope agreement and simplification handoff

本文件补齐一个前提：**不是每个 Agent 环境都有生图能力**。建筑与景观平面可以直接从原图整理，
透视路线在拿不到确认稿时不能导出。先问清范围，再按当前环境的能力选执行方式。

Not every agent environment can generate images. Plans can be interpreted directly from the
source; the perspective route cannot export without an approved drawing. Agree on scope first,
then pick the execution mode that the current environment actually supports.

## 1. 先问一次范围 / Agree on scope once

读图后集中问一次，每题都给出建议默认值，用户回一句「按默认」即可继续。不要逐条追问。
Ask once, with a recommended default for every item, so the user can answer "use the defaults".
Do not drip the questions out one at a time.

**建筑平面 / Architectural plan**

| 问题 | 选项（默认在前） |
| --- | --- |
| 主要表达什么 | 墙体、门窗与主要开口 / 再加楼梯与固定设备 / 再加家具 |
| 文字与尺寸 | 全部省略 / 保留房间名 / 保留全部标注 |
| 线宽 | 统一线宽 / 保留原图线宽差异 |

**景观平面 / Landscape plan**

| 问题 | 选项（默认在前） |
| --- | --- |
| 保留对象 | 场地外缘、主步道两侧、主体构筑物轮廓 / 加分区边界 / 加台阶与平台 / 加铺装纹理 |
| 用途不明的灰面、色块 | 只画可见边界 / 整块省略 |
| 图签、文字、散点 | 省略 / 保留 |

**透视钢笔稿 / Perspective pen drawing**

| 问题 | 选项（默认在前） |
| --- | --- |
| 保留内容 | 主体轮廓、关键开口、分格 / 保留材质线 / 保留背景山线与植物 |
| 省略内容 | 人物、车辆、倒影 / 保留一人作尺度 |
| 线条 | 统一细钢笔线 / 保留粗细层次 |

景观的问法可以直接照这个结构：

> 建议保留三个圆的外轮廓和入口、主步道两侧边线、主要场地分区；圆内主造型可以独立成层，
> 附属构筑物只留外轮廓；右侧灰区可以画边界，具体用途看不清。建议省去碎石、铺装纹理和地面标识。
> 可以按这套做，也可以指定要增减的对象或区域。你想保留哪些？

## 2. 把范围写进布局 / Record the scope in the layout

- `omitted`：用户确认省略的对象。必填，程序会把它写进报告的 `out_of_scope`。
- `regularization`：统一线宽、规整抖动、门窗符号约定。必填。
- `certainty: needs_confirmation`：仍不确定的开口，交付时单列。

范围是一种约定，不是识别结果。用户后来改主意时，改布局数组并重新生成，不要悄悄扩大范围。

## 3. 按能力选执行方式 / Pick the mode you can actually run

| 情况 | 做法 |
| --- | --- |
| 能直接生成或编辑图片 | 生成简化稿 → 与原图逐区对照 → 单独发给用户确认 → 确认后加 `--approved` 导出 |
| 不能生图，用户愿意跑一次外部工具 | 交出提示词与源图 → 用户用任意图像生成/编辑工具生成 → 存回 `simplified.png` → 助手逐区验收 → 用户确认后加 `--approved` |
| 不能生图，用户不想折腾 | 直接从原图整理布局，不用简化稿。建筑与景观都适用 |
| 透视路线且没有可用的确认稿 | 只能走前两种；没有确认稿就不导出 DXF |

**不要假装能力。** 判断依据是当前环境能否真的调用图像生成或编辑工具，不是猜测、也不是问用户
「你有没有生图工具」。拿不到工具就走交接，不要用文字描述冒充生成结果。

Never claim a capability you cannot invoke. Decide from the tools actually available in the
current environment, not from guesswork and not by asking the user whether they have an image
model. If no tool is available, hand off; never describe an image you did not produce.

## 4. 交接协议 / Handoff protocol

1. **导出基准图。** PDF 先定页与 DPI，建筑与景观的布局坐标必须对着这张图写。

   ```bash
   .venv/bin/python skills/image-to-cad/scripts/convert.py prepare drawing.pdf --page 1 --dpi 200 --output reference.png
   ```

2. **写提示词文件。** 与源图放在同一目录，命名为 `simplify-prompt.md`，包含下方模板与本轮的范围要求。
3. **用户生成。** 把源图和提示词一起交给任意图像生成/编辑工具，结果存成 `simplified.png`。
4. **验收。** 逐区对照原图，列出遗漏、新增、灰底、水印。
5. **确认后导出。** 用户明确认可同一版本后，才执行带 `--approved` 的命令。
6. **留痕。** 报告记录简化稿的 SHA-256；尺寸与源图不一致时同时记录 `simplified_frame_match: false`。

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py building \
  --source reference.png --layout layout.json \
  --simplified simplified.png --approved --output building-v1
```

### 提示词模板 / Prompt template

```text
Edit the attached drawing into a clean line version. Keep the canvas, framing,
orientation and proportions unchanged: do not crop, rotate or rescale.
Output pure black lines on a pure white background, with no grey fills, no
shading, no textures, no text, no dimensions and no watermark.
Keep <范围: 墙体、门窗与主要开口 / 场地外缘、主步道两侧、主体构筑物轮廓 ...>.
Remove <范围: 家具、文字、铺装纹理、碎石、地面标识 ...>.
Do not add, delete or move any element. Where the drawing is unreadable, leave
the area empty rather than inventing geometry.
```

### 验收清单 / Acceptance checklist

- **尺寸与比例**：与源图一致最稳妥。不一致时叠合页会把简化稿拉伸到源图框，只能当视觉参考，
  不能用来判断位置；报告里的 `simplified_frame_match` 会是 `false`。
- **构件数量**：门窗、开口逐区核对。生成稿最常见的错误是漏门、多画门弧、把设备边界画成隔墙。
- **背景**：纯白。灰底或阴影会污染钢笔路线的四档阈值。
- **水印与文字**：出现即重做，不要试图在后续步骤里修补。

## 5. 什么时候不用简化图 / When to skip it

- 图面本身清晰、线条不多：直接读原图更快，也不会引入生成误差。
- 用户只要求局部或单一构件。
- 用户不接受把图纸交给第三方服务：这既是保密决定，也是授权决定，必须问过再操作。

简化稿只用于帮助读图。几何一律回原图核对，简化稿里的位置漂移、增删都不作为依据。
A simplification is a reading aid. Check geometry against the source; never inherit its drift,
additions or omissions into the drawing.
