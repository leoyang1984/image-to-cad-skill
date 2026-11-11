# 合成示例图 / Synthetic demo outputs

这三张图由 [examples/demo.py](../../examples/demo.py) 生成，输入是仓库内手写的合成布局
（[apartment.json](../../examples/apartment.json)、[garden.json](../../examples/garden.json)），
不含任何真实项目图纸。

它们只用于回归：CI 每次推送都会重跑 `examples/demo.py`，确认三条导出路线都能产出可预览的结果。
README 不展示这些图，因为它们只验证导出链路，不代表真实图纸的绘图质量。

These three images are produced by [examples/demo.py](../../examples/demo.py) from the synthetic
layouts authored in this repository. No real project drawing is involved. They exist as regression
output: CI reruns the script on every push to confirm that all three exporters produce a preview.
They are not shown in the README because they exercise the pipeline rather than demonstrate output
quality on real drawings.

```bash
.venv/bin/python examples/demo.py
```
