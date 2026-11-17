"""
模型推理封装。

设计要点：**预测逻辑和 Web 框架解耦**。
以后把 baseline 换成 BERT，只需要新写一个实现同样接口的类，
`main.py` 一行都不用动。
"""

import os
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT / "models" / "baseline" / "model.joblib"))

# 置信度低于这个值 → 建议人工复核
# 依据：models/baseline/report.json 的阈值扫描
#   0.50 → 自动处理 79.6%，准确率 84.9%
#   0.65 → 自动处理 45.4%，准确率 95.9%
REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.50"))

CAT_META = {
    "plumbing":  {"name": "水电维修", "group": "水电班",   "desc": "漏水、跳闸、电路、下水道、灯具"},
    "carpentry": {"name": "家具门窗", "group": "木工班",   "desc": "门锁、门窗、床、桌椅、柜子"},
    "network":   {"name": "网络设备", "group": "信息中心", "desc": "校园网、投影、电脑、门禁、打印"},
    "cleaning":  {"name": "保洁环境", "group": "保洁班",   "desc": "垃圾、异味、积水、蚊虫、公共区域"},
    "hvac":      {"name": "空调通风", "group": "暖通班",   "desc": "空调、暖气、新风、出风口"},
    "other":     {"name": "其他咨询", "group": "综合受理", "desc": "咨询、投诉、无法归类"},
}

URG_META = {
    "P0": {"name": "紧急", "sla": "2 小时内响应", "level": 3},
    "P1": {"name": "较急", "sla": "24 小时内响应", "level": 2},
    "P2": {"name": "一般", "sla": "72 小时内响应", "level": 1},
}

# ---------------------------------------------------------------------
# 安全兜底规则
# 背景：模型在测试集上 P0 召回率为 0（见 models/baseline/report.json）。
# 原因不是类别不平衡——试过 class_weight="balanced"，指标一分没变；
# 真正原因是测试集的 P0 说法（如"焦味"）在训练集里完全没有出现，
# 模型没有任何特征可依据。加权只能移动决策阈值，造不出特征。
#
# 所以上线加一层关键词兜底：宁可误报，不可漏报。
# 这是工程补丁，不是模型能力的提升——报告里必须如实说明。
# ---------------------------------------------------------------------
P0_RULES = [
    "冒烟", "冒火花", "火花", "漏电", "焦味", "着火", "起火",
    "被困", "出不去", "反锁", "爆", "塌", "漏到楼下", "一直喷",
    "溢出", "燃气", "明火", "触电", "短路",
]


class BaselinePredictor:
    """TF-IDF + 校准 SVM。"""

    kind = "tfidf-svm"
    display_name = "TF-IDF + SVM（baseline）"

    def __init__(self, path: Path = MODEL_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"找不到模型文件 {path}，请先运行 python src/train/baseline.py")
        self.bundle = joblib.load(path)
        self.vec = self.bundle["vec"]
        self.clf_cat = self.bundle["clf_category"]
        self.clf_urg = self.bundle["clf_urgency"]
        # ⚠️ 必须用分类器的 classes_，不能用训练时的类别列表！
        # sklearn 的 predict_proba 列顺序 = classes_（按类别名排序），
        # 直接用 ["plumbing","carpentry",...] 索引会导致标签整体错位。
        self.cats = list(self.clf_cat.classes_)
        self.urgs = list(self.clf_urg.classes_)
        self.version = self.bundle.get("version", "v1")
        self.n_train = self.bundle.get("n_train", 0)

    def predict(self, text: str) -> dict:
        X = self.vec.transform([text])

        p_cat = self.clf_cat.predict_proba(X)[0]
        p_urg = self.clf_urg.predict_proba(X)[0]

        i = int(np.argmax(p_cat))
        j = int(np.argmax(p_urg))

        cat_code, cat_conf = self.cats[i], float(p_cat[i])
        urg_code, urg_conf = self.urgs[j], float(p_urg[j])

        # 安全兜底：命中 P0 关键词但模型没判紧急 → 强制升级
        matched = [k for k in P0_RULES if k in text]
        rule_triggered = bool(matched) and urg_code != "P0"
        if rule_triggered:
            urg_code = "P0"
            urg_conf = max(urg_conf, 0.5)

        # 取两个任务里更低的那个作为整体置信度——只要一个不确定就该复核
        conf = min(cat_conf, urg_conf)
        needs_review = conf < REVIEW_THRESHOLD or rule_triggered

        reasons = []
        if rule_triggered:
            reasons.append(f"命中安全关键词「{'、'.join(matched)}」，已强制升级为紧急")
        if conf < REVIEW_THRESHOLD:
            reasons.append(f"置信度 {conf:.0%} 低于阈值 {REVIEW_THRESHOLD:.0%}")
        if urg_code == "P0":
            reasons.append("判定为紧急工单，请人工确认后派单")

        return {
            "category": {
                "code": cat_code,
                "name": CAT_META[cat_code]["name"],
                "group": CAT_META[cat_code]["group"],
                "confidence": round(cat_conf, 4),
                "top3": self._topk(p_cat, self.cats, 3),
            },
            "urgency": {
                "code": urg_code,
                "name": URG_META[urg_code]["name"],
                "sla": URG_META[urg_code]["sla"],
                "level": URG_META[urg_code]["level"],
                "confidence": round(urg_conf, 4),
            },
            "confidence": round(conf, 4),
            "needs_review": needs_review,
            "review_reasons": reasons,
            "rule": {"triggered": rule_triggered, "matched": matched},
            "model": {"kind": self.kind, "name": self.display_name,
                      "version": self.version, "n_train": self.n_train},
        }

    def _topk(self, proba, labels, k):
        idx = np.argsort(proba)[::-1][:k]
        return [{"code": labels[i], "name": CAT_META[labels[i]]["name"],
                 "prob": round(float(proba[i]), 4)} for i in idx]


_cache: dict[str, BaselinePredictor] = {}


def get_predictor() -> BaselinePredictor:
    """进程内单例——模型只加载一次，不能每个请求加载。"""
    key = str(MODEL_PATH)
    if key not in _cache:
        _cache[key] = BaselinePredictor(MODEL_PATH)
    return _cache[key]
