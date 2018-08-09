from collections import OrderedDict
from shutil import which
from typing import Optional

from .wget import WgetWrapper
from .base import DownloadState, DownloadWrapper
from .http_header import HeaderName

__NAME__ = 'download_wrapper'
__VERSION__ = '0.1'
__RELEASE__ = __VERSION__
__KEYWORDS__ = 'http, download'
__DESC__ = '常用下载工具的纯 Python 封装。支持进度回调。'
__LICENSE__ = 'MIT'
__AUTHOR__ = 'weiyulan'
__AUTHOR_EMAIL__ = 'yulan.wyl@gmail.com'
__URL__ = 'https://github.com/aheadlead/download_wrapper'

__all__ = [
    'WgetWrapper',
    'DownloadWrapper',
    'DownloadState',
    'HeaderName',
    'wrapper_factory',
]


def wrapper_factory(wrapper: Optional[str]=None, *args,
                    **kw) -> DownloadWrapper:
    """ wrapper 的工厂函数.

    传递参数 wrapper 时, 仅创建参数 wrapper 指定的下载工具.
    不传递参数 wrapper 时, 自动寻找系统中安装的下载工具.

    目前可传递给 wrapper 的值有: "wget".

    :param wrapper: 指定要使用的下载工具
    :return: 一个 DownloadWrapper 实例
    :raise RuntimeError: 当找不到指定的 wrapper 时
    """
    mapper = OrderedDict((
        ('wget', WgetWrapper),
        # 'axel': AxelWrapper,
        # 'curl': CurlWrapper,
        # 'aria2c': Aria2Wrapper,
    ))
    if wrapper:
        if wrapper not in mapper:
            raise RuntimeError('不支持的下载工具 "{}"'.format(wrapper))
        return mapper[wrapper](*args, **kw)

    for bk in mapper:
        if which(bk):
            return mapper[bk](*args, **kw)

    raise RuntimeError('没有可用的下载工具, 请安装以下任意一个下载工具: '
                       '{}.'.format(', '.join([name for name in mapper])))
