from aisle import LogMixin
import asyncio

class StreamBase(LogMixin):
    async def copy(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        """将r中的数据写入w"""
        while 1:
            try:
                data = await r.read(4096)  # 这里阻塞了，等待本地的数据
                # self.logger.info(f'{r.at_eof()}')
                if r.at_eof():
                    self.logger.debug('远程连接关闭')
                    break
                if not data:
                    w.close()
                    await w.wait_closed()
                w.write(data)
                await w.drain()
            except Exception as e:
                self.logger.warning(f'远程连接关闭 {e}')
                break
            
        return