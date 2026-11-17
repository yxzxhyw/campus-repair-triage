"""
合成工单数据生成器（v2）。

====================================================================
为什么不用模板拼接
====================================================================
第一版把"地点 + 模板"拼起来，结果训练集和测试集是同一批句子换个楼号，
模型只要记住模板就能得 99% —— 这个数字是假的，一上线就崩。

所以这一版的关键设计是【按核心短语切分】：

    每条"核心短语"（如"马桶堵了冲不下去"）是一个独立语义单元，
    它生成的所有句子只会出现在 train / val / test 其中一个集合里。

    测试集里出现的核心短语，训练时【一次都没见过】。

这模拟了真实场景：用户永远会说新的话。测出来的分数才可信。

====================================================================
用法
====================================================================
    python scripts/synth_data.py

输出：
    data/synth/tickets.csv     带 split 列（train/val/test）
"""

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(2026)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "synth" / "tickets.csv"

# ====================================================================
# 核心短语库：每条 = (核心短语, 类别, 紧急度)
# 紧急度是人工判定的，不用规则推——规则推出来的标签会让模型学到规则本身
# ====================================================================
CORE = [
    # ---------------- plumbing 水电 ----------------
    ("卫生间水管接口漏水", "plumbing", "P1"),
    ("水管爆了水一直往外喷", "plumbing", "P0"),
    ("水龙头一直滴水关不紧", "plumbing", "P2"),
    ("马桶堵了冲不下去", "plumbing", "P1"),
    ("下水道堵了脏水漫上来", "plumbing", "P0"),
    ("插座冒火花不敢用了", "plumbing", "P0"),
    ("灯管一直闪看着晃眼", "plumbing", "P2"),
    ("房间突然没电总闸跳了", "plumbing", "P1"),
    ("热水器不出热水", "plumbing", "P1"),
    ("洗手池下水很慢积水", "plumbing", "P2"),
    ("走廊的灯不亮了", "plumbing", "P2"),
    ("墙里的电线有焦味", "plumbing", "P0"),

    # ---------------- carpentry 家具门窗 ----------------
    ("宿舍门锁坏了关不上", "carpentry", "P0"),
    ("门被反锁了人出不来了", "carpentry", "P0"),
    ("床板塌了一块", "carpentry", "P0"),
    ("窗户合页松了关不严", "carpentry", "P1"),
    ("衣柜门掉下来了", "carpentry", "P2"),
    ("桌子腿断了站不稳", "carpentry", "P2"),
    ("纱窗破了个洞进蚊子", "carpentry", "P2"),
    ("门把手松了拧不动", "carpentry", "P2"),
    ("阳台门推不动卡住了", "carpentry", "P1"),
    ("窗玻璃裂了一道缝", "carpentry", "P1"),
    ("衣柜门关不上变形了", "carpentry", "P2"),
    ("床架螺丝掉了吱吱响", "carpentry", "P2"),

    # ---------------- network 网络与设备 ----------------
    ("校园网连不上认证失败", "network", "P1"),
    ("WiFi老是掉线重连不上", "network", "P1"),
    ("教室投影仪打不开黑屏", "network", "P1"),
    ("电脑开不了机按电源没反应", "network", "P1"),
    ("打印机卡纸打不出来", "network", "P2"),
    ("门禁刷不开进不了楼", "network", "P1"),
    ("网线接口松了插上没反应", "network", "P2"),
    ("监控画面黑屏没图像", "network", "P2"),
    ("路由器亮红灯上不了网", "network", "P1"),
    ("校园网速度特别慢网页打不开", "network", "P1"),
    ("投影连不上电脑没信号", "network", "P1"),
    ("实验室服务器连不上", "network", "P1"),

    # ---------------- cleaning 保洁环境 ----------------
    ("楼道垃圾桶满了没人收", "cleaning", "P2"),
    ("厕所异味很重熏得慌", "cleaning", "P2"),
    ("走廊有积水走路打滑", "cleaning", "P1"),
    ("宿舍霉味很重散不掉", "cleaning", "P1"),
    ("卫生间有很多蚊虫", "cleaning", "P2"),
    ("楼道堆满杂物挡路", "cleaning", "P2"),
    ("墙面有大片污渍", "cleaning", "P2"),
    ("下水道反味很臭", "cleaning", "P2"),
    ("教室地板一直没人拖", "cleaning", "P2"),
    ("宿舍进老鼠了", "cleaning", "P1"),
    ("垃圾堆在门口没人清", "cleaning", "P2"),
    ("公共卫生间没人打扫", "cleaning", "P2"),

    # ---------------- hvac 空调通风 ----------------
    ("空调不制冷吹的是热风", "hvac", "P1"),
    ("暖气片是凉的", "hvac", "P1"),
    ("空调出风口有异响很吵", "hvac", "P2"),
    ("空调遥控器没反应", "hvac", "P2"),
    ("新风系统不工作了", "hvac", "P1"),
    ("风扇不转了", "hvac", "P2"),
    ("空调漏水滴到地上", "hvac", "P1"),
    ("暖气不热房间很冷", "hvac", "P1"),
    ("出风口没有风", "hvac", "P1"),
    ("空调味道很重像霉味", "hvac", "P2"),
    ("空调开了一会儿就停", "hvac", "P1"),
    ("暖气阀门关不上一直漏", "hvac", "P1"),

    # ---------------- other 其他咨询 ----------------
    ("请问报修一般多久能上门", "other", "P2"),
    ("维修要收费吗", "other", "P2"),
    ("已经报修三天还没人来", "other", "P2"),
    ("想投诉维修师傅态度", "other", "P2"),
    ("怎么申请换个房间", "other", "P2"),
    ("能不能加急处理一下", "other", "P2"),
    ("这个问题应该找谁", "other", "P2"),
    ("建议增加夜间维修值班", "other", "P2"),
    ("想问下宿舍能不能装个架子", "other", "P2"),
    ("报修单怎么撤销", "other", "P2"),
    ("维修完没收尾垃圾", "other", "P2"),
    ("想查一下报修进度", "other", "P2"),
]

