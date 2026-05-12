# 汽车维修知识图谱系统

基于规则-统计融合 NER 与多路关系抽取，从汽车维修手册 PDF 自动构建领域知识图谱，并提供交互式可视化探索界面。

## 项目结构

```
kg-repair/
├── src/
│   ├── extraction/          # 抽取模块
│   │   ├── pdf_extractor.py     # PyMuPDF PDF 解析
│   │   ├── text_preprocessor.py # jieba 分词 + 词性标注
│   │   ├── ner_extractor.py     # 双路 NER（规则词典 + CRF）
│   │   ├── re_extractor.py      # 双路 RE（触发词模板 + 共现启发式）
│   │   └── pipeline.py          # 抽取全流程协调
│   ├── graph/               # 图谱存储
│   │   ├── neo4j_connector.py   # Neo4j 驱动封装
│   │   ├── graph_builder.py     # 节点/关系写入
│   │   └── schema.py            # 实体类型与关系类型定义
│   └── api/                 # FastAPI 后端
│       ├── main.py              # 应用入口 + 路由注册
│       └── routes/              # graph / search / path / stats / eval
├── frontend/                # React + Vite 前端
│   └── src/
│       ├── App.jsx              # 主布局（侧边栏 + 图谱区）
│       ├── components/          # GraphCanvas / SearchBar / DetailPanel ...
│       └── services/api.js      # 后端接口封装
├── scripts/
│   ├── run_extraction.py        # 运行 PDF 抽取并写入 Neo4j
│   ├── train_crf.py             # 训练 CRF-NER 模型
│   ├── write_llm_annotations.py # 生成金标评估数据集
│   ├── evaluate.py              # NER / RE 评估（含图谱对齐）
│   └── generate_figures.py      # 生成评估图表
├── annotations/
│   └── samples.json             # 140 条金标标注（AnnotationLoader 格式）
├── output/                  # 所有输出文件（实体 JSON、评估指标、图表）
├── models/
│   └── crf_ner.pkl              # 训练好的 CRF 模型
├── dicts/
│   └── auto_repair_dict.txt     # 领域词典
├── docs/                    # 技术报告
└── config.yaml              # 全局配置
```

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+ |
| Neo4j | 5.x（Community Edition） |

Python 依赖安装：

```bash
pip install -r requirements.txt
```

前端依赖安装：

```bash
cd frontend
npm install
```

## 快速开始

### 1. 配置

编辑 `config.yaml`，填写 Neo4j 连接信息：

```yaml
neo4j:
  uri: "bolt://<host>:7687"
  username: "neo4j"
  password: "<password>"
```

### 2. 训练 CRF 模型（首次运行）

```bash
python scripts/train_crf.py
```

使用 `annotations/samples.json` 中的 140 条金标数据训练，模型保存至 `models/crf_ner.pkl`。

### 3. 抽取知识图谱

将维修手册 PDF 放入 `data/` 目录，在 `config.yaml` 中配置文件路径后运行：

```bash
python scripts/run_extraction.py
```

抽取结果（实体、关系）自动写入 Neo4j，同时输出 `output/entities.json`。

### 4. 启动后端

```bash
python -m uvicorn src.api.main:app --reload --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm run dev
```

访问 `http://localhost:5173` 打开知识图谱可视化界面。

## 评估

```bash
# 生成金标数据
python scripts/write_llm_annotations.py

# 运行评估
python scripts/evaluate.py
```

评估结果输出至 `output/eval_metrics.json`，可在前端"统计信息"中查看，或直接打开 `output/eval_report.html`。

**当前评估指标（140 条金标，672 实体，415 关系）：**

| 指标 | 对齐前 | 对齐后 |
|------|--------|--------|
| NER 整体 F1 | 0.472 | **0.716** |
| RE 整体 F1  | 0.146 | **0.744** |

## 核心技术

### 双路 NER
- **规则路径**：领域词典（300+ 词条）+ 正则匹配，精确率优先
- **CRF 路径**：sklearn-crfsuite BIO 序列标注，补充规则未覆盖的实体
- 合并策略：规则结果为主，CRF 只填补无重叠空白

### 双路 RE
- **触发词模板**：针对 11 类关系（`CAUSES_FAULT`、`HAS_SYMPTOM`、`REPAIRED_BY` 等）的动词/连词触发词列表
- **共现启发式**：同句实体类型组合规则（`_CO_RULES`），覆盖隐式关系
- 最大实体间距：45 个字符

### 图谱对齐评估
评估前对金标进行两步对齐，消除分词粒度差异导致的不公平惩罚：
1. NER 边界对齐（最大重叠替换）
2. RE 端点重映射 + 双来源纳入

## API 接口

| 路径 | 说明 |
|------|------|
| `GET /api/graph/overview` | 获取全景图（支持 `limit` 参数） |
| `GET /api/graph/subgraph/{name}` | 以节点为中心展开子图 |
| `GET /api/search/?q=` | 实体模糊搜索 |
| `GET /api/path/shortest` | 两节点间最短路径 |
| `GET /api/stats/` | 图谱统计（节点/关系类型分布） |
| `GET /api/eval/metrics` | 获取 NER/RE 评估指标 |

## 实体类型

`Vehicle` · `Component` · `Fault` · `Symptom` · `RepairStep` · `Tool` · `System`

## 关系类型

`CAUSES_FAULT` · `HAS_SYMPTOM` · `REPAIRED_BY` · `REQUIRES_TOOL` · `HAS_COMPONENT` · `BELONGS_TO_SYSTEM` · `PART_OF` · `AFFECTS` · `PRECEDES` · `INDICATES` · `DIAGNOSED_BY`
