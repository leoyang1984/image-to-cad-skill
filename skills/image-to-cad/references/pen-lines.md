# 透视钢笔画转可编辑线条

先从整图判断建筑轮廓、主要构件和前后遮挡，再直接整理路径。用连续路径表达可见边界，线在遮挡处结束。较重的建筑轮廓可通过图层线宽表达。

## 把透视图当作着色视图来读

已有透视图时，可以理解成在同一视角补做一张 Make2D 式线稿。Rhino 的着色模式用颜色、材质和光照帮助看清形体。Make2D 按视角投影选中对象的几何，隐藏线可单独选择。本流程从图片推断可见边界，在原图视角重绘二维路径，线在遮挡处结束。[Rhino 着色模式](https://docs.mcneel.com/rhino/8/help/en-us/options/view_displaymodes_shaded.htm) · [Rhino Make2D](https://docs.mcneel.com/rhino/8/help/en-us/commands/make2d.htm)

遇到一条线，先判断它属于构件几何、显示效果，还是不在本次范围内的对象。例如地面砖缝可能只是贴图，也可能是单独建模的分缝。前者作为材质略过，后者在任务需要表达分缝时保留。地坪外缘、台阶前缘和高差转折则表达空间关系，通常保留。阴影可以帮助识别檐口或凹槽，画线时沿可辨认的构件边。

## 建筑线稿的取舍

- 优先保留墙、柱、屋檐、门窗洞口和主要分格，以及入口、平台、台阶和坡道的边缘。重复构件只画足以交代形状和位置的分格。
- 默认略过铺装网格、植物、人物、投影边界、材质纹理和灰面填充。一个区域可以只保留构造边界，例如花池画池壁和压顶，台阶保留踏步前缘，内部纹理留白。
- 主体关系能判断时就开始重绘。仅为确认洞口、连接和遮挡而查看必要局部。线稿主要关系清楚、能继续编辑后即可交付。

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py pen \
  --source perspective.jpg --layout strokes.json --output pen-lines-v1
```

提供路径布局时默认导出线条，可加 `--representation lines` 显式指定。用户提供的透视图可直接使用。若使用生成式简化图，获得该版本的确认后添加 `--simplified approved.png --approved`，可用 `--approved-sha256` 固定版本。两图同时提供时以原图坐标写布局，并在对照页核查位置。如果仅提供确认稿，布局按该稿坐标写。需要灰度笔触时可显式使用 `--representation hatch`。原来的 `pen --simplified approved.png --approved` 继续生成四档 HATCH。

## 路径布局

`frame` 是归一化参考图的 `[0, 0, width, height]`。坐标使用像素中心，x 向右，y 向下，导出时转为 CAD 的 y 向上。可选 `focus` 只设定预览与初始视图。程序编译助手或设计师整理的二维路径，尺寸未校准。

```json
{
  "schema_version": 1,
  "frame": [0, 0, 200, 140],
  "interpretation": "human",
  "paths": [
    {"id": "eave", "layer": "P-OUTLINE", "d": "M 20 50 C 65 10 125 15 180 52"},
    {"id": "panel", "layer": "P-PANEL", "d": "M 62 60 L 87 58 L 84 75 L 58 76 Z"}
  ]
}
```

每条路径有唯一 `id`、图层和绝对坐标命令，命令及数值以空格分隔。用 `M x y` 起笔，接 `L x y` 或三次贝塞尔 `C x1 y1 x2 y2 x y`，最后可用 `Z` 闭合。一条直线写成 LINE，折线写成 LWPOLYLINE，含曲线的路径写成 SPLINE。可用 `omitted` 和 `unresolved_questions` 记录取舍和不确定之处。

| 图层 | 内容 |
| --- | --- |
| `P-OUTLINE` | 建筑主轮廓 |
| `P-FRAME` | 主要结构线 |
| `P-DETAIL` | 分格与细部 |
| `P-PANEL` | 翘板与开口边缘 |
| `P-ENTRANCE` | 入口与场地构件 |
| `P-CONTEXT` | 环境轮廓 |

用实际 DXF 回读检查主要轮廓、开口和遮挡。纯线稿只包含 LINE、LWPOLYLINE 和 SPLINE，且 HATCH 数为零。按用户指定的格式交付，只要 DXF 时直接交付该文件。需要截图时使用实际 DXF 的回读 PNG。

For pen perspectives, supply a path layout in reference-image coordinates to export editable strokes by default. The existing HATCH command preserves the tonal appearance of approved ink.
