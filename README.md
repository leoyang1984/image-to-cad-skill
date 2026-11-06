# 图片转 CAD Skill · Image-to-CAD Skill

把建筑平面、景观平面和透视线稿转成分层 DXF。平面路线从助手整理的布局绘制可编辑图形，透视路线保留用户确认的钢笔稿笔触。

Convert architectural plans, landscape plans, and perspective line art into layered DXF. The plan workflows draw editable geometry from layouts interpreted by the agent. The perspective workflow preserves the strokes in a user-approved pen drawing.

[Skill 说明 / Skill instructions](skills/image-to-cad/SKILL.md) · [中文运行说明](skills/image-to-cad/references/runtime.md) · [English runtime guide](skills/image-to-cad/references/runtime.en.md)

| 路线 / Workflow | 输入 / Input | 主要输出 / Main outputs |
| --- | --- | --- |
| 建筑平面<br>Architectural plan | 原图和墙体、开口布局 JSON<br>Source image and JSON layout of walls and openings | 分层 DXF、门窗图块、叠合页<br>Layered DXF, door and window blocks, overlay page |
| 景观平面<br>Landscape plan | 原图和分层路径 JSON<br>Source image and layered paths in JSON | 分层 DXF、样条和多段线、叠合页<br>Layered DXF with splines and polylines, overlay page |
| 透视钢笔稿<br>Perspective pen drawing | 已确认的白底钢笔线稿<br>Approved pen drawing on a white background | 矢量填充 DXF、SVG、PNG<br>DXF with vector fills, SVG, PNG |

## 安装 / Installation

使用 Python 3.11，在仓库根目录执行以下命令。最后一条命令用合成图验证三条导出路线。

Run the following commands from the repository root with Python 3.11. The last command checks all three exporters using synthetic drawings.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r skills/image-to-cad/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python examples/smoke.py
```

## 加载 Skill / Load the skill

将整个 Skill 文件夹交给能读取文件并运行 Python 的 Agent。Codex 用户可从仓库根目录创建项目级链接，再用 `$image-to-cad` 调用。也可以直接让 Agent 阅读上面链接的 `SKILL.md)。

Give the entire skill folder to an agent that can read files and run Python. For Codex, create the project-level link from the repository root and invoke `$image-to-cad`. You can also point an agent directly to the linked `SKILL.md`.

```bash
mkdir -p .agents/skills
ln -s ../../skills/image-to-cad .agents/skills/image-to-cad
```

## 使用约定 / Workflow notes

助手负责读图、确定保留范围和整理平面布局。采用生成式简化稿时，先让用户确认具体版本，再导出 DXF。生成简化稿需要 Agent 环境提供图像生成工具。Python 依赖负责编译和回读。

The agent interprets the source, agrees on what to retain, and prepares the plan layout. If a generated simplification is used, the user approves that exact version before DXF export. Generating a simplification requires an image-generation tool in the agent environment. The Python dependencies handle compilation and readback.

已验证环境为 macOS arm64 和 Python 3.11。没有尺度依据时，DXF 使用未校准像素单位。

Tested on macOS arm64 with Python 3.11. DXF coordinates use uncalibrated pixel units when a reliable scale is unavailable.
