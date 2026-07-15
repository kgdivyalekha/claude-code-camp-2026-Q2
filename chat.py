import asyncio
from client import LlamaGatewayClient

async def chat():
    client = LlamaGatewayClient()
    print("Local Llama Chat — type 'exit' to quit")

    while True:
        user = input("> ")
        if user.lower() in ("exit", "quit"):
            break

        reply = await client.send(user)
        print(reply)

if __name__ == "__main__":
    asyncio.run(chat())
