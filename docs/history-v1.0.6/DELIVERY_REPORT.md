# 交付报告 · Effie Entry Expert v1.0.6

> 本文件由 `_upgrade/gen_delivery_report.py` 从实际文件与 JSON **自动生成**，
> 所有数字均为实测值。v1.0.0 曾因手写统计导致多处失真（ZIP 哈希、体积、
> 条目数、规则数、工作流数、测试数），改为自动生成为根治措施。

**生成日期**：2026-11-24
**发布状态**：**BETA**（证据等级 E2；宿主 E3 / 模型对照 / 真实案例未执行）
**包名**：`dist/Effie-Entry-Expert-v1.0.6.zip`
**内容指纹（除本报告外全部包内文件）**：`eb23c95d7f0a961c4dd8184753c194ce339fdd157572d911620fb795e4167eac`
**ZIP 自身 SHA-256**：见包外 `SHA256SUMS.txt`（报告在包内，记录包哈希会造成自指矛盾，
故改由包外文件记录；`shasum -a 256 dist/Effie-Entry-Expert-v1.0.6.zip` 可复算）

---

## 一、包内容实测

| 项 | 实测值 |
|---|---|
| 包内文件数 | 73 |
| ZIP 条目 | 82（文件 73 + 目录 9） |
| 规则条目 | 487（13 个奖项） |
| 参赛类别 | 134（主奖项，含官方定义全文） |
| 参赛表字段 | 89 |
| 校验脚本 | 13 个 |
| 工作流 | 12 个 |
| 专业方法论 | 8 篇 |
| JSON Schema | 8 个 |
| 交付模板 | 8 个 |
| 官方文件登记 | 81 份（771 页 PDF / 579,201 汉字 / 27 份 OCR） |

## 二、引用真实性（本版重点修复）

| 引用类型 | 条数 | 含义 | 能否加引号 |
|---|---|---|---|
| `verbatim` | 444 | 原文整条在来源文档逐字命中 | ✅ 可，须附页码 |
| `paraphrase` | 4 | 跨奖项统一措辞的转述，来源无此原句 | ❌ 只能转述 |
| `referential` | 39 | 形如「见…条款」的指代 | ❌ 须改写 |

| 校验状态 | 条数 |
|---|---|
| `VERIFIED` | 483 |
| `UNVERIFIED`（转述，不得用于正式判定） | 4 |

**引文体量（如实披露）**：`source_quote` 合计 16,476 字，
其中逐字原文 15,263 字；类别定义 23,133 字。
约占官方 2026 资料 10%，属实质性引用，详见 `LICENSE` 与 `THIRD_PARTY_NOTICES.md`。

**页码覆盖**：475 条有页码；12 条无页码，
其中转述类 4 条已标 `UNVERIFIED` 并写明原因，
其余指代性引用已加 `page_note` 说明「不得编造页码」。

**引用守卫的验证边界**：
- 构建期已用完整语料做过逐字核验，结果即上表；
- 包内 `verify_quotes.py` 默认只做**内置自检**（计数、状态一致性、页码说明），
  **不做逐字比对**——官方语料不随包分发（版权）。
- 用户若需逐字核验，用 `--corpus` 指向自备语料；`references/corpus-index.json`
  可用于核对你手中的官方文件是否与构建时一致。

## 三、测试实测

| 套件 | 结果 |
|---|---|
| `tests/run_tests.py` | 单元 + 集成 + 对抗 |
| `tests/run_scenarios.py` | 12 类业务场景 |
| **合计** | **通过 76 / 76** |

场景测试实际调用的校验器：`eligibility` / `metrics` / `attribution` /
`evidence` / `submission`（v1.0.0 只调用前两个，却称「端到端」，已修正）。

**变异测试（证明测试非恒真）**：5 个变异体全部被捕获——
撤回 G05 复核、撤回 G10 复核、引用守卫短路、paraphrase 偷改 verbatim、
证据哈希校验短路。

## 四、门禁实测

| 反例 | 结果 |
|---|---|
| 证据全部自标 `VERIFIED` + 清空 `open_p0/p1_issues` + 文件不存在 | G05、G10 均 FAIL，状态 DRAFT |
| 同上但提供 `--base-dir` 且哈希匹配 | G05、G10 通过 |
| 提供 `--base-dir` 但文件被篡改 | G05 FAIL（E02 哈希不一致） |

## 五、为什么仍是 BETA

| # | 门槛 | 状态 |
|---|---|---|
| 1 | 真实宿主触发测试（E3） | ❌ 未执行 |
| 2 | 模型 A/B/C 对照实验 | ❌ 未执行（`MODEL_EVALUATION_NOT_EXECUTED`） |
| 3 | 真实客户案例验证 | ❌ 未执行（12 场景全为 SYNTHETIC） |

**证据等级：E2。** 不得声称「已验证可用」「比裸模型好 X%」「生产就绪」。

## 六、已知限制

1. 仅覆盖 **2026** 竞赛年度。
2. 7 个奖项无类别定义文件；5 个奖项类目册 PARTIAL。
3. 汽车奖官方仅 8 条取消资格（非九条）。
4. 12 个场景全为合成夹具，证明逻辑自洽，不证明对真实案例判断准确。
5. 主观判断（洞察是否独到）不可脚本验证。
6. `confounders_addressed` 等字段靠用户如实填写。
7. 知识库可被用户篡改；建议用 `references/corpus-index.json` 的指纹自校验。

## 七、安装与使用

```bash
# 解压到技能目录
unzip dist/Effie-Entry-Expert-v1.0.6.zip -d ~/.workbuddy/skills/
cd ~/.workbuddy/skills/effie-entry-expert

python3 scripts/rule_query.py --award EFFIE_GC_MAIN --type scoring_weights
python3 scripts/validate_eligibility.py --case my.json --award EFFIE_GC_MAIN
python3 scripts/validate_submission.py --case my.json --award EFFIE_GC_MAIN --base-dir ./materials
python3 scripts/verify_quotes.py        # 引用守卫内置自检
python3 tests/run_all.py                # 全部测试
```

无第三方依赖，Python ≥3.9。

## 八、声明

- 本 Skill 为**独立营销案例评估与报奖辅助工具，不代表艾菲奖组委会**，
  与其无隶属、授权、认证、合作或背书关系
- 不承诺获奖，不提供获奖概率
- 不代为提交参赛作品、不代为支付费用
- 官方规则可能变更，正式提交前请核对 https://www.effie-greaterchina.cn/
- 最终提交决定与合规责任由用户承担

---

*本报告由脚本生成于 2026-11-25 09:36:40*
