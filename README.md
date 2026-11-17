# 校园报修智能分派 · Campus Repair Triage

> 把「宿舍水龙头一直滴水」这种自由文本，自动变成 **类别 + 紧急度 + 建议处理组 + 置信度**，
> 让后勤调度员少读一半字、不漏掉紧急工单。

**线上地址**：（部署后填这里）

---

## 项目进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| Step 1 | 方案设计、数据标注规范 | ✅ |
| Step 2 | 数据管道（防泄漏切分）、TF-IDF baseline、失败样例 | ✅ |
| **Step 3** | **FastAPI 后端（模型常驻、置信度、规则兜底）** | ✅ |
| **Step 4** | **前端页面（加载态、错误提示、结果卡片）** | ✅ |
| Step 5 | 部署上线（魔搭创空间） | 📄 文档已给，待执行 |
| Step 6 | BERT 多任务微调 + 与 baseline 对比 | ⬜ |
| Step 7 | 失败案例分析、500 字介绍、演示材料 | ⬜ |

---

## 当前模型效果（TF-IDF + 校准 SVM）

| 任务 | 准确率 | macro-F1 | 已知缺陷 |
|---|---|---|---|
| 类别分类 | 0.806 | 0.758 | **plumbing 召回 0** |
| 紧急度 | 0.778 | 0.539 | **P0 召回 0**（已用关键词规则兜底） |

> 这是在**按核心短语切分**的测试集上的结果——测试集里的说法训练时完全没见过。
> 普通随机切分会虚高到 95%+，那个数字没有意义。

报告：[report.json](models/baseline/report.json)　失败样例：[failures.csv](models/baseline/failures.csv)

---

## 快速开始（本地）

```powershell
# 1. 依赖
pip install -r requirements.txt          # 训练 + 服务全量
pip install fastapi "uvicorn[standard]"  # 若只想跑服务

# 2. 生成数据 → 训练 → 验证
python scripts/synth_data.py
python src/train/baseline.py
python scripts/smoke_test.py             # 不开服务也能验证推理链路

# 3. 起服务
uvicorn src.api.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000 就是网站；接口文档在 http://127.0.0.1:8000/docs 。

---

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 前端页面 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/meta` | 类别定义、复核阈值 |
| POST | `/api/predict` | `{"text": "..."}` → 分类结果 |
| POST | `/api/predict/batch` | `{"texts": [...]}`，最多 50 条 |

返回示例：

```json
{
  "category": {"code": "plumbing", "name": "水电维修", "group": "水电班",
               "confidence": 0.96, "top3": [...]},
  "urgency": {"code": "P0", "name": "紧急", "sla": "2 小时内响应", "level": 3},
  "confidence": 0.96,
  "needs_review": false,
  "review_reasons": [],
  "rule": {"triggered": false, "matched": []},
  "model": {"kind": "tfidf-svm", "version": "v1", "n_train": 431}
}
```

---

## 目录

```
campus-repair-triage/
├── docs/                 方案设计、数据标注规范
├── data/                 数据定义与合成数据
├── scripts/              数据生成、冒烟测试
├── src/train/            训练与评测
├── src/api/              后端（predictor 与框架解耦，换模型不动接口）
├── src/web/              前端单页
├── models/baseline/      模型与报告
├── deploy/               部署手册
└── Dockerfile
```

---

## 三个关键工程决策

1. **切分按 `template_id` 分组**，不随机切。随机切会让同一句话的不同说法同时出现在训练和测试里，指标虚高。
2. **类别和紧急度分开校准**，置信度取两者较小值——一个不确定就该复核。
3. **P0 加规则兜底**。模型 P0 召回为 0（"焦味"这类词训练时没见过），用关键词强制升级为紧急。这是补丁不是能力，报告里要如实写。

---

## 下一步

- 部署到魔搭创空间：[deploy/modelscope.md](deploy/modelscope.md)
- 换成 BERT 多任务模型，对比 baseline
