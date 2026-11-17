# 推理镜像
# 说明：
#   1. 只装推理依赖，不装 torch/transformers（镜像从 ~3GB 降到 ~400MB）
#   2. 端口 7860 是创空间类平台的通用约定，部署时按平台要求改
#   3. 模型文件已随仓库提交（392KB），不需要额外下载

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 国内构建用清华源，海外平台可删掉 -i 参数
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements-serve.txt

COPY src ./src
COPY models ./models
COPY data ./data

EXPOSE 7860

# 健康检查（部分平台会用）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/health').status==200 else 1)"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
