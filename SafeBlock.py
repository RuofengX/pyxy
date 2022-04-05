from typing import Any
from aisle import LogMixin, LOG
import uuid
import json
import random
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

class Key():
    """用来加解密的key

    Raises:
        TypeError: 如果__set__传入了非bytes类型
        ValueError: 如果__set__传入非16位

    Returns:
        self: 一个16位比特串
    """

    def __init__(self, keyString: str='') -> None:
        if not keyString:
            keyString = str(uuid.uuid4().hex)
        self.keyString = keyString
        self.keyBytes = keyString.encode('utf-8')
            
    @property
    def keyBytes(self):
        return self._keyValue

    @keyBytes.setter
    def keyBytes(self, value):
        if not isinstance(value, bytes):
            raise TypeError('key must be bytes')
        elif len(value) != 32:
            raise ValueError('key must be 32 bytes')
        else:
            self._keyValue = value


class Crypto(LogMixin):
    def __init__(self, keyBytes: bytes) -> None:
        super().__init__()
        self.cipher = AES.new(keyBytes, AES.MODE_ECB)
        self.blockSize = 32

    def encrypt(self, b: bytes) -> bytes:
        """输入的字节串无需填充"""
        return self.cipher.encrypt(pad(b, self.blockSize))

    def decrypt(self, b: bytes) -> bytes:            
        try:
            return unpad(self.cipher.decrypt(b), self.blockSize)
        except ValueError:
            """解密错误，解密失败"""
            self.logger.warning('解密错误，解密失败')
            raise DecryptError('解密错误')


class Block(LogMixin):
    """安全区块
    """

    @classmethod
    def fromBytes(cls, key: Key, b: bytes) -> 'Block':
        """解密字节串并转换为Block对象

        Args:
            key (Key): 加密密钥

        Raises:
            DecryptError: 解密错误，解密失败
        """
        crpto = Crypto(key.keyBytes)
        rebuildDict = json.loads(crpto.decrypt(b).decode('utf-8'))
        rtn = cls(key, {})  # 创建空对象
        rtn.uuid = rebuildDict['uuid']  # 强制重载
        rtn.payload = rebuildDict['payload']  # 强制重载
        vTime = rebuildDict['timestamp'] - int(time.time())
        if vTime >= 10:
            raise DecryptError('时间戳误差大于10秒')
        rtn.timestamp = rebuildDict['timestamp']
        return rtn

    def __init__(self, key: Key, payload: dict = {}) -> None:
        """安全区块构造函数"""
        super().__init__()

        # 三个参数（简称ukp）都会加密
        self.uuid = uuid.uuid4().hex
        self.key = key.keyString
        self.payload = payload
        self.timestamp = int(time.time())

        self.__bytesBuffer = None  # 缓存解密结果提高性能
        self.__crpto = Crypto(key.keyBytes)
    
    # TODO: 需要兼容多进程
    def __setattr__(self, __name: str, __value: Any) -> None:
        self.__dict__['__bytesBuffer'] = None  # 刷新缓存
        return super().__setattr__(__name, __value)

    @property
    def __ukpt(self) -> dict:
        # ukpt取首字母
        return {
            'uuid': self.uuid,
            'key': self.key,
            'payload': self.payload,
            'timestamp': self.timestamp
            
        }

    @property
    def blockBytes(self) -> bytes:
        """自我加密后，返回ukp的字节串"""
        if not self.__bytesBuffer:
            jsondumps = json.dumps(self.__ukpt)
            bBlock = jsondumps.encode('utf-8')
            self.__bytesBuffer = self.__crpto.encrypt(bBlock)
        return self.__bytesBuffer


class DecryptError(Exception):
    """解密错误"""
    pass

if __name__ == '__main__':
    key = Key()
    LOG.info(key.keyBytes)
    