PREFIX = ["", "", "", "", "你好，", "老师您好，", "麻烦问一下，", "急！", "报修：", "同学你好，"]
SUFFIX = ["", "", "", "", "麻烦尽快处理", "已经好几天了", "谢谢", "晚上更严重", "不知道找谁修"]
LOCS = ["1号楼2层", "2号楼3层", "3号楼5层", "5号楼1层", "6号楼4层",
        "图书馆", "教学楼A", "教学楼B", "实验楼", "体育馆", "食堂", "7栋"]


def make_sentence(core: str, loc: str) -> str:
    """在核心短语外面套一层口语包装，模拟真实工单的噪声。"""
    parts = []

    pre = random.choice(PREFIX)
    if pre:
        parts.append(pre)

    # 60% 的工单会带地点
    if random.random() < 0.6:
        if random.random() < 0.5:
            parts.append(loc + "的")
        else:
            parts.append(loc)

    parts.append(core)

    suf = random.choice(SUFFIX)
    if suf:
        parts.append("，" + suf if random.random() < 0.5 else suf)

    text = "".join(parts)

    # 20% 去掉标点（真实输入常常没有标点）
    if random.random() < 0.2:
        text = text.replace("，", "").replace("。", "")

    # 10% 加口语语气词
    if random.random() < 0.1:
        text += random.choice(["啊", "呢", "了", "。。", "！"])

    return text


def main() -> None:
    # 1) 按类别分组，为每条核心短语分配唯一 template_id
    by_cat = defaultdict(list)
    for i, (core, cat, urg) in enumerate(CORE):
        by_cat[cat].append({"tid": f"{cat[:3]}_{i:03d}", "core": core,
                            "cat": cat, "urg": urg})

    # 2) 每条核心短语切分：70% train / 15% val / 15% test（类别内部分）
    split_of = {}
    for cat, items in by_cat.items():
        n = len(items)
        n_train = int(round(n * 0.70))
        n_val = int(round(n * 0.15))
        for j, it in enumerate(items):
            if j < n_train:
                split_of[it["tid"]] = "train"
            elif j < n_train + n_val:
                split_of[it["tid"]] = "val"
            else:
                split_of[it["tid"]] = "test"

    # 3) 每条核心短语生成 8–10 条句子
    rows = []
    idx = 1
    for cat, items in by_cat.items():
        for it in items:
            k = random.randint(8, 10)
            for _ in range(k):
                loc = random.choice(LOCS)
                rows.append({
                    "id": f"g{idx:04d}",
                    "text": make_sentence(it["core"], loc),
                    "location": loc,
                    "category": it["cat"],
                    "urgency": it["urg"],
                    "template_id": it["tid"],
                    "collected_at": "2026-11-14",
                    "source": "synth",
                    "split": split_of[it["tid"]],
                    "note": it["core"],
                })
                idx += 1

    random.shuffle(rows)
    for i, r in enumerate(rows, start=1):
        r["id"] = f"g{i:04d}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "text", "location", "category", "urgency",
            "template_id", "collected_at", "source", "split", "note"])
        w.writeheader()
        w.writerows(rows)

    # 4) 打印统计
    print(f"写入 {len(rows)} 条 -> {OUT}")
    print()
    print("切分分布:")
    for s, c in Counter(r["split"] for r in rows).most_common():
        print(f"  {s:<6} {c:>4} 条")

    print()
    print("各类别在测试集中的样本数:")
    test_rows = [r for r in rows if r["split"] == "test"]
    for k, v in sorted(Counter(r["category"] for r in test_rows).items()):
        print(f"  {k:<10} {v:>3}")

    print()
    print("紧急度分布（全量）:")
    for k, v in sorted(Counter(r["urgency"] for r in rows).items()):
        print(f"  {k:<4} {v:>4}")

    # 5) 泄漏检查：train 和 test 的 template_id 不能有交集
    train_t = {r["template_id"] for r in rows if r["split"] == "train"}
    test_t = {r["template_id"] for r in rows if r["split"] == "test"}
    overlap = train_t & test_t
    print()
    if overlap:
        print(f"[警告] 模板泄漏！train 和 test 共享 {len(overlap)} 个 template_id")
    else:
        print(f"[OK] 无模板泄漏：train {len(train_t)} 个核心短语，test {len(test_t)} 个，零交集")

    print()
    print("测试集示例（训练时从未见过的说法）:")
    for r in test_rows[:6]:
        print(f"  [{r['category']:<9}|{r['urgency']}] {r['text']}")


if __name__ == "__main__":
    main()
