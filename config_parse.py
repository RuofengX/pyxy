import os
import toml
from typing import Iterable, Union, Any, NoReturn, Dict
import pprint

from safe_block import Key
from aisle import LogMixin

EXAMPLE_FILE = "./config.example"
DEFAULT_FILE = "./config.toml"
VERSION = 1  # TODO: 添加跨版本控制代码


class PyxyConfig:
    """配置文件类，三个属性，每个属性存储一个字典"""

    def __init__(self) -> None:
        with ConfigParser() as config:
            self.all = config.config
        return

    @property
    def version(self) -> int:
        return self.all["version"]

    @property
    def server(self) -> Dict[str, Any]:
        """获取服务器集合
        Raise:
            KeyError: 如name超出了配置文件的第一层的属性列表，则会引起KeyError
        """
        return self.all["server"]

    @property
    def client(self) -> Dict[str, Any]:
        """获取客户端属性集合
        Raise:
            KeyError: 如name超出了配置文件的第一层的属性列表，则会引起KeyError
        """
        return self.all["client"]

    @property
    def general(self) -> Dict[str, Any]:
        """获取通用属性集合
        Raise:
            KeyError: 如name超出了配置文件的第一层的属性列表，则会引起KeyError
        """
        return self.all["general"]


class ConfigParser(LogMixin):
    def __init__(self) -> None:
        super().__init__()

        if not os.path.exists("./config.toml"):
            self.gen_default()

        config = self.load_file("./config.toml")

        self.check_config(config)
        self.config = config

    def load_file(self, path: str) -> dict:
        self.logger.info(f"读取文件{path}")

        try:
            config = toml.load(path)
        except toml.TomlDecodeError as err:
            self.logger.error("文件格式错误导致读取失败")
            self.logger.error(err)
        except IOError as err:
            self.logger.error("路径无效")
            self.logger.error(err)
        except Exception as err:
            self.error(f"未知错误 > {type(err)} {err}")

        return config

    def gen_default(self) -> NoReturn:
        """动态生成默认配置

        配置生成之后触发TypeError，不会返回
        """
        self.logger.error("配置文件不存在")
        self.logger.warning("生成默认配置...")

        config = self.load_file(EXAMPLE_FILE)

        config["general"]["key"] = Key().key_string
        config["general"]["domain"] = "将你的服务器域名粘贴至此，例如www.example.com"
        config["server"]["crt_file"] = "填入你的SSL密钥的crt文件的路径"
        config["server"]["key_file"] = "填入你的SSL密钥的key文件的路径"

        with open(DEFAULT_FILE, "wt", encoding="utf-8") as f:
            toml.dump(config, f)

        self.logger.warning(f"配置文件生成完成，路径{DEFAULT_FILE}，请查看并修改文件")
        raise TypeError(f"配置文件生成完成，路径{DEFAULT_FILE}，请查看并修改文件")

    def check_config(self, config: dict) -> bool:
        """检查config是否满足样例标准

        Args:
            config (dict): 需要检查的配置字典

        Returns:
            bool: 正逻辑，可以使用则为真
        """

        def check_i(
            target: Union[dict, Iterable[Any]],
            standard: Union[dict, Iterable[Any]],
        ) -> bool:
            """递归检查target字典是否包含standard所有key"""
            if not isinstance(target, dict) or not isinstance(standard, dict):
                return True

            for key in standard:
                if key not in target.keys():
                    return False

                if isinstance(standard[key], dict):
                    if not check_i(target[key], standard[key]):
                        return False

            return True

        target_config = config
        standard_config = self.load_file(EXAMPLE_FILE)
        rtn = check_i(target_config, standard_config)
        if rtn:
            self.logger.info("配置文件格式正确")
        else:
            self.logger.critical("配置文件格式错误！")
            raise TypeError("配置文件格式错误")
        return rtn

    def __enter__(self):
        return self

    def __exit__(self, err_type, err, traceback):
        del self


if __name__ == "__main__":
    p = ConfigParser()
    config = PyxyConfig()
    pprint.pprint(config.all)
