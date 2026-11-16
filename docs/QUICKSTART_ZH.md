# 中文快速上手｜UE5 Asset Validator

## 1. 先备份你的原项目

你目前可正常运行的原版文件位于 `F:\PythonProjects\AssetValidator\`。**不要直接覆盖原目录。**

将本仓库解压到单独目录，例如：

`F:\PythonProjects\UE5-Asset-Validator\`

确认 `ue_mesh_info.py` 与 `validation_rules.json` 在同一文件夹。

## 2. 检查 JSON 规则

打开 `validation_rules.json`，可看到默认规则及分类覆盖规则。当前默认 `max_triangles = 200` 是为了演示检查流程，不是游戏生产环境统一面数标准。

分类按资产路径中的目录名匹配：`/Architecture/`、`/Props/`、`/Foliage/`，不区分大小写。没有匹配到分类就使用 `Default`。

## 3. 在 UE5.7 中运行

1. 启动你的 UE5.7 项目。
2. 确认启用 **Python Editor Script Plugin**。
3. 打开 **Output Log**，将左下角命令输入模式设为 **Cmd**。
4. 输入（请替换为你实际解压后的路径）：

   ```text
   py "F:/PythonProjects/UE5-Asset-Validator/ue_mesh_info.py"
   ```

5. 查看 PASS、WARNING、Warning Reasons 和最后的 Summary。

**不要在 VS Code 的普通 Python 终端运行这个脚本。** 那里通常没有 `unreal` 模块。

## 4. 查看 CSV

运行结束后打开：

`F:\PythonProjects\UE5-Asset-Validator\reports\UE5_MeshReport.csv`

新增文件夹 `reports` 由脚本自动创建。报告包含状态、资产路径、分类、三角面预算及具体警告原因。

## 5. 发布 GitHub 之前

- 打开 README 检查英文说明是否准确。
- 确认 `screenshots/` 截图没有第三方受限内容和个人隐私信息。
- 用真实 UE5.7 项目再次执行整理后的脚本，并检查 CSV（当前整理版已经通过模拟环境测试，但尚未进行现场 UE5.7 回归测试）。
- 决定是否添加 LICENSE（若希望他人自由使用或修改代码）。
- GitHub 上可以在仓库 **Add file → Upload files** 上传文件，但后续建议逐步学习 Git 提交记录。
