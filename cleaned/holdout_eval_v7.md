# Holdout 最终验证 — 冻结 v7 管线（50 岗）

日期：2026-10-13。标注与判定：Claude（LLM），逐岗阅读 `summary_full`。规则、代码、现有产物均未改动；本次只新建了 3 个文件：

| 文件 | 内容 |
|---|---|
| `cleaned/holdout_gold_claude.csv` | 50 岗盲标 gold（family、全量技能、edu、yoe、certs、notes） |
| `cleaned/holdout_skill_judgments_claude.csv` | v7 对这 50 岗的 590 条预测技能逐条判定（correct 1/0 + error_type） |
| `cleaned/holdout_eval_v7.md` | 本报告 |

## 结论

**有过拟合，但集中在 job_family 一项；技能抽取基本可以泛化。**

- **job_family 严重过拟合**：tune 0.827 → holdout 0.540（差 0.287）。同一批 holdout 岗位上 v5 是 0.52、v7 是 0.54，也就是 v6/v7 的 family 规则改动在 tune 之外几乎没有收益。
- **yoe_overall（差 0.107）和 certs_required 含词典外（差 0.087）超出 0.05**，未达 0.80 目标。
- **技能 precision（差 0.044）、recall（差 0.031）、edu_required（差 0.047）在 0.05 以内**，但都在 tune 之下，且 edu 贴着阈值。
- v6→v7 的 recall 提升在 holdout 上是真实的（0.513 → 0.578），不是只对 tune 有效。

## 对比表

| 指标 | tune v7 | holdout v7 | 差距 (tune − holdout) | ≤0.05？ | 目标 | holdout 达标？ |
|---|---|---|---|---|---|---|
| 技能 precision | 0.768 (1001/1303) | **0.724** (427/590) | 0.044 | 是 | ≥0.82 | 否 |
| 技能 recall（词表内严格） | 0.609 (224/368) | **0.578** (337/583) | 0.031 | 是 | ≥0.60 | 否 |
| job_family（严格） | 0.827 (124/150) | **0.540** (27/50) | **0.287** | **否** | ≥0.75 | 否 |
| edu_required | 0.807 (121/150) | **0.760** (38/50) | 0.047 | 是（贴线） | ≥0.80 | 否 |
| yoe_overall | 0.807 (121/150) | **0.700** (35/50) | **0.107** | **否** | ≥0.80 | 否 |
| certs_required（含词典外） | 0.807 (121/150) | **0.720** (36/50) | **0.087** | **否** | ≥0.80 | 否 |
| certs_required（词典内） | 0.873 | 0.900 | −0.027 | 是 | — | — |
| edu_preferred | 0.940 | 0.940 | 0.000 | 是 | — | — |
| job_family（lenient，接受 alt） | 0.840 | 0.560 | 0.280 | 否 | — | — |

同一批 holdout 岗位上各版本的表现（用同一份 holdout gold 打分；precision 只判了 v7 的预测）：

| 版本 | 预测条数 | recall | job_family | edu_required | yoe_overall | certs（全部） | certs（词典内） |
|---|---|---|---|---|---|---|---|
| v5 | 522 | 0.509 | 0.52 | 0.50 | 0.54 | 0.66 | 0.84 |
| v6 | 473 | 0.513 | 0.54 | 0.76 | 0.70 | 0.72 | 0.90 |
| v7 | 590 | 0.578 | 0.54 | 0.76 | 0.70 | 0.72 | 0.90 |

edu、yoe、certs 相对 v5 的提升在 holdout 上大部分保留了下来，只是幅度比 tune 小；family 没有保留。

## 口径与可比性说明

- 计算直接调用 `scripts/eval_tune_v6.py` 的 `skill_recall`、`quals_accuracy`、`_norm_edu`、`_yoe_eq`、`_certs_*` 函数；precision 与 family 按该脚本同样的定义计算。预测取自现成的 `job_skill_refined_v7_sample5000.csv` 和 `job_features_v7_sample5000.csv`（已包含 holdout，无需重跑管线）。
- **tune precision 0.768 偏乐观的可能性**：它只在 v5 时判过的 1303 条上计算，v6/v7 新增的 401 条预测没有标签。holdout 的 0.724 覆盖全部 590 条。v5 当时全量判定的 tune precision 是 0.721，与 holdout 几乎一样。所以 0.044 的差距有一部分来自口径，而非过拟合。
- **recall 的岗位集不同**：tune 用 30 个 `full_recall` 岗（368 个词表内 gold）；holdout 没有 `full_recall` 标记，用全部 50 岗（583 个）。
- **评估脚本的一个小瑕疵**：`skill_recall` 把空的 `gold_skills_all` 读成字符串 `"nan"` 并计为 1 个未命中（无 JD 文本的 Assistant General Manager）。脚本原样输出是 337/584 = 0.577；上表用剔除后的 337/583 = 0.578。
- **样本量**：岗位级指标 n=50，单个指标的 95% 区间约 ±0.13，所以 0.05 的阈值对 edu/yoe/certs 而言在噪声范围内。family 的差距（0.287）远超噪声。
- 盲标顺序：先读 50 岗 JD 写完 gold（写完后记录了文件哈希），之后才读取预测。gold 未回改。唯一读了标题的岗位是无 JD 文本的那一个。

