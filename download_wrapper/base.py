import enum
import threading
import time
from collections import deque
from threading import Lock
from typing import Optional, Callable, Tuple, List, Union

from pathlib import Path

from download_wrapper.helper import kilobytes_to_bytes

__all__ = ['DownloadWrapper', 'DownloadState']


class DownloadCallback:

    callback_T = Optional[Callable[['DownloadWrapper'], None]]

    def __init__(self,
                 on_finish: callback_T=None,
                 on_error: callback_T=None,
                 on_progress_update: callback_T=None,
                 on_stall: callback_T=None):
        self.on_finish = on_finish
        self.on_error = on_error
        self.on_progress_update = on_progress_update
        self.on_stall = on_stall

    def register_finish(self, callback: callback_T):
        """ 注册当下载完成时的回调函数. """
        self.on_finish = callback

    def register_error(self, callback: callback_T):
        """ 注册当下载失败时的回调函数. """
        self.on_error = callback

    def register_progress_update(self, callback: callback_T):
        """ 注册回报下载进度的回调函数. """
        self.on_progress_update = callback

    def register_stall(self, callback: callback_T):
        """ 注册当下载卡住时的回调函数. """
        self.on_stall = callback


@enum.unique
class DownloadState(enum.Enum):
    #
    #                            call stop()
    #                         +----------------> [STOP]
    #      call start()       |      succeeded
    #  [READY] --------> [DOWNLOAD] -----------> [FINISH]
    #                         |
    #                         +----------------> [ERROR]
    #                               failed
    READY = 0
    DOWNLOAD = 1
    FINISH = 2
    ERROR = 3
    STOP = 4


State = DownloadState  # shortcut


