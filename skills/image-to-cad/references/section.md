# 建筑剖面布局与导出

用 Reconstruct 把剖面表达为能继续设计的底图。助手或设计师从原图判断构件与空间关系，Python 按布局编译。原图用于判断保留哪些构件以及它们的连接、方向和遮挡。位置和边界可以在有证据时整理。

## 运行

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py section \
  --intent reconstruct --source reference.png --layout section.json --output section-v1
```

附带经确认的简化稿时加 `--simplified approved.png --approved`。可用 `--approved-sha256 <SHA-256>` 固定同一版本。已有干净线稿可跳过布局参数，执行 `--input-route linework`。它在 `S-LINEWORK` 输出未分类线条，生成可继续编辑的布局 JSON。补充语义之后可用 `--layout` 重新编译。

## 数据格式

`frame` 为 `[0, 0, width, height]`，与归一化后的源图一致。点用像素中心坐标，x 向右，y 向下。DXF 使用 `height - 1 - y`，单位未校准。编译结果写入 `source_image`，含源文件名、SHA-256 和坐标系。再次编译该布局时用同一份源图。可选 `focus: [x1, y1, x2, y2]` 用于预览和 DXF 初始视图，保留全图坐标。

下面的最小例子对应 600 × 400 像素图。墙和楼板相接。墙上的洞口有可见范围，窗型待确认。

```json
{
  "schema_version": 1,
  "frame": [0, 0, 600, 400],
  "interpretation": "human",
  "components": [
    {"id": "w1", "kind": "wall", "axis": [[80, 60], [80, 340]], "thickness": 14},
    {"id": "s1", "kind": "slab", "outline": [[87, 320], [480, 320], [480, 340], [87, 340]]},
    {"id": "o1", "kind": "unresolved", "host": "w1", "outline": [[71, 125], [89, 125], [89, 190], [71, 190]]}
  ],
  "relationships": [{"from": "w1", "to": "s1", "type": "connects"}],
  "omitted": ["材料填充", "人物"],
  "regularization": ["规整近似水平的楼板"],
  "unresolved_questions": ["o1 的窗型待确认"]
}
```

- `id` 全图唯一。 `kind` 可取 `wall`、`slab`、`beam`、`column`、`door`、`window`、`stair`、`ramp`、`foundation`、`unresolved`、`linework`。分别对应 `S-WALL`、`S-SLAB`、`S-BEAM`、`S-COLUMN`、`S-DOOR`、`S-WINDOW`、`S-STAIR`、`S-RAMP`、`S-FOUNDATION`、`S-REVIEW` 和 `S-LINEWORK`。
- 结构实体用闭合 `outline`（可省末尾的起点），或 `axis` 加像素 `thickness`。两者都有时以轮廓画实体。可用 `paths` 记录多条可编辑折线，例如踏步或玻璃分格。给构件加 `certainty: "needs_confirmation"` 和 `notes` 可保留辨认限制，`unresolved` 自动标待确认。
- `door`、`window` 需提供 `host`（墙 ID）及切口 `outline`。可判断洞口但类型不明时用带宿主的 `unresolved`。只看见投影线、宿主未知时用无宿主 `unresolved` 和可见几何。洞口不碰宿主、多个切口重叠或切掉整墙会报错。明确类型的洞口可用 `paths` 指定符号，省略时绘制简化门或玻璃线。
- `relationships` 中 `connects` 检查两构件是否相接。坡道的 `axis` 从实际起点写到终点。用 `ramp_start` 与 `ramp_end` 从坡道分别指向相邻的楼板 ID。遮挡使关系不明时设 `certainty: "needs_confirmation"`，保留推断边界。报告记录各端距离与高差，供人工核查。未声明的关系不会被推断。
- `interpretation` 可用 `human`、`agent`、`model_assisted` 或 `unspecified`。程序线条提取自动写 `automatic_linework`。用 `omitted`、`regularization`、`unresolved_questions` 记录取舍、人工规整和待查问题。

## 规整与开口保护

容差按图像较短边换算为像素，范围为 0–0.02。局部线段长度与构件厚度会进一步限制移动量。

| `tolerances` 字段 | 默认值 | 作用 |
| --- | --- | --- |
| `tolerance_ratio` | 0.001 | 轻微斜轴与近似平行边界规整的最大位移依据，也用来标记短线。 |
| `relationship_ratio` | 0.002 | 检查已声明构件关系的距离阈值。 |
| `gap_ratio` | 0 | 只对同一未分类构件内、相向且只有唯一候选的短断线做吸附。确认是画线断口后再开启。 |

普通线条会清理重复和共线部分。规则保留已声明连接、靠得很近的构件、宿主墙、坡道方向和踏步。对某一实体设 `"rectify": false` 可保留近斜或近矩形轮廓。重要留白可在顶层 `protected_openings` 用多边形数组标出，阻止附近的端点吸附与共线合并。宿主洞口和待确认开口的轮廓也会加入保护区。报告保存各项程序规整的修改前后坐标。

线稿路线用 Otsu 二值化、细化笔画、提取连通路径及闭合轮廓、折线简化和重复清理。粗笔画只提取一条中心路径。保留曲线外观、灰度或纹理时使用 Trace。已有线稿的轮廓可能代表构件双边界，也可能只是画法，分类和洞口确认仍需要看原图。

## 回读与报告

| 指标 | 检查 |
| --- | --- |
| Relationship | 已声明连接、宿主洞口切割、坡道端点与走向、未知构件和未声明的坡道端点。连通性需要结合原图人工判断。 |
| Geometry | 闭合轮廓合法性、重合边、同类实体重叠、短线与规整记录。短踏步可能是合法几何。 |
| Editability | DXF 回读、图层、构件 ID（XDATA）、原生 LINE/LWPOLYLINE、可编辑图元比例。 |
| Cleanliness | 结构层有无填充或文字，是否仍有未分类线条。杂纹或有意保留的投影线由视觉验收判断。 |

输出 `redrawn.dxf`、`cad-preview.png`、`layout.json`、`report.json` 和 `review.html`。使用确认稿时还生成 `cleaned.png`。对照页可切换原图、确认稿、DXF 和各构件层。相同布局、源图和设置生成相同图元，DXF 保存元数据可能含时间。设计修改优先从布局或 DXF 构件着手。

合成回归可用 `python examples/section_smoke.py` 运行，覆盖无填充剖面、多层剖面、门窗与通行构件、保护区、简化稿版本和普通线稿提取。
