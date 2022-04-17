import asyncio
import sys


class MultiServer:
    def __init__(self, max_size: int = 4):
        self.max_size = max_size

    def run_until_complete(self):
        loop = asyncio.get_event_loop()
        for i in range(self.max_size):
            loop.create_task(self.start_process())
        loop.run_forever()

    async def start_process(self):
        p = await asyncio.create_subprocess_exec("python3", "server.py", stdout=sys.stdout, stderr=sys.stderr)
        await p.wait()


if __name__ == "__main__":
    server = MultiServer()
    server.run_until_complete()