class DownloadWrapper:

    name = ''

    def __init__(self, *args, **kw):
        self._state = State.READY  # type: State

        self._parallel = 1
        self._url = str()
        self._proxy = str()
        self._output_path = None  # type: Optional[Path]
        self._headers = list()  # type: List[Tuple[str, str]]

        self._start_time = None  # type: Optional[float]
        self._finish_time = None  # type: Optional[float]
        self._error_time = None  # type: Optional[float]
        self._stop_time = None  # type: Optional[float]

        self._sample_points = deque([], 100)
        self._sample_points_lock = Lock()

        self._stall_tracer_th = threading.Thread(
            target=self._stall_checker_thread, daemon=True,
        )

        # self._sample_points 的类型为 Deque[Tuple[float, int]]
        # (因为 Python 3.5.2 还不支持 Deque 的 Type Annotations.)
        #
        # float 为采样时间, int 为上一段时间下载的字节数.
        #
        # e.g.
        # self._sample_points = [
        #     (1519982934.3242974, 1508502),
        #     (1519982935.3242974, 2305083),
        #     (1519982936.3242974, 8465302),
        #     (1519982937.3242974, 10428304),
        #     (1519982938.3242974, 14208540),
        # ]
        #
        # 以最后一个元素为例, 指截至 1519982938.3242974 这一刻相对上次采样点多
        # 下载了 14208540 字节.

        # _total_size 和 _downloaded_size 的单位均为字节
        # _total_size 为下载的文件大小, 如无法获得则为 None
        self._total_size = None  # type: Optional[int]
        # _downloaded_size 可能不是准确值, 仅用来计算进度和速度.
        self.__downloaded_size = 0  # type: int

        self._callback = DownloadCallback()  # type: DownloadCallback

    @property
    def parallel(self) -> int:
        return self._parallel

    @parallel.setter
    def parallel(self, value: int) -> None:
        """ 设定并发数.

        如果 Wrapper 不支持并发下载, 则不会设定成功, 且并发值为 1.
        如果传入的 parallel 值不合法, 则不会设定成功, 保留原值.
        """
        if isinstance(value, int) and value in range(1, 21):
            self._parallel = value

    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, value: str) -> None:
        """ 设定下载链接. 只能设置一次.

        仅支持以 "http" 开头的链接 (亦支持 "https").
        """
        if not self._url:  # 保证 url 只能被设置一次
            if isinstance(value, str) and value.startswith('http'):
                self._url = value

    @property
    def proxy(self) -> str:
        return self._proxy

    @proxy.setter
    def proxy(self, value: str) -> None:
        """ 设定代理. 只能设置一次.

        需要 IP 地址 (或域名) 和端口号, 以冒号分隔.

        正确:

            "127.0.0.1:8118"
            "proxy.my-company.com:23333"

        不正确:

            "127.0.0.1"
            "http://127.0.0.1:8118"

        仅支持 http 代理 (https 也会使用).
        """
        if not self._proxy:  # 保证 proxy 只能被设置一次
            if isinstance(value, str):
                self._proxy = value

    @property
    def output_path(self) -> Path:
        return self._output_path

    @output_path.setter
    def output_path(self, value: Union[Path, str]) -> None:
        """ 设定保存地址. 只能设置一次. """
        if not self._output_path:  # 保证 output_path 只能被设置一次
            if isinstance(value, Path):
                self._output_path = value
            elif isinstance(value, str):
                self._output_path = Path(value)
            else:
                raise RuntimeError('output_path 的参数 value 只接受 Path 或 str')
        else:
            raise RuntimeError('output_path 被设置了多次')

    @property
    def total_size(self) -> int:
        """ 返回正在下载的文件的总大小, 单位字节. """
        return self._total_size

    @property
    def downloaded_size(self) -> int:
        """ 返回正在下载的文件的已下载部分的大小, 单位字节. """
        return self._downloaded_size

    @property
    def _downloaded_size(self) -> int:
        return self.__downloaded_size

    @_downloaded_size.setter
    def _downloaded_size(self, value):
        self._add_sample_point(value - self.__downloaded_size)
        self.__downloaded_size = value

    @property
    def callback(self) -> DownloadCallback:
        return self._callback

    @property
    def state(self) -> DownloadState:
        return self._state

    def add_header(self, key, value):
        self._headers.append((key, value))

    def start(self) -> None:
        """ 开始下载. """
        self._state = DownloadState.DOWNLOAD
        self.on_start()
        if self.callback.on_stall:  # 非空则代表启动卡滞检测
            self._stall_tracer_th.start()

    def on_start(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        """ 停止下载. """
        self._state = DownloadState.STOP
        if self._stall_tracer_th.is_alive():
            self._stall_tracer_th.join()
        self.on_stop()

    def on_stop(self) -> None:
        raise NotImplementedError()

    def wait(self, timeout: Optional[float]=None) -> None:
        """ 等待下载结束.

        可以透过参数 timeout 指定超时时间, None 则关闭超时功能.

        :raise TimeoutError: 当超时时
        """
        self.on_wait(timeout)

    def on_wait(self, timeout: Optional[float]=None) -> None:
        raise NotImplementedError()

    def progress(self) -> int:
        """ 返回任务完成的进度. 返回值为百分比, 从 0 到 100. """
        if not self.total_size or self.downloaded_size <= 0:
            return 0

        if self.downloaded_size >= self.total_size:
            return 100

        from math import ceil
        return int(ceil(100.0 * self.downloaded_size/self.total_size))

    def speed(self) -> int:
        return self.average_speed()

    def average_speed(self) -> int:
        """ 返回自开始下载以来的平均速度. 返回值为 B/s. """
        if self.state == DownloadState.READY:
            return 0
        end_time = {
            DownloadState.DOWNLOAD: time.time(),
            DownloadState.ERROR: self._error_time,
            DownloadState.STOP: self._stop_time,
            DownloadState.FINISH: self._finish_time,
        }[self.state]
        return self._downloaded_size/(end_time - self._start_time)

    def _instant_speed_locked(self) -> int:

        if len(self._sample_points) > 2:
            anchor = time.time()
            # 得到 5 秒以内的采样点
            filtered = list(filter(lambda i: anchor - i[0] < 5,
                                   self._sample_points))
            if len(filtered) > 2:
                delta_data = sum(i[1] for i in filtered) - filtered[0][1]
                delta_t = anchor - filtered[0][0]
                return delta_data/delta_t
            else:
                return 0
        else:
            return self.average_speed()

    def instant_speed(self) -> int:
        """ 返回瞬时速度. 返回值为 B/s. """
        with self._sample_points_lock:
            return self._instant_speed_locked()

    def _add_sample_point(self, downloaded_size: int) -> None:
        with self._sample_points_lock:
            self._sample_points.append((time.time(), downloaded_size))

    def _stall_checker_thread(self):
        # 变量 differentiator 用于将电平触发的 stall 回调转为边沿触发.
        #
        # 1.  当 differentiator 为 False 时, 判定为 stall 会触发回调
        #     on_stall, 且 differentiator 翻转为 True;
        # 2.  当 differentiator 为 True 时, 再次判定为 stall 不会触发回调;
        # 3.  当当前状态判定为非 stall 时, differentiator 置为 False.

        differentiator = False

        # 跳过慢启动阶段
        while time.time() - self._start_time < 4:
            if self.state != DownloadState.DOWNLOAD:
                return
            time.sleep(1)

        while self.state == DownloadState.DOWNLOAD:
            # 当瞬间速度低于 5KiB/s
            stalled = self.instant_speed() < kilobytes_to_bytes(5)
            if stalled:
                if not differentiator:
                    differentiator = True
                    if self._callback.on_stall:
                        self.callback.on_stall(self)
                else:
                    pass  # do nothing
            else:
                differentiator = False
            time.sleep(1)

    def __del__(self):
        self.stop()
