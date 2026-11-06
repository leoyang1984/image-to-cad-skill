# 图片转 CAD Skill

把建筑平面、景观平面和透视线稿转成分层 DXF。平面路线从助手整理的布局绘制可编辑图形，透视路线保留用户确认的钢笔稿笔触。

| 路线 | 输入 | 主要输出 |
| --- | --- | --- |
| 建筑平面 | 原图和墙、开口布局 JSON | 分层 DXF、门窗图块、叠合页 |
| 景观平面 | 原图和分层路径 JSON | 分层 DXF、样条与多段线、叠合页 |
| 透视钢笔稿 | 已确认的白底钢笔线稿 | 矢量填充 DXF、SVG、PNG |

## 安装

使用 Python 3.11。在本仓库根目录执行以下命令。

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r skills/image-to-cad/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python examples/smoke.py
```

将 [Skill 文件夹](skills/image-to-cad) 交给能读取文件并执行 Python 的 Agent。Codex 用户也可以把该文件夹链接到项目内的 Skill 搜索路径。

```bash
mkdir -p .agents/skills
ln -s ../../skills/image-to-cad .agents/skills/image-to-cad
```

在 Codex 中用 `$image-to-cad` 调用。若不使用自动加载，可直接请 Agent 读 [SKILL.md](skills/image-to-cad/SKILL.md)。布局字段、运行参数和离线安装见[运行说明](skills/image-to-cad/references/runtime.md)。

平面中的读图、取舍和布局由助手在对话中完成。采用生成式简化稿时，先让用户确认具体版本，再导出。生成图依赖 Agent 环境中的图像生成工具，Python 依赖用于编译和回读。

已验证环境为 macOS arm64 与 Python 3.11。没有尺度依据时，DXF 使用未校准像素单位。
