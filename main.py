import os
import json
import httpx
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 加载环境变量
load_dotenv()
app = FastAPI(title="Token出海API代理服务", version="2.0")

# 跨域支持（海外调用必备）
if os.getenv("ALLOW_CORS") == "true":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ==================== 从环境变量读取所有配置（无明文！） ====================
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY")
UPSTREAM_API_URL = os.getenv("UPSTREAM_API_URL")
YOUR_PROXY_API_KEY = os.getenv("YOUR_PROXY_API_KEY")

# 成本与定价（环境变量读取）
INPUT_COST = float(os.getenv("INPUT_TOKEN_COST", 0.07))
OUTPUT_COST = float(os.getenv("OUTPUT_TOKEN_COST", 0.21))
INPUT_PRICE = float(os.getenv("INPUT_TOKEN_PRICE", 0.11))
OUTPUT_PRICE = float(os.getenv("OUTPUT_TOKEN_PRICE", 0.32))

# ==================== OpenRouter 核心接口：模型列表（环境变量定价） ====================
@app.get("/v1/models")
async def list_models():
    created_time = int(time.time())
    # 自动计算：每1Token价格 = 环境变量定价 / 1000000
    prompt_price = str(INPUT_PRICE / 1_000_000)
    completion_price = str(OUTPUT_PRICE / 1_000_000)

    return {
        "data": [
            {
                "id": "deepseek-chat",
                "name": "DeepSeek Chat",
                "created": created_time,
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "quantization": "fp16",
                "context_length": 32768,
                "max_output_length": 8192,
                "pricing": {
                    "prompt": prompt_price,
                    "completion": completion_price,
                    "image": "0",
                    "request": "0",
                    "input_cache_read": "0"
                },
                "supported_sampling_parameters": [
                    "temperature", "top_p", "stop", "max_tokens"
                ],
                "supported_features": ["json_mode"],
                "description": "Cost-Effective & Fast DeepSeek Chat Model",
                "datacenters": [{"country_code": "US"}],
                "openrouter": {"slug": "deepseek/chat"}
            }
        ]
    }

# ==================== 核心代理接口 ====================
@app.post("/v1/chat/completions")
async def chat_completions(
    request: dict,
    authorization: str = Header(None)
):
    # 校验API密钥
    if not authorization or authorization.replace("Bearer ", "") != YOUR_PROXY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    headers = {
        "Authorization": f"Bearer {UPSTREAM_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url=UPSTREAM_API_URL,
                headers=headers,
                json=request
            )
            result = response.json()

        # 自动计费日志
        if "usage" in result:
            input_tokens = result["usage"]["prompt_tokens"]
            output_tokens = result["usage"]["completion_tokens"]
            cost = (input_tokens * INPUT_COST + output_tokens * OUTPUT_COST) / 1_000_000
            revenue = (input_tokens * INPUT_PRICE + output_tokens * OUTPUT_PRICE) / 1_000_000
            profit = revenue - cost
            print(f"📊 调用日志 | 输入：{input_tokens} | 输出：{output_tokens}")
            print(f"💰 利润：${profit:.4f}")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")

# ==================== 前端页面 & 健康检查 ====================
@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)