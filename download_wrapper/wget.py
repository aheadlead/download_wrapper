import _io
import re
import selectors
import shlex
import subprocess
import threading
import time
from typing import Optional

from .base import DownloadWrapper, DownloadState

__all__ = ['WgetWrapper']


class WgetWrapper(DownloadWrapper):

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._tracer_th = threading.Thread(target=self._tracer)

        self._popen_hd = None  # type: Optional[subprocess.Popen]
        self._sel = selectors.DefaultSelector()

    def _tracer(self):
        self._popen_hd = subprocess.Popen(
            args=self.cmdline,
            shell=True,
            stderr=subprocess.PIPE,
            env={
                'LC_ALL': 'C',
                'http_proxy':
                    '' if not self.proxy else 'http://' + self.proxy,
                'https_proxy':
                    '' if not self.proxy else 'https://' + self.proxy,
            }
        )
        self._sel.register(
            fileobj=self._popen_hd.stderr,
            events=selectors.EVENT_READ,
        )

        parser = self._wget_stderr_parser(self._popen_hd.stderr)
        while self.state == DownloadState.DOWNLOAD:
            self._sel.select(timeout=1)
            try:
                old_progress = self.progress()
                next(parser)
                if self.progress() != old_progress:
                    if self.callback.on_progress_update:
                        self.callback.on_progress_update(self)
            except StopIteration:
                break

            if self._popen_hd.poll() is not None:
                break

        if self._state == DownloadState.STOP:
            if self._popen_hd.poll() is None:  # if process is alive
                self._popen_hd.terminate()
                try:
                    self._popen_hd.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._popen_hd.kill()
                    self._popen_hd.wait()

        else:
            self._popen_hd.wait()
            if self._popen_hd.returncode == 0:
                self._finish_time = time.time()
                self._state = DownloadState.FINISH
                if self.callback.on_finish:
                    self._callback.on_finish(self)
            else:
                self._error_time = time.time()
                self._state = DownloadState.ERROR
                if self.callback.on_error:
                    self._callback.on_error(self)

        self._sel.unregister(self._popen_hd.stderr)

    def _wget_stderr_parser(self, fileobj: _io.BufferedReader):
        """ 解析 wget 输出的生成器. """
        # 头部
        while True:
            line = fileobj.readline().strip()  # type: bytes

            if line.startswith(b'Length: '):
                split = line.split()
                if len(split) >= 1 and split[1].isdigit():
                    self._total_size = int(split[1])

            elif line.startswith(b'Saving to: '):
                break
            yield

        # 点状的进度条
        #      0K .......... .......... .......... .......... ..........  0% 4.45M 14s
        while True:
            line = fileobj.readline().strip()  # type: bytes
            if b'K' not in line:
                continue
            line_2 = line[line.index(b'K')+2:]
            if b'=' in line_2[54:]:  # the end
                break
            line_3 = line_2[:54]  # 50 dots and 4 spaces
            self._downloaded_size += line_3.count(b'.') * 1024
            yield

        # 根据最后输出修正已下载的字节数
        # 上述代码根据每个点代表 1K 来粗略计算已下载的字节数, 实际文件可能并不是
        # 1K 的整数倍.
        lines = fileobj.readlines()
        for line in lines:
            if b'saved ' in line:
                r = re.search(b'saved \[(\d+)/\d+\]', line)
                if r:
                    actual_downloaded_size = r.group(1)
                    if actual_downloaded_size.isdigit():
                        self._downloaded_size = int(actual_downloaded_size)

    def on_start(self) -> None:
        self._start_time = time.time()
        self._tracer_th.start()

    def on_stop(self) -> None:
        self._stop_time = time.time()
        self._tracer_th.join()

    def on_wait(self, timeout: Optional[float]=None) -> None:
        if self._state == DownloadState.DOWNLOAD:
            self._tracer_th.join(timeout=timeout)
            if self._tracer_th.is_alive():
                raise TimeoutError()

    @property
    def cmdline(self):
        r = list()
        r.append('wget')

        for key, value in self._headers:
            r.append('--header=' + shlex.quote(key + ': ' + value))

        if self._output_path:
            r.append('--output-document=' + shlex.quote(str(self.output_path)))

        r.append('--progress=dot')
        r.append(shlex.quote(self.url))
        return ' '.join(r)

    def __del__(self):
        self.stop()
        super().__del__()
