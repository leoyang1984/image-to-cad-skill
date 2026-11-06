# 运行方式与布局格式

## 安装与检查

将 `skills/image-to-cad/` 整个目录交给 Agent。转换脚本和运行依赖清单都在其中。以下命令以本仓库根目录为起点。

在目标机器上准备 Python 3.11。从 CAD 项目根目录执行以下命令。已有兼容的虚拟环境时，可以使用它的 Python。

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r skills/image-to-cad/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python skills/image-to-cad/scripts/convert.py --help
```

已验证环境为 macOS arm64 和 Python 3.11。Windows 上虚拟环境的解释器路径为 `.venv\Scripts\python.exe`，依赖和转换的实际运行仍需在目标环境验证。入口帮助应列出 `prepare`、`building`、`landscape`、`pen`。

直接依赖是 NumPy、OpenCV Headless、Shapely、ezdxf、Pillow、pypdfium2 和 PyMuPDF。按 [requirements.txt](../requirements.txt) 安装固定版本，pip 会一并解析传递依赖。透视 PNG 回读渲染使用 PyMuPDF，其发行包注明 AGPL 3.0 或 Artifex 商业许可。

若目标机器离线，在能联网且与目标机使用相同操作系统、架构和 Python 版本的机器上先下载 wheels，再把 `wheelhouse/` 带到目标机器。

```bash
# 联网机器
.venv/bin/python -m pip download --only-binary=:all: -r skills/image-to-cad/requirements.txt -d wheelhouse
# 目标机器
.venv/bin/python -m pip install --no-index --find-links=wheelhouse -r skills/image-to-cad/requirements.txt
```

## 让 Agent 加载 Skill

Codex 用户可以从 CAD 项目根目录创建项目级链接，然后在该目录的对话中调用 `$image-to-cad`。已有同名入口时，先检查其指向。首次加载没显示时，重启 Codex。 [OpenAI 官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

```bash
mkdir -p .agents/skills
ln -s ../../skills/image-to-cad .agents/skills/image-to-cad
```

如果 Agent 通过对话读取工作区文件，直接指向 `skills/image-to-cad/SKILL.md`，并从项目根目录执行本文命令。生成式简化需要 Agent 环境提供 ImageGen，安装 Python 依赖即可运行 DXF 编译、导出和回读。没有图像生成工具时，建筑和景观可从原图整理布局，透视可使用用户已确认的钢笔稿。

## 准备原图

坐标取原图或选定 PDF 页归一化后的像素中心，x 向右、y 向下。需要明确 PDF 页码、DPI 或 EXIF 朝向时，先导出基准 PNG，并对着该图写布局。输出目录按任务版本命名。

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py prepare drawing.pdf --page 1 --dpi 200 --output reference.png
```

## 建筑平面

全图使用 `crop_xyxy: [0, 0, width, height]`。墙体条目含 `id`、两个端点 `axis: [[x1, y1], [x2, y2]]` 和像素宽度 `width`。开口条目含 `id`、宿主墙 ID `wall`、沿轴起点量起的 `offset`、`length`、`kind` 和 `certainty`。开口类型为 `door`、`window`、`garage`、`passage` 或 `unresolved`。明确的平开门还需 `hinge: start|end` 和 `side: -1|1`。开向难辨时用 `unresolved`，并把 `certainty` 设为 `needs_confirmation`。顶层提供 `regularization` 和 `omitted` 数组记录规整与省略。

仓库内的 [合成样例](../../../examples/smoke.py) 演示了最小布局。核查原图中的开口和通行关系，保持未识别对象的可编辑边界。

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py building --source reference.png --layout layout.json --output building-v1
```

## 景观平面

先给出一套默认保留范围，指出辨认困难的对象和可达到的表达程度。用户可以增加指定构件或局部，再按原图整理路径。保留场地、步道两侧、入口缺口及主体内部主导形态。用途不明的色块按可见边界记录。裁切处保持断开，铺装、散点和纹理按确认范围取舍。

布局含 `frame: [0, 0, width, height]` 和 `paths` 数组。路径含唯一 `id`、`layer`、`d`。路径命令以空格分隔，支持绝对坐标 `M x y`、`L x y`、`C x1 y1 x2 y2 x y` 和末尾的 `Z`。可用图层为 `L-SITE-EDGE`、`L-WALK`、`L-ZONE`、`L-PAVILION`、`L-FORM`、`L-AUX`、`L-STAIR`。最小路径示例见 [合成样例](../../../examples/smoke.py)。

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py landscape --source reference.png --layout layout.json --output landscape-v1
```

建筑和景观采用经确认的简化稿时，在对应命令加 `--simplified approved.png --approved`。叠合页把简化稿放入原图画幅用于视觉核对，重绘产生的位置漂移以原图为准。

## 透视钢笔画

提示词按对象分别约束。已有透视线稿保留建筑分格、主体轮廓和关键开口，压低材质与背景纹理。效果图保留取景、透视关系、门洞进深和远处有实体体量的构筑物，再处理倒影、材质、人物和植物的取舍。用连续线和线重表达层次。确认稿优先使用白底不透明 PNG。

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py pen --simplified approved.png --approved --output pen-v1
```

DXF 使用四档灰度的 HATCH，适合保持钢笔画的外观。需要逐条编辑建筑构件时，应另按构件重绘。检查圆饰、窗格和其他内部留白，确认填充边界回读有效。网页需要放大对照时，用实际 DXF 派生的 SVG 路径显示 CAD。

## 输出

各路线输出 `redrawn.dxf`、`cad-preview.png` 和 `report.json`。平面另外输出结构化 `layout.json` 和单画布 HTML。透视另外输出 `cad-vector.svg`。有确认稿时报告记录其 SHA-256，便于核对使用的版本。
