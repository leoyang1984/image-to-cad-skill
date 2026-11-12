# 图片转 CAD Skill · Image-to-CAD Skill

将建筑平面、剖面和景观图重构为可继续编辑、改造和设计的 CAD 底图。**Reconstruct** 优先保护构件、开口和空间关系，允许根据原图做合理的几何规整。**Trace** 用于钢笔画、插画和 Logo 等外观敏感的线稿，保留轮廓、笔触和视觉层次。

Reconstruct architectural plans, sections and landscapes into editable CAD drawings.
Trace approved artwork to preserve contours, line weight and tonal detail.

[Skill 说明](skills/image-to-cad/SKILL.md) · [中文运行说明](skills/image-to-cad/references/runtime.md) ·
[English runtime guide](skills/image-to-cad/references/runtime.en.md) ·
[第三方许可](THIRD-PARTY-NOTICES.md)

| 路线 / Route | 输入 / Input | 主要输出 / Main outputs |
| --- | --- | --- |
| 建筑平面<br>Architectural plan | 原图与墙体、开口布局 JSON<br>Source image and a full-image layout JSON | 分层 DXF、门窗图块、单画布叠合页<br>Layered DXF, door and window blocks, review page |
| 建筑剖面<br>Architectural section | 原图与构件、宿主开口和连接 JSON<br>Source image and semantic layout | 原生线段与多段线、构件图层、关系检查<br>Native editable geometry and relationship report |
| 景观平面<br>Landscape plan | 原图与分层路径 JSON<br>Source image and layered paths in JSON | 分层 DXF、样条与多段线、叠合页<br>Layered DXF with splines and polylines, review page |
| 透视钢笔稿<br>Perspective pen drawing | 原图与路径布局，或已确认的白底稿<br>Source and path layout, or an approved white-background drawing | 分层可编辑线条或四档 HATCH，附 SVG 与 PNG<br>Layered editable strokes or four-tone HATCH, with SVG and PNG |

## 示例 / Examples

仓库自带两套可以直接改用的布局：[examples/apartment.json](examples/apartment.json)（8 段墙、14 处开口，
含车库门与待确认开口）和 [examples/garden.json](examples/garden.json)（7 个景观图层、曲线与多段线）。
`examples/smoke.py` 是最小合成夹具，它验证原有建筑、景观和钢笔画路线。[剖面回归](examples/section_smoke.py)验证无填充、多层和带通行构件的剖面，以及普通线稿提取。

仓库**不附带任何真实项目图纸**。要在自己的图纸上使用，把图放到本地目录，再按
[运行说明](skills/image-to-cad/references/runtime.md)整理布局。`examples/demo.py` 用上面的合成布局
生成三张输出图放在 `docs/cases/`，只作为回归产物，不在本页展示。

Two layouts ship with the repository and are meant to be copied:
[examples/apartment.json](examples/apartment.json) (eight walls, fourteen openings, including a garage
door and an unresolved opening) and [examples/garden.json](examples/garden.json) (seven landscape
layers, curves, and polylines). `examples/smoke.py` is the minimal synthetic fixture that CI runs on
every push. [Section regressions](examples/section_smoke.py) also cover openings, stair treads, ramp connections and unclassified linework.

The repository ships **no real project drawing**. To work on your own plan, keep the image in your
own directory and prepare the layout as described in the
[runtime guide](skills/image-to-cad/references/runtime.en.md). `examples/demo.py` renders the
synthetic layouts into `docs/cases/` as regression output only; the images are not shown here.

## 安装 / Installation

使用 Python 3.11，在仓库根目录安装依赖并运行回归。最后一条命令重新生成 `docs/cases/` 里的合成回归图。

Run these from the repository root with Python 3.11. The last command regenerates the synthetic images in `docs/cases/`.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r skills/image-to-cad/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python examples/smoke.py
.venv/bin/python examples/section_smoke.py
.venv/bin/python examples/pen_lines_smoke.py
.venv/bin/python examples/demo.py
```

Windows 使用 `.venv\Scripts\python.exe`。依赖版本固定，`pip check` 应无冲突。

## 加载 Skill / Load the skill

将整个 `skills/image-to-cad/` 文件夹交给能读取文件并运行 Python 的 Agent，它自带转换脚本和依赖清单。
Codex 用户可以从仓库根目录创建项目级链接后调用 `$image-to-cad`；也可以直接让 Agent 阅读
[SKILL.md](skills/image-to-cad/SKILL.md)。

Give the `skills/image-to-cad/` folder to an agent that can read files and run Python; it is
self-contained. For Codex, create the project-level link and invoke `$image-to-cad`. You can
also point an agent directly to [SKILL.md](skills/image-to-cad/SKILL.md).

```bash
mkdir -p .agents/skills
ln -s ../../skills/image-to-cad .agents/skills/image-to-cad
```

## 剖面重构 / Reconstruct a section

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py section \
  --intent reconstruct --source reference.png --layout section.json --output section-v1

.venv/bin/python skills/image-to-cad/scripts/convert.py section \
  --source clean-lines.png --input-route linework --output lines-v1
```

清晰的原图可直接整理布局。填充密集的图纸可先做简化稿，逐区核查开口、墙板柱连接和坡道方向，经用户确认后使用 `--simplified approved.png --approved`。已有干净线稿可提取普通矢量路径，再判断建筑语义。简化提示词与无生图工具时的交接方式见[工作流](skills/image-to-cad/references/scope.md)。剖面构件、规整容差和报告格式见[剖面规范](skills/image-to-cad/references/section.md)。

## 输出与质量 / Deliverables

导出 `redrawn.dxf`、`cad-preview.png`、`layout.json`、`report.json` 和可切换底图及图层的 `review.html`。使用确认稿时另存 `cleaned.png`，报告保存确认稿哈希。建筑与景观继续支持原有布局和命令。透视钢笔画默认从原图整理路径并生成原生可编辑线条。需要保留灰度笔触时可选分层 HATCH。两种都输出 `cad-vector.svg`。可编辑线条的命令与路径格式见[透视线稿规范](skills/image-to-cad/references/pen-lines.md)。

剖面报告分别检查已声明的关系、几何规整、可编辑性和图面整洁。判断构件类别、遮挡和整体空间连通性需要查看原图。程序自动提取的线条放入未分类层。所有坐标使用未校准像素单位。

Each route exports editable DXF, a readback preview, a JSON layout and report, and an offline review page. Section reports check declared relationships, geometry, editability and cleanliness. Automatic extraction from clean raster linework leaves paths unclassified. Trace defaults to native editable strokes for architectural perspectives and supports tonal HATCH on request. Existing plan layouts remain supported.

## 许可证 / License

代码以 [MIT](LICENSE) 发布。运行时依赖的许可，以及 PyMuPDF 的 AGPL-3.0 / 商业双授权说明，见
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。仓库内的示例图由脚本生成，不含第三方图纸。

The code is released under the [MIT license](LICENSE). Dependency licenses and the
AGPL-3.0 / commercial dual license of PyMuPDF are listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Example images are generated by scripts and
contain no third-party drawings.

## 已验证环境 / Tested environment

macOS arm64 与 Python 3.11；GitHub Actions 每次推送都运行原有导出与剖面回归。
Tested on macOS arm64 with Python 3.11. GitHub Actions runs both exporter and section regressions on every push.
