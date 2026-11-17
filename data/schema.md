# 数据字段定义

一份数据 = 一个 CSV 文件，UTF-8 编码，**不带 BOM**，逗号分隔，首行是表头。

## 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 唯一标识，如 `g0001`。不要用行号，避免重排后错位 |
| `text` | string | ✅ | 工单原文。**保留口语、错别字、标点缺失**，这是真实输入的样子 |
| `location` | string | ❌ | 地点，脱敏到"楼栋+楼层"粒度。没有就留空 |
| `category` | enum | ✅ | `plumbing` `carpentry` `network` `cleaning` `hvac` `other` |
| `urgency` | enum | ✅ | `P0` `P1` `P2` |
| `template_id` | string | ✅ | **切分依据**。同一条核心语义的所有变体共享同一个 id |
| `collected_at` | date | ✅ | `YYYY-MM-DD`，用于分析季节对紧急度的影响 |
| `source` | enum | ✅ | `export`(系统导出) / `forum`(公开帖子) / `mock`(人工撰写) / `synth`(程序合成) |
| `split` | enum | ✅ | `train` / `val` / `test`，由生成脚本按 `template_id` 分配 |
| `note` | string | ❌ | 标注理由，或原始核心短语 |

## 示例

```csv
id,text,location,category,urgency,template_id,collected_at,source,split,note
g0001,报修：墙里的电线有焦味麻烦尽快处理！,实验楼,plumbing,P0,plu_011,2026-11-14,synth,test,墙里的电线有焦味
g0002,你好，走廊的灯不亮了晚上更严重,教学楼B,plumbing,P2,plu_010,2026-11-14,synth,test,走廊的灯不亮了
```

## ⚠️ 切分规则（最重要的一条）

**必须按 `template_id` 分组切分，绝对不能按行随机切分。**

```
正确：  template A 的全部变体 → train
        template B 的全部变体 → test     （B 在 train 里一个都没有）

错误：  同一句话的 10 种说法，7 条进 train，3 条进 test
        → 模型只要记住句式就能"预测"，指标虚高，上线即崩
```

数据生成脚本 `scripts/synth_data.py` 已内置这个逻辑，并在结尾做泄漏自检：

```
[OK] 无模板泄漏：train 48 个核心短语，test 12 个，零交集
```

自己加数据时，**新句子必须给一个新的 `template_id`**，否则会污染测试集。

## 关于 `source` 字段

这个字段是给报告用的。写失败分析时你必须能回答：
"测试集里有多少条是合成数据？" 如果 100% 是合成的，结论强度要打折。

**当前状态**：全部 `synth`，必须在报告的"不足"一节显式声明。
