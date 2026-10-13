# v8 最终验证 — 冻结 v8 管线（fresh 50 + holdout 50）

日期：2026-10-13。标注与判定：Claude（LLM），逐岗阅读 JD 原文。规则、代码、模型、现有产物均未改动（冻结文件前后 SHA-256 一致）；本次只新建文件。

## 结论

| 模块 | fresh50（干净数字） | 是否可用于全量分析 |
|---|---|---|
| 技能抽取 | precision 0.658，recall 0.584 | **可用，但要带口径说明**。适合做技能频次排名和跨组比较；不适合当作单岗的准确技能清单。两源一致（job_skills + 正文）的子集 precision 0.93，可作高置信口径。 |
| job_family | **0.62**（95% 区间 0.48–0.74） | **不可用，未达 0.70**。holdout 上是 0.54，与 v7 完全相同。见下方“异常 1”：v8 的分类器实际上没有生效。 |
| edu_required | 0.86（0.74–0.93） | 可用。 |
| yoe_overall | 0.84（0.71–0.92） | 可用。主要问题是漏抽（空值偏多），抽到的数值大多正确。 |
| certs_required | 词典内 0.72，含词典外 0.56 | **按“整组完全一致”口径不可用**。只适合看单个大证书（RN、BLS、CDL、Driver's License）的出现率；不要用 `certifications_pipe` 当作“必需证书”清单，它混入了 preferred 证书。 |

技能、edu、yoe 在 fresh50 上与 holdout 相差都在区间之内，没有新的过拟合迹象。job_family 和 certs 是两个不能直接用的字段。

## 并排对比表

| 指标 | tune v8 (n=150) | holdout v7 | holdout v8 | **fresh50 v8** | fresh50 的 95% 区间 |
|---|---|---|---|---|---|
| 技能 precision | 0.768 (1001/1303)ᵃ | 0.724 (427/590) | 0.724 (427/590) | **0.658** (302/459) | 0.60–0.71ᵇ |
| 技能 recall（词表内严格） | 0.609 (224/368)ᶜ | 0.578 (337/583) | 0.578 (337/583) | **0.584** (230/394) | 0.52–0.64ᵇ |
| 技能 recall（含词典外） | — | 0.439 (337/768) | 0.439 | 0.429 (230/536) | — |
| job_family（严格） | 0.900 (135/150)ᵈ | 0.540 (27/50) | **0.540** (27/50) | **0.620** (31/50) | 0.48–0.74 |
| job_family（接受 alt） | 0.913 | 0.560 | 0.560 | 0.660 (33/50) | 0.52–0.78 |
| edu_required | 0.827 (124/150) | 0.760 (38/50) | 0.820 (41/50) | **0.860** (43/50) | 0.74–0.93 |
| yoe_overall | 0.853 (128/150) | 0.700 (35/50) | 0.880 (44/50) | **0.840** (42/50) | 0.71–0.92 |
| certs_required（含词典外） | 0.800 (120/150) | 0.720 (36/50) | 0.760 (38/50) | **0.560** (28/50) | 0.42–0.69 |
| certs_required（词典内） | 0.860 (129/150) | 0.840 (42/50)ᵉ | 0.840 (42/50) | **0.720** (36/50) | 0.58–0.83 |
| edu_preferred | 0.947 | 0.940 | 0.940 | 0.960 | — |

holdout v8 的 95% 区间（n=50，Wilson）：family 0.40–0.67，edu 0.69–0.90，yoe 0.76–0.94，certs 含词典外 0.63–0.86，词典内 0.71–0.92；precision 0.67–0.77，recall 0.52–0.63。

- ᵃ tune precision 只覆盖 v5 时判过的 1303 条，另有 401 条 v6 之后新增的预测没有标签，数字偏乐观。
- ᵇ precision / recall 的区间按岗位做 bootstrap（同一岗内的技能不独立）；其余为 Wilson 区间。
- ᶜ tune recall 只用 30 个 full_recall 岗。
- ᵈ 训练集内的数字，不能当作质量指标（见异常 1）。
- ᵉ `holdout_eval_v7.md` 里写的是 0.900。差别来自词典：v8 把 CIPD、LMFT、Veterinary License 等加进了 `CERT_DICT`，这些 gold 证书现在算“词典内”，v7 的预测漏了它们。按 v8 词典重算是 0.840。

