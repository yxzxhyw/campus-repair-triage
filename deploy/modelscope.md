# 部署到魔搭创空间（路线 A）

> 目标：拿到一个 `https://modelscope.cn/studios/...` 的公网地址，评委点开就能用。
> 成本 0 元，不需要服务器，不需要备案。

---

## 0. 为什么是这条路

| 顾虑 | 实际情况 |
|---|---|
| 要不要买服务器 | 不要，平台给免费 CPU 实例 |
| 要不要备案 | 不要，平台子域名 |
| 模型 392KB 放得下吗 | 放得下，仓库限制通常在 GB 级 |
| 内存够吗 | 够。TF-IDF+SVM 推理只占几百 MB |
| 冷启动多久 | 免费实例会休眠，首次访问等 10–30 秒 |

---

## 1. 前提：代码在 GitHub 上

创空间推荐从 Git 仓库导入。先在本地提交：

```powershell
cd C:\Users\Lenovo\Documents\deepseek-harness\default-workspace\campus-repair-triage
git init -b main
git add .
git commit -m "feat: 报修工单分派 baseline（API + 前端 + Docker）"
```

然后在 GitHub 上新建仓库 `campus-repair-triage`（Public），推到远端：

```powershell
git remote add origin https://github.com/yxzxhyw/campus-repair-triage.git
git push -u origin main
```

> 注意 `models/baseline/model.joblib` 只有 392KB，`.gitignore` 里排除了 `*.bin/*.pt` 但没排除 `.joblib`，所以会被提交——**这是故意的**，部署时需要它。

---

## 2. 创建创空间

1. 打开 https://modelscope.cn ，用手机号或阿里云账号登录
2. 右上角头像 → **创空间** → **创建创空间**
3. 填写：
   - **名称**：`campus-repair-triage`（会成为 URL 的一部分）
   - **可见性**：**公开**（评委要能访问）
   - **SDK / 框架**：选 **Docker**（不是 Gradio/Streamlit）
   - **许可证**：随便选一个，如 Apache-2.0
4. 创建后会得到一个 Git 仓库地址，形如：
   ```
   https://www.modelscope.cn/studios/<你的用户名>/campus-repair-triage.git
   ```

> 平台界面会更新，字段名称可能略有差异，**核心是选 Docker、公开、记住端口要求**。

## 3. 上传代码

**方式一（推荐）：直接推**

```powershell
git remote add modelscope https://www.modelscope.cn/studios/<你的用户名>/campus-repair-triage.git
git push modelscope main
```

首次会要求登录：用户名是你的魔搭账号，密码用 **访问令牌**（在「账号设置 → 访问令牌」里生成，不是登录密码）。

**方式二：网页上传**
创空间页面 → 文件 → 上传，把整个项目拖进去。适合网络不稳时。

## 4. 关键配置（最容易错的地方）

| 配置 | 值 | 说明 |
|---|---|---|
| 端口 | **7860** | 必须和 Dockerfile 的 `CMD ... --port 7860` 一致 |
| Dockerfile 路径 | `Dockerfile` | 在仓库根目录，不用改 |
| 启动命令 | 由 Dockerfile 的 CMD 决定 | 不要在平台里再填一次 |

如果平台要求填端口，填 `7860`。如果平台的默认端口是别的值（比如 8080），**改 Dockerfile 最后一行的 `--port` 即可**，两处必须一致。

## 5. 等待构建

进入创空间页面 → 看**构建日志**。第一次构建 3–8 分钟（装依赖）。

成功标志：
```
Uvicorn running on http://0.0.0.0:7860
INFO:     Application startup complete.
```

失败的话日志里会有明确报错，对照下面的表排查。

## 6. 验证部署

浏览器打开你的创空间地址，应该看到「校园报修智能分派」页面。

再验证接口：

```
https://<你的地址>/api/health
```
应返回：
```json
{"status":"ok","model":"TF-IDF + SVM（baseline）","version":"v1"}
```

**把这三个都验一遍再收工**：
- [ ] 首页能打开
- [ ] 输入一条工单能出结果
- [ ] `/api/health` 返回 ok

---

## 7. 常见错误

| 现象 | 原因 | 解决 |
|---|---|---|
| 构建失败，`No such file: requirements-serve.txt` | 文件没提交上去 | `git status` 检查，补 `git add` |
| 启动后页面 502 / 无法访问 | 端口不一致 | 平台配置端口 = Dockerfile 端口 |
| `ModuleNotFoundError: fastapi` | 依赖没装 | 检查 `requirements-serve.txt` 是否被 COPY |
| 页面能开但预测报 500 | 模型文件缺失 | 确认 `models/baseline/model.joblib` 在仓库里 |
| `InconsistentVersionWarning` | sklearn 版本不一致 | `requirements-serve.txt` 已锁版本，确认没被改动 |
| `Could not find a version that satisfies numpy==2.5.4` + `Requires-Python >=3.12` | **版本号是从本地 Python 3.15 抄的，但镜像用 3.11** | 降到该 Python 版本支持的最高版（如实测 3.11 → numpy 2.4.6） |
| 首次访问很慢（20 秒+） | 免费实例冷启动 | 正常现象，说明里写一句"首次访问需等待" |

---

## 8. 备选方案（魔搭不通时）

| 平台 | 特点 | 注意 |
|---|---|---|
| Hugging Face Spaces | 生态最好，Docker SDK 一样能用 | `*.hf.space` 国内访问不稳，需自行评估 |
| Railway | 部署最简单，$5 试用额度 | 需要国际信用卡 |
| Render | 有免费层 | 免费实例会休眠 |

换平台基本只改端口，代码不用动。

---

## 9. 上线后要做的三件事

1. **在 README 顶部写上访问地址**（评委第一眼要看）
2. **截一张图**放进 README，防止评审时平台抽风
3. 记录**部署日期和版本**，方便写报告的"系统实现"一节