## 技能 precision 细分

| 切片 | holdout precision |
|---|---|
| sources = job_skills\|summary（两源一致） | 0.918 (134/146) |
| sources = job_skills（ner_only） | 0.735 (83/113) |
| sources = summary only | 0.634 (210/331) |
| 每岗均值 / 中位数 | 0.691 / 0.727（5 岗低于 0.5） |

敏感性：35 条判定带 borderline 备注（21 条判 1，14 条判 0）；全部翻向一侧时 precision 在 0.688 – 0.747 之间。

### 错误类型（163 条误报）

| 排名 | error_type | 条数 | 占比 | 典型例子 |
|---|---|---|---|---|
| 1 | wrong_sense | 48 | 29% | "driving the commercial success" → Driving；"eye-hand coordination" → Project Coordination；"electrical shock" → Electrical Systems；"organization"（指机构）→ Organization |
| 2 | not_requirement | 32 | 20% | EEO / Clery 安全报告 / 招聘联系方式；多个可选学位专业之一；"不承担管理职责" → People Management |
| 3 | ner_unsupported | 28 | 17% | job_skills 里有、JD 正文没有依据（Attention to Detail、Budgeting、Forecasting、Dental） |
| 4 | too_generic | 21 | 13% | Development / Management / Quality / Operations (unspecified) 作为其他短语的片段 |
| 5 | company_title | 18 | 11% | 公司简介、中介简介、仅出现在职位名里的词 |
| 6 | wrong_alias | 9 | 6% | installation → Repair；product knowledge → Merchandising；Rehabilitation → Physical Therapy |
| 7 | benefit | 7 | 4% | "flexible scheduling"、"professional development reimbursement" |

排序与 tune v7 基本一致（tune：wrong_sense 84、not_requirement 67、ner_unsupported 62、company_title 42、benefit 26、wrong_alias 12、too_generic 9）。差别是 too_generic 在 holdout 占比明显更高。

### 最差技能（≥5 条）

| 技能 | precision | 主要原因 |
|---|---|---|
| Development (unspecified) | 1/11 | "development of X" 片段、R&D、福利 |
| Human Resources | 1/7 | HR 部门 / 联系人 |
| Quality (unspecified) | 1/6 | "quality metrics / quality care" 片段 |
| Organization | 2/10 | 指"机构"而非组织能力 |
| Production | 1/5 | 公司业务、"production-ready" |
| Quality Assurance | 1/5 | ner_only 无正文依据 |
| Management (unspecified) | 4/19 | 指管理层；"X management" 片段 |
| Engineering | 2/7 | 学位专业片段、部门名 |
| Operations (unspecified) | 2/7 | 部门名、职位名 |
| Training (unspecified) | 5/10 | EEO 声明、候选人自己接受的培训 |
| Scheduling | 4/8 | "scheduling an interview"、排班灵活福利 |

Development / Management / Quality / Operations (unspecified) 四个标签合计 43 条、只对 8 条，贡献了 163 条误报中的 35 条。

## 技能 recall

- 词表内严格：0.578（337/583）。按我在 notes 里标出的近义名（Computer Literacy/Proficiency、Quality Assurance/Quality Control (Manufacturing)、Employee Training / L&D 与 Training (unspecified)、Writing/Written Communication 等）放宽后为 0.621（362/583）。
- 含词典外：gold 另有 185 个 OOV 技能，全部计入时 recall 为 0.439（337/768）。
- 漏得最多：Teamwork 8、Written Communication 7、People Management 7、Employee Training / L&D 7、Coaching 6、Documentation 6、Organization 6、Contract Administration 5、Interpersonal Skills 5、Compliance 5。多数仍是以职责句表达（"supervise staff"、"train, coach and develop employees"、"maintains accurate records"）。
- 3 岗几乎零输出：Registered Nurse（IntelyCare，gold 12 个词表内技能，命中 1）、Associate Veterinarian（命中 1）、Kitchen Supervisor（只有 ner_only 的 6 条）。