**holdout 的 v7→v8 提升仅供参考**：edu（+0.06）、yoe（+0.18）、certs（+0.04）的补丁是看过 holdout 的错误之后设计的。fresh50 是这些补丁唯一没见过的样本，以它为准：edu 0.86、yoe 0.84 说明补丁是通用的；certs 没有跟着改善。

## 样本与流程

- **抽样**：`cleaned/jobs_combined.parquet`（与 v5 抽样同源，四个国家），只保留有 JD 文本的岗位（1,297,332 个），`numpy.default_rng(20261013)` 随机排列后按顺序取 50 个。排除范围取了更宽的口径：`sample_links_v5.csv` 的全部 5,000 岗（包含 tune 150 + holdout 50）以及与它们同 `dup_group_id` 的岗位，fresh 内部也不重复 dup 组。跳过了 2 个候选。国家分布：US 43、UK 4、CA 2、AU 1。
- **盲标**：先只读 50 个 JD 写完 gold，`cleaned/fresh50_gold_claude.csv` 的 SHA-256 记在 `cleaned/fresh50_gold_claude.sha256`（`58df6c90…94bd2`），之后才运行管线、读取预测。写完后未回改，结束时校验一致。脚本只用于展示文本、写文件、校验技能名是否在词表里、计数。
- **管线**：新写的脚本逐步调用 `run_pipeline_v8.py` 的同一组函数，加载已冻结的 `job_family_tfidf_lr_v8.joblib`，不重新训练。先在 holdout 50 上验证过：技能 590 条、family、edu、yoe、certs 与现有 `*_v8_sample5000` 产物逐条一致，再用于 fresh50。
- **打分**：直接调用 `scripts/eval_tune_v6.py` 的 `_norm_edu`、`_yoe_eq`、`_certs_*` 等函数，与 tune / holdout 同一定义。

新建文件：`fresh50_links_v8.csv`、`fresh50_gold_claude.csv`、`fresh50_gold_claude.sha256`、`job_skill_refined_v8_fresh50.csv`、`job_features_v8_fresh50.csv`、`fresh50_skill_judgments_claude.csv`、`final_eval_v8.md`（都在 `cleaned/`）。

## 异常

1. **v8 的 job_family 分类器基本没有生效。** `predict_job_family` 在最高概率低于 `min_proba=0.18` 时回退到旧的 regex 规则。模型有 31 个类、只用 150 条训练，最高概率的中位数只有 0.05：
   - 5,000 岗里 4,907 岗（98%）回退到规则，只有 93 岗用了分类器，其中 49 岗就是 tune 训练样本本身。
   - holdout 50 岗全部回退，预测与 v7 逐岗相同，所以 holdout family 仍是 0.54。fresh50 里只有 1 岗用了分类器。
   - tune 的 0.900 = 49 个被模型记住的训练岗（49/49）+ 101 个走规则的岗（86/101 = 0.85）。从 0.827 到 0.900 的提升完全来自训练集记忆。
   - 把阈值去掉、只用分类器（仅作诊断，不是冻结管线）：holdout 0.44（22/50），fresh50 0.50（25/50），比规则更差。所以调低阈值也不能解决问题，150 条标签对 31 个类不够。
2. **`run_pipeline_v8.py` 的 `main()` 每次运行都会调用 `train_and_save()`，重新训练并覆盖已冻结的 joblib。** 本次验证没有走这条路径。跑全量时如果直接用 `main()`，冻结的模型文件会被重写。
3. **`validation_sample_v8.csv` 的 tune/holdout 划分与 v5 不同**（划分按 job_family 分层，family 预测变了，划分就变了）。`validation_tune_links_v8.csv` / `validation_holdout_links_v8.csv` 不是真正的 tune / holdout，不要拿来用。真正的划分在 `validation_sample_v5.csv` 和 gold 文件里。
4. **泄漏检查通过**：分类器只读 `gold_annotation_template_v5_claude.csv` 中 `split == 'tune'` 的 150 行；该文件里 holdout 50 行的 `job_family_gold` 全部为空；tune 集合与 v5 划分一致；fresh50 与 5,000 岗样本无交集，与 gold 文件无交集。分类器训练没有用到 holdout 或 fresh 的标签。
5. fresh50 的技能 precision（0.658）比 holdout（0.724）低 0.066。两者区间重叠（0.60–0.71 对 0.67–0.77），而且 fresh 里公司简介类误报更多（见下）。全量上的 precision 更可能在 0.65–0.72 之间，而不是 tune 的 0.77。

