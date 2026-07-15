import asyncio
import argparse
from client import LlamaGatewayClient

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=str, help="Prompt to send")
    args = parser.parse_args()

    client = LlamaGatewayClient()
    reply = await client.send(args.prompt)
    print(reply)

if __name__ == "__main__":
    asyncio.run(main())
