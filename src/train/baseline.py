"""
Baseline：TF-IDF + 校准 SVM

====================================================================
为什么不是裸 LinearSVC
====================================================================
SVM 只给决策值，没有概率。但网站需要"置信度"来判断"是否转人工复核"。
所以外面套一层 CalibratedClassifierCV(sigmoid)：保住 SVM 的准确率，
同时得到近似校准的概率。

注意：置信度仍然只是"模型的自我感觉"，不能直接当"87% 正确率"展示给用户，
只用于"低于阈值 → 建议人工复核"这个内部判断。

====================================================================
用法
====================================================================
    python src/train/baseline.py
输出：
    models/baseline/model.joblib    模型包（向量器 + 两个分类器）
    models/baseline/report.json     指标 + 阈值分析
    models/baseline/failures.csv    判错样本
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score)
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "synth" / "tickets.csv"
OUTDIR = ROOT / "models" / "baseline"

CATS = ["plumbing", "carpentry", "network", "cleaning", "hvac", "other"]
URGS = ["P0", "P1", "P2"]


def fit_task(df, label, labels, class_weight=None):
    """在训练集上训练单个任务，返回模型、指标和测试集预测。

    class_weight:
        None        → 普通训练
        "balanced"  → 按类别频率反比加权。用于紧急度任务：
                      宁可把 P1 误报成 P0，也不能让 P0 漏掉（漏判代价最高）。
    """
    tr = df[df.split == "train"]
    te = df[df.split == "test"]

    vec = TfidfVectorizer(analyzer="char", ngram_range=(1, 3),
                          min_df=2, max_features=50000)
    Xtr = vec.fit_transform(tr["text"])      # 只在训练集 fit，防止信息泄漏
    Xte = vec.transform(te["text"])

    # LinearSVC 本身没有概率；外面套一层 sigmoid 校准，得到可用的置信度
    base = LinearSVC(C=1.0, max_iter=5000, class_weight=class_weight)
    clf = CalibratedClassifierCV(base, cv=3, method="sigmoid")
    clf.fit(Xtr, tr[label])

    pred = clf.predict(Xte)
    proba = clf.predict_proba(Xte)
    conf = proba.max(axis=1)
    truth = te[label].values

    acc = accuracy_score(truth, pred)
    mf1 = f1_score(truth, pred, average="macro", zero_division=0)

    print(f"\n{'=' * 60}")
    print(f"任务：{label}")
    print(f"{'=' * 60}")
    print(f"准确率   : {acc:.4f}")
    print(f"macro-F1 : {mf1:.4f}")
    print()
    print(classification_report(truth, pred, labels=labels, digits=3, zero_division=0))

    cm = confusion_matrix(truth, pred, labels=labels)
    print("混淆矩阵（行=真实，列=预测）:")
    print(f"{'':<10}" + "".join(f"{l[:8]:>10}" for l in labels))
    for i, l in enumerate(labels):
        print(f"{l[:8]:<10}" + "".join(f"{v:>10}" for v in cm[i]))

    # 阈值扫描：置信度低于 t 的转人工，看剩下的准确率
    print("\n阈值分析（低置信度转人工）:")
    print(f"  {'阈值':<8}{'自动处理比例':<14}{'自动处理准确率':<16}")
    sweep = []
    for t in np.arange(0.3, 0.96, 0.05):
        keep = conf >= t
        cov = float(keep.mean())
        acc_keep = float((pred[keep] == truth[keep]).mean()) if keep.sum() else 0.0
        sweep.append({"threshold": round(float(t), 2),
                      "coverage": round(cov, 3),
                      "accuracy": round(acc_keep, 4)})
        print(f"  {t:<8.2f}{cov:<14.1%}{acc_keep:<16.1%}")

    return {
        "vec": vec, "clf": clf,
        "metrics": {
            "accuracy": round(float(acc), 4),
            "macro_f1": round(float(mf1), 4),
            "n_train": int(len(tr)),
            "n_test": int(len(te)),
            "n_features": int(Xtr.shape[1]),
            "labels": labels,
            "confusion_matrix": cm.tolist(),
            "threshold_sweep": sweep,
        },
        "pred": pred, "truth": truth, "conf": conf,
        "texts": te["text"].values, "template_ids": te["template_id"].values,
    }


def show_failures(res, label, k=10):
    rows = []
    print(f"\n--- {label} 判错样例（最多 {k} 条）---")
    n = 0
    for text, t, p, c, tid in zip(res["texts"], res["truth"], res["pred"],
                                  res["conf"], res["template_ids"]):
        if t != p:
            rows.append({"task": label, "text": text, "truth": t, "pred": p,
                         "confidence": round(float(c), 3), "template_id": tid})
            if n < k:
                print(f"  真={t:<10} 预={p:<10} conf={c:.2f} | {text}")
                n += 1
    if not rows:
        print("  （无）")
    return rows


def main():
    df = pd.read_csv(DATA, encoding="utf-8")
    print(f"数据: {DATA.name}  共 {len(df)} 条  切分: {df.split.value_counts().to_dict()}")

    cat_res = fit_task(df, "category", CATS)
    # 紧急度用 balanced 权重：P0 只占 10%，不加权的话模型会直接放弃这一类
    urg_res = fit_task(df, "urgency", URGS, class_weight="balanced")

    fails = show_failures(cat_res, "category") + show_failures(urg_res, "urgency")

    OUTDIR.mkdir(parents=True, exist_ok=True)

    # 保存模型包：推理时需要的东西全在里面
    bundle = {
        "kind": "tfidf-lr",
        "version": "v1",
        "vec": cat_res["vec"],          # 类别和紧急度共用同一个向量器
        "clf_category": cat_res["clf"],
        "clf_urgency": urg_res["clf"],
        "cats": CATS,
        "urgs": URGS,
        "trained_on": str(DATA.relative_to(ROOT)),
        "n_train": cat_res["metrics"]["n_train"],
    }
    joblib.dump(bundle, OUTDIR / "model.joblib")

    report = {
        "model": "tfidf-char1-3 + LinearSVC(sigmoid)",
        "data": str(DATA.relative_to(ROOT)),
        "category": cat_res["metrics"],
        "urgency": urg_res["metrics"],
    }
    (OUTDIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if fails:
        pd.DataFrame(fails).to_csv(OUTDIR / "failures.csv", index=False, encoding="utf-8")

    print(f"\n模型已保存  : {OUTDIR / 'model.joblib'}")
    print(f"报告已保存  : {OUTDIR / 'report.json'}")
    print(f"失败样例    : {OUTDIR / 'failures.csv'}（{len(fails)} 条）")


if __name__ == "__main__":
    main()