## fresh50：job_family（31/50）

混淆最多的 5 对（预测 → gold）：

| 预测 | gold | 次数 | 岗位 |
|---|---|---|---|
| Other | Sales | 2 | Client Advisor（VinFast）、State Farm Agent Team Member |
| Other | Construction & Trades | 2 | Security Systems Installation Technician、Starlight Homes Internship |
| Management General | Finance & Accounting | 2 | Large Account Business Segment Manager（保险核保）、Senior Manager, Development Advisory（Baker Tilly） |
| Nursing & Clinical | Personal Care / Physician & PA | 各 1 | CNA 居家护理员、Surgical Oncology NP/PA |
| Allied Health / Behavioral Health | Imaging & Radiology / Allied Health | 各 1 | Radiology Technologist、Psychiatric Occupational Therapist |

只有前三对出现 2 次，其余 13 个错误各不相同。按预测类别看更清楚：

- 预测为 `Other` 的 9 岗全部错（holdout 上是 10 岗全错）。除上面 4 岗外还有 Team Leader - Children、Master Resilience Trainer、Space Management Specialist、Cleanroom Technician、法语的 Concepteur Surfacique。
- `Management General` 3 岗错 2 岗。
- 明显的规则错误：`Substitute Drivers`（校车司机）→ Project / Product Mgmt；`Temporary Park Planner` → Supply Chain & Ops；`Data Center Engineer` → Engineering (Non-software)。
- 我的 gold 里有 5 岗自己标了“不确定”（实习、保险核保经理、Resilience Trainer、BIM 工程师、咨询高级经理）。接受全部 alt 之后是 0.66，仍低于 0.70。

## fresh50：技能

**precision 0.658（302/459）**

| 切片 | precision |
|---|---|
| 两源一致（job_skills\|summary） | 0.926 (113/122) |
| 仅 job_skills（ner_only） | 0.607 (54/89) |
| 仅 summary | 0.544 (135/248) |
| 每岗均值 / 中位数 | 0.607 / 0.634（12 岗低于 0.5） |

敏感性：86 条带 borderline 备注（51 条判 1，35 条判 0），全部翻向一侧时 precision 在 0.547–0.734 之间。

误报类型（157 条）：

| error_type | 条数 | 占比 | 典型例子 |
|---|---|---|---|
| wrong_sense | 37 | 24% | "driving force" / "driving up memberships" → Driving；"teaching hospital" → Teaching；"creative arts programming" → Software Development；CSS（烈酒认证）→ CSS；organization 指公司 |
| company_title | 36 | 23% | 中介和公司简介、核心价值观列表、大学的学院列表（Engineering、Computer Science、Business Administration） |
| ner_unsupported | 32 | 20% | job_skills 里有、正文没有依据（Problem Solving、Decision Making、Dental、Budgeting） |
| not_requirement | 26 | 17% | EEO 条款、"No surgery or dentistry required"、可选学位专业、"We are interviewing candidates" → Recruitment |
| too_generic | 12 | 8% | Management (unspecified) 来自 "records management"、"wound management"、"learning management system" |
| benefit | 8 | 5% | mentorship、career development、flexibility |
| wrong_alias | 6 | 4% | installation → Repair（3 次）；product knowledge → Merchandising |

与 holdout 相比，company_title 的占比翻了一倍（11% → 23%），fresh 样本里中介岗和带长篇公司介绍的 JD 更多。`(unspecified)` 标签合计 44 条、对 15 条；其中 Management (unspecified) 2/17。

