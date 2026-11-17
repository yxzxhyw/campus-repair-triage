"""临时冒烟测试：验证推理链路（跑完即删）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.predictor import get_predictor

p = get_predictor()
print("模型:", p.display_name, "| 训练样本:", p.n_train)

cases = [
    "3号楼502卫生间水管接口漏水，地上已经积了一层水",
    "宿舍空调吹出来是热风，晚上热得睡不着",
    "请问报修一般多久能上门",
    "走廊的灯不亮了",
    "墙里的电线有焦味",
    "马桶堵了冲不下去",
]

print()
print(f"{'输入':<30} {'类别':<8} {'紧急':<4} {'conf':<6} 建议")
print("-" * 78)
for t in cases:
    r = p.predict(t)
    c, u = r["category"], r["urgency"]
    flag = "人工复核" if r["needs_review"] else "直接派单"
    print(f"{t[:28]:<30} {c['name']:<8} {u['code']:<4} "
          f"{r['confidence']:<6.2f} {flag}")

print()
r = p.predict(cases[0])
print("完整返回结构:")
import json
print(json.dumps(r, ensure_ascii=False, indent=2)[:900])
