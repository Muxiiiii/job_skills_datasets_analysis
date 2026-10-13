# 数据质量口径（全量分析对外说明）

来源：`cleaned/final_eval_v8.md`（fresh 50 个从未见过的岗位，2026-10-13）。

## 可用字段

| 字段 | fresh50 指标 | 用法 |
|---|---|---|
| 学历要求 `edu_required` | 准确率 **0.86** | 可用 |
| 经验年限 `yoe_min_overall` | 准确率 **0.84** | 可用；空值偏多，有值时多数正确 |
| 技能 | precision **0.66**，recall **0.58** | **适合频次排名与跨组比较**；不适合当作单岗完整技能清单 |
| 技能（两源一致子集） | precision **0.93** | 高置信口径（`high_confidence=true`） |
| 证书 | 整组一致 0.56（不可用） | **只看单个证书出现率**（RN、BLS、CDL、Driver's License 等） |
| `job_family_pred` | 0.62 | **不可用 / 实验性**；主分组请用 `search_position` → `position_group` |

## 分析默认设置

- 去重：每个 `dup_group_id` 只计 `is_dup_primary` 一次；另存「含重复」对照表。
- 技能默认视图：排除 `is_generic` 与名称含 `(unspecified)` 的标签。
- 主分组维度：`position_group`（由 LinkedIn `search_position` 映射）、`search_country`、`job_level`、`job_type`。

## 不要对外宣称的数字

- tune 集上的 job_family 0.90（训练集记忆，无效）。
- 证书「整组完全一致」准确率。
- 把技能列表当作每个 JD 的金标准清单。