**recall 0.584（230/394）**。漏得最多：Communication 9、Documentation 8、Patient Care 6、Client Relationships 4、Medication Administration 4、Customer Service 4、Care Planning 4、Organization 4、Multitasking 4、Analysis (unspecified) 4、Driving 4、People Management 4。仍以职责句表达为主。几乎零召回的岗：Psychiatric Occupational Therapist（0/5）、Attending Physician（1/7）、State Farm Agent Team Member（2/11）、CNA（2/9）。法语 JD 的正文技能只靠 job_skills 字段命中。

## fresh50：资格字段

**edu_required（7 错）**

- 漏 5 个：`Four-year Bachelor's Degree in Electrical Engineering`、`H.S. Diploma or equivalent required`、`DVM/VMD degree`、`Medical doctor`、`Master's or Doctoral degree`（被标成 mentioned 而不是 required）。
- 虚假 master 1 个：`MS/PCU RN`（MS 指 Med-Surg）仍被判成 master。v8 的 MS 补丁没有覆盖这种写法，旅行护士岗里很常见。
- 取错档 1 个：正文是 `Master's degree`，公司介绍里的 "doctoral university" 被取成 phd。

**yoe_overall（8 错）**：6 个漏抽，2 个取错值。

- 漏抽：`1< year of relevant HR experience preferred`、`three to six months related experience`、`6 months current L&D experience required`、`2+ Years post Part 3 qualification`、`A minimum of five (5) plus years of progressive related consulting experience`、法语 `5 à 10 ans`。
- 取错：`8-10 years commercial lines experience` 取成了后面 preferred 子项的 5；`Required exp: 1/year` 取成了 preferred 的 2。
- 月份和法语不在规则范围内；`five (5) plus years` 属于 v8 应该覆盖的句式。

**certs_required（含词典外 22 错，其中词典内 14 错）**

- preferred 证书混进预测（4 岗）：SHRM/PHR、CCNA、CPA 都写明 preferred。`certifications_pipe` 不区分 required 和 preferred，而 gold 只记 required。
- 公司简介或否定句的误报（5 岗）：招聘网站简介 → PA；"CPA firm" → CPA；"board-certified doctors" → Board Certification；`Board Certification Required: No` → Board Certification；`BLS or as required per unit (ACLS, PALS…)` → ACLS、PALS。
- 漏抽词典内证书（4 岗）：`Active bar membership in California`（Bar Admission）、`Active license in good standing to practice`（Veterinary License）、`Registered to practice medicine`（Medical License）、`BCLS`（BLS 的写法）。
- 词典外证书（8 岗只因这个错）：CDL 的 S/P 背书、DMV Salesperson License、RIBA Part 3、CTS、保险销售牌照、PRINCE2/APM、OT License、项目内认证。
- gold 的写法也有影响：我把“二选一”写成 `CNA/HHA`、`BLS/ACLS`，脚本按整串比较会判错。把二选一拆开、并允许预测里出现 gold 的 preferred 证书之后，词典内准确率是 fresh50 0.82（41/50）、holdout v8 0.90（45/50）。所以 0.72 里有一部分是口径问题，但误报和漏抽是真实的。

## 数据观察

- 50 岗里有 8 个几乎没有要求内容的短帖（招聘网站导流帖、旅行护士模板、只有福利的兽医广告），这类岗位的技能和资格字段天然为空。
- 1 个法语 JD（Creaform，魁北克）。管线只支持英文，全量里加拿大岗位会有同类情况。
- 标题与正文不一致：标题 `Lecturer` 的正文是心理咨询实习督导；标题 `Senior Compliance Manager` 的正文是咨询顾问高级经理。

## 口径说明

- gold 口径沿用 `llm_labeling_v5_notes.md` 和 holdout：技能按“岗位是否要求”判定而不是按证据片段；yoe 取最低的总体年限，preferred 也计入；学位专业只有是本岗学科时才算技能；驾照、行医执照等词典外证书照常记录。
- gold 和判定是单人 LLM 标注，没有人工复核。family 的 19 个分歧和 86 条 borderline 判定值得人工抽查。
- n=50 时单项指标的区间约 ±0.12–0.14。fresh50 与 holdout 之间 0.05 左右的差异都在噪声内；family 低于 0.70、certs 低于 0.80 这两个结论不受噪声影响（family 的区间上限 0.74 略过线，但 holdout 的独立结果是 0.54，两个样本合并为 58/100 = 0.58，区间 0.48–0.67）。
