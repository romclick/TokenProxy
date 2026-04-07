import os
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# 加载配置
load_dotenv()
app = FastAPI(title="Token出海API代理服务", version="1.0")

# 跨域支持（海外前端调用必备）
if os.getenv("ALLOW_CORS") == "true":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 读取配置
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY")
UPSTREAM_API_URL = os.getenv("UPSTREAM_API_URL")
YOUR_PROXY_API_KEY = os.getenv("YOUR_PROXY_API_KEY")

# 计费参数
INPUT_COST = float(os.getenv("INPUT_TOKEN_COST"))
OUTPUT_COST = float(os.getenv("OUTPUT_TOKEN_COST"))
INPUT_PRICE = float(os.getenv("INPUT_TOKEN_PRICE"))
OUTPUT_PRICE = float(os.getenv("OUTPUT_TOKEN_PRICE"))

# ==================== 核心：API代理接口（兼容OpenAI格式） ====================
@app.post("/v1/chat/completions")
async def chat_completions(
    request: dict,
    authorization: str = Header(None)
):
    # 1. 验证用户的API密钥
    if not authorization or authorization.replace("Bearer ", "") != YOUR_PROXY_API_KEY:
        raise HTTPException(status_code=401, detail="无效的API密钥")

    # 2. 转发请求到国产大模型
    headers = {
        "Authorization": f"Bearer {UPSTREAM_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # 调用上游API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url=UPSTREAM_API_URL,
                headers=headers,
                json=request
            )
            result = response.json()

        # 3. Token计费统计（核心盈利逻辑）
        if "usage" in result:
            input_tokens = result["usage"]["prompt_tokens"]
            output_tokens = result["usage"]["completion_tokens"]
            
            # 计算成本 & 收入 & 利润
            cost = (input_tokens * INPUT_COST + output_tokens * OUTPUT_COST) / 1_000_000
            revenue = (input_tokens * INPUT_PRICE + output_tokens * OUTPUT_PRICE) / 1_000_000
            profit = revenue - cost

            # 打印日志（后台查看收益）
            print(f"📊 计费日志 | 输入Token：{input_tokens} | 输出Token：{output_tokens}")
            print(f"💰 成本：${cost:.4f} | 收入：${revenue:.4f} | 利润：${profit:.4f}")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理请求失败：{str(e)}")

# ==================== 前端页面入口 ====================
@app.get("/")
async def root():
    return FileResponse("index.html")

# 健康检查（部署用）
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)