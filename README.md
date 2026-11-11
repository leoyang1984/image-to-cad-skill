# 图片转 CAD Skill · Image-to-CAD Skill

把建筑平面、景观平面和透视钢笔画转换成分层 DXF。平面路线由助手读图整理布局，程序据此绘制可编辑图形；透视路线保留已确认钢笔稿的笔触与层次。

Convert architectural plans, landscape plans, and approved perspective pen drawings into
layered DXF. Plan routes draw editable geometry from a layout interpreted by the agent.
The perspective route preserves the strokes and tones of a pen drawing the user approved.

[Skill 说明](skills/image-to-cad/SKILL.md) · [中文运行说明](skills/image-to-cad/references/runtime.md) ·
[English runtime guide](skills/image-to-cad/references/runtime.en.md) ·
[第三方许可](THIRD-PARTY-NOTICES.md)

| 路线 / Route | 输入 / Input | 主要输出 / Main outputs |
| --- | --- | --- |
| 建筑平面<br>Architectural plan | 原图与墙体、开口布局 JSON<br>Source image and a full-image layout JSON | 分层 DXF、门窗图块、单画布叠合页<br>Layered DXF, door and window blocks, review page |
| 景观平面<br>Landscape plan | 原图与分层路径 JSON<br>Source image and layered paths in JSON | 分层 DXF、样条与多段线、叠合页<br>Layered DXF with splines and polylines, review page |
| 透视钢笔稿<br>Perspective pen drawing | 已确认的白底扫描稿或渲染稿<br>Approved pen drawing on a white background | 四档灰度实心 HATCH 的 DXF、SVG、PNG<br>DXF with four-tone solid HATCH, SVG, PNG |

## 示例 / Examples

仓库自带两套可以直接改用的布局：[examples/apartment.json](examples/apartment.json)（8 段墙、14 处开口，
含车库门与待确认开口）和 [examples/garden.json](examples/garden.json)（7 个景观图层、曲线与多段线）。
`examples/smoke.py` 是最小合成夹具，CI 每次推送都用它验证三条导出路线。

仓库**不附带任何真实项目图纸**。要在自己的图纸上使用，把图放到本地目录，再按
[运行说明](skills/image-to-cad/references/runtime.md)整理布局。`examples/demo.py` 用上面的合成布局
生成三张输出图放在 `docs/cases/`，只作为回归产物，不在本页展示。

Two layouts ship with the repository and are meant to be copied:
[examples/apartment.json](examples/apartment.json) (eight walls, fourteen openings, including a garage
door and an unresolved opening) and [examples/garden.json](examples/garden.json) (seven landscape
layers, curves, and polylines). `examples/smoke.py` is the minimal synthetic fixture that CI runs on
every push.

The repository ships **no real project drawing**. To work on your own plan, keep the image in your
own directory and prepare the layout as described in the
[runtime guide](skills/image-to-cad/references/runtime.en.md). `examples/demo.py` renders the
synthetic layouts into `docs/cases/` as regression output only; the images are not shown here.

## 安装 / Installation

使用 Python 3.11，在仓库根目录执行。倒数第二条命令用合成图验证三条导出路线，最后一条命令重新生成 `docs/cases/` 里的回归图。

Run these from the repository root with Python 3.11. The second-to-last command checks all
three exporters; the last one regenerates the regression images in `docs/cases/`.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r skills/image-to-cad/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python examples/smoke.py
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

## 使用约定 / Workflow notes

助手先与用户确认这次要表达的范围（墙体与门窗、场地外缘与步道、保留哪些构件），再按当前环境
的能力选做法：能生图就直接生成简化稿并请用户确认；不能生图就把提示词和源图交给用户，用任意
图像工具生成后拿回来验收；两者都不适用就直接从原图整理布局。只有带 `--approved` 的命令才接受
简化稿。三条路线的做法与提示词模板见
[范围确认与简化图交接](skills/image-to-cad/references/scope.md)。

The agent agrees on scope first (walls and openings, site outline and walks, which elements to
retain), then uses whatever the environment supports: generate the simplification and ask for
approval, hand the prompt and source to the user and verify what comes back, or build the layout
from the source without a simplification. Only a command with `--approved` accepts one. See
[scope and handoff](skills/image-to-cad/references/scope.md) for the question sets and the prompt
template.

## 能力边界 / What it is not

- **不是自动识别。** 脚本不读图；布局 JSON 由助手读图后整理，程序只做确定性重绘。没有模型、
  没有 OCR，也不会上传图纸。
- **不做文字、尺寸与标注。** 不推断真实比例；没有校准时一律使用未校准像素单位。
- **平面路线不输出填充。** 只有墙体边界、门窗图块与图层；HATCH 只属于透铁路线。
- **曲线是近似。** 景观样条与多段线由控制点生成，不还原原图打印线宽或抖动。
- **只画整幅。** `crop_xyxy` 与 `frame` 必须等于源图尺寸；要画局部，先用 `prepare` 或外部工具裁图。
- **不猜设计。** 布局里没有的墙不会被补齐，缺口不会被连上，斜墙不会被强行拉正。

- **Not an automatic recognizer.** The scripts never read the image; the agent prepares the
  layout and the scripts redraw it deterministically. No model, no OCR, no uploads.
- **No text, dimensions, or annotations.** Scale is never inferred; uncalibrated pixel units
  are used unless you supply a real measurement.
- **Plan routes emit no fills.** Only wall boundaries, door and window blocks, and layers.
  HATCH belongs to the perspective route.
- **Curves are approximations.** Landscape splines and polylines follow control points rather
  than reproducing printed line weight.
- **Whole frames only.** `crop_xyxy` and `frame` must equal the source size; crop first with
  `prepare` or another tool to work on a region.
- **No invented design.** Missing walls are not filled in, gaps are not bridged, and skewed
  walls are not forced orthogonal.

## 许可证 / License

代码以 [MIT](LICENSE) 发布。运行时依赖的许可，以及 PyMuPDF 的 AGPL-3.0 / 商业双授权说明，见
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。仓库内的示例图由脚本生成，不含第三方图纸。

The code is released under the [MIT license](LICENSE). Dependency licenses and the
AGPL-3.0 / commercial dual license of PyMuPDF are listed in
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Example images are generated by scripts and
contain no third-party drawings.

## 已验证环境 / Tested environment

macOS arm64 与 Python 3.11；`examples/smoke.py` 在每次推送时由 GitHub Actions 重跑。
Tested on macOS arm64 with Python 3.11. `examples/smoke.py` runs on every push in GitHub Actions.
