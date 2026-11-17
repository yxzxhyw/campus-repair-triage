"""
FastAPI 后端。

接口：
    GET  /                 前端页面
    GET  /api/health       健康检查（部署平台用）
    GET  /api/meta         类别定义、阈值等元信息
    POST /api/predict      单条预测
    POST /api/predict/batch  批量预测（最多 50 条）

本地运行：
    uvicorn src.api.main:app --reload --port 8000
文档：
    http://127.0.0.1:8000/docs
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .predictor import (CAT_META, REVIEW_THRESHOLD, URG_META,
                        get_predictor)

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "src" / "web"

MAX_LEN = 500

app = FastAPI(title="校园报修智能分派 API", version="0.1.0")

# 开发期放开跨域；上线同源部署时其实用不到，但留着不影响
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictIn(BaseModel):
    text: str = Field(..., description="工单原文")

    @field_validator("text")
    @classmethod
    def check_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("工单内容不能为空")
        if len(v) > MAX_LEN:
            raise ValueError(f"工单内容超过 {MAX_LEN} 字，请截断后再试")
        return v


class BatchIn(BaseModel):
    texts: list[str] = Field(..., description="工单文本列表")


@app.get("/api/health")
def health():
    try:
        p = get_predictor()
        return {"status": "ok", "model": p.display_name, "version": p.version}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"模型未就绪: {e}")


@app.get("/api/meta")
def meta():
    return {
        "categories": [{"code": k, **v} for k, v in CAT_META.items()],
        "urgencies": [{"code": k, **v} for k, v in URG_META.items()],
        "review_threshold": REVIEW_THRESHOLD,
        "max_len": MAX_LEN,
    }


@app.post("/api/predict")
def predict(body: PredictIn):
    try:
        return get_predictor().predict(body.text)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败: {e}")


@app.post("/api/predict/batch")
def predict_batch(body: BatchIn):
    texts = [t.strip() for t in body.texts if t.strip()]
    if not texts:
        raise HTTPException(status_code=400, detail="没有有效内容")
    if len(texts) > 50:
        raise HTTPException(status_code=400, detail="一次最多 50 条")
    p = get_predictor()
    return {"results": [{"text": t, **p.predict(t)} for t in texts]}


@app.get("/")
def index():
    f = WEB / "index.html"
    if not f.exists():
        raise HTTPException(status_code=404, detail="前端文件缺失")
    return FileResponse(f, media_type="text/html; charset=utf-8")
