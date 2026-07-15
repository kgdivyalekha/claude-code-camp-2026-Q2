import httpx

class LlamaGatewayClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    async def send(self, prompt: str, model: str = "llama3.2:3b"):
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def generate(self, prompt: str):
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/generate",
                json={"prompt": prompt}
            )
            response.raise_for_status()
            return response.json()["response"]
