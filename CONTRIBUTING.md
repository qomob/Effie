# 贡献指南

感谢你愿意改进 Effie Entry Expert。本项目是一个本地运行的营销案例评估与报奖辅助 AI Skill，对准确性和边界声明的要求高于功能数量。

## 先读这些

- [README.md](README.md)：产品定位、能力状态与已知限制
- [SKILL.md](SKILL.md)：铁律、意图路由与输出规范
- [PRIVACY.md](PRIVACY.md) 与 [SECURITY.md](SECURITY.md)：数据处理与安全边界
- [CHANGELOG.md](CHANGELOG.md)：版本变化

## 开发环境

要求 Python 3.10+；视频相关检查需要 `ffprobe`，部分测试需要 `ffmpeg`。

```bash
git clone https://github.com/qomob/Effie.git
cd Effie
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 测试规范

提交前必须运行统一测试入口：

```bash
python3 tests/run_all.py --json
```

- 退出码必须为 0，且 `passed == total`。
- 不允许删除测试、跳过用例或降低断言标准来制造通过结果。
- 新增检查逻辑时，请补充对应的通过用例与失败用例。
- 涉及解析器（pypdf、python-docx、openpyxl、python-pptx）的改动，请说明缺失依赖时的降级行为。

## 代码要求

- 以 Python 标准库为主；新增第三方依赖必须有明确用途，并同步更新 `requirements.txt`。
- 保持脚本可离线运行，不引入联网调用、遥测或自动上传。
- 不把用户文件内容写入日志。
- 退出码语义保持一致：`0` 通过、`1` 有问题、`2` 用法错误。
- 不得让任何代码路径输出“已授权提交”或等价状态。

## 数据与隐私

- 禁止提交真实客户资料、未脱敏业务数据、密钥、Token 或个人信息。
- 需要演示时使用 `examples/` 下的合成数据，或自行脱敏并说明。
- 涉及规则库的修改，请在 PR 中说明来源文件、页码与核验范围；无法核验的内容必须标注为未核验。

## 提交 Pull Request

1. 从 `main` 创建分支，保持改动聚焦。
2. 提交信息建议使用 `feat:`、`fix:`、`docs:`、`test:`、`chore:` 前缀。
3. PR 描述中说明：
   - 改了什么、为什么改
   - 对现有能力边界的影响
   - 已执行的测试命令与结果
   - 是否涉及隐私、安全或规则库
4. 确认 CI 通过后再请求评审。
5. 若 `main` 受分支保护，请通过 PR 合并，不要绕过保护规则。

## 行为准则

参与本项目即表示同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