## job_family（27/50）

- 预测为 `Other` 的有 10 岗，全部错；预测为 `Management General` 的有 7 岗，只有 2 岗我也标为 Management General。这两类合计 15 个错误，占 23 个错误的 65%。
- 主要混淆（预测 → gold）：Other → Construction & Trades 3（Regional Technician、Quantity Surveyor、Reliability Technician）；Management General → Construction & Trades 2（Contracts Manager Ducting、Design Manager）；Management General → Finance & Accounting 2（Client Service Manager、Tax Manager）；Other → Behavioral Health 2（LMFT、Team Leader）；Other → Education 2（PT Faculty、Special Education Instructional Coach）。
- 明显的规则漏洞：`AWS Solution Architect` → Architecture & Design；`Senior Manager, Machine Learning Engineering` → Engineering (Non-software)；`Molecular Immunologist`、`LMFT`、`Land Surveyor` → Other。
- 我的 gold 中有 4–5 个可争议（Senior Operations Strategy Analyst、Senior Engineering Project Manager、Lead Cardiac Sonographer、Occupational Therapist 的归属；技术员归 Construction & Trades 是沿用 tune 的先例）。即使全部让给管线，也只有约 0.62–0.64，结论不变。

## 资格字段错误明细

**edu_required（12 错）**

- **6 个是虚假的 `master`**：匹配到 "MS Office / MS Word / MS Project"（当作 M.S. 学位）和普通词 "master"（"master contract agreement"、"Supply Chain master data"、"master sanitation schedule"、"Master Level Business Systems Analyst"）。涉及 Procurement Coordinator、Supply Chain PTM、Lead Security Engineer、Quality Supervisor、Reliability Technician、Territory Sales Manager。这与 v5 时 "as" → associate 是同一类问题，tune 上没有暴露。
- 漏掉 3 个：HNC（Contracts Manager）、"BSc in Quantity Surveying"、DVM。
- 3 个梯度/等级差异：Design Manager "HNC or Degree"（预测 bachelor，gold associate）；BI Developer 学位梯度（预测 associate，gold 取第一档 bachelor）；Customer Service Rep 的高中学历在 "Great if you have" 下，被判成 required。

**yoe_overall（15 错）**：13 个是漏抽，2 个取错值。

- 漏抽里有明显简单的句式：英文数字加括号 "Five (5) to ten (10) years"、"Three (3) – five (5) years"、"Minimum of three (3) or more years"；"Two years prior experience of…"、"Two years of supervisor experience"、"5+ years in relevant position"、"Minimum of one year of experience as a Cardiac Sonographer (Required)"。
- 取错值：Senior Engineering PM（预测 3，gold 7）、ML Engineering Sr Manager（预测 2，gold 8）——都取了列表里最小的子项年限而不是总体年限。
- 其中约 5 个 gold 可争议（"4 个月"记为 0.33、preferred 年限、Pattern I/II、学位梯度、注塑 2 年/制造 3 年）。

**certs_required（14 错，其中 9 个只因词典外证书）**

- 词典外：APICS BSCM、CIPD、Veterinary License、DCWF + IAM/IAT II、NIHSS、RDCS/RCS、LMFT、OT License、Illinois PEL、First Aid、PLS。
- 词典内的真错 5 个：Nursing Technician 多出 RN、LPN（"在 RN 或 LPN 监督下"）；PPG RN 多出 LPN（福利句）和 ACLS（preferred）；Lead Security Engineer 多出 PMP（学位的替代项）；Occupational Therapist 多出 Driver's License（"如岗位需要"）；Land Surveyor 的 PLS/PMP 二选一。

## 建议（规则已冻结，以下留待解冻后）

1. job_family 是唯一确定过拟合的模块，应在解冻后优先重做，并在一个新的未见样本上验证，而不是继续对 tune 调。目前全量分析里按 family 分组的任何结论都不可靠（holdout 上约一半岗位归错，`Other` 全错）。
2. edu 的 "MS / master" 误匹配、yoe 的 "Five (5) years" 句式、(unspecified) 四个标签，都是成片的、规则可修的错误。
3. 跑全量前，报告中应使用 holdout 数字（precision 0.72、recall 0.58、family 0.54、edu 0.76、yoe 0.70、certs 0.72）作为对外的质量口径，而不是 tune 数字。
4. 我的 gold 和判定是单人 LLM 标注，建议人工抽查 family 的 23 个分歧和 35 条 borderline 判定。
