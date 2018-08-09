#!/usr/bin/env python3
from sys import stdout

from download_wrapper import DownloadWrapper, wrapper_factory
from download_wrapper.helper import pretty

rich = wrapper_factory()
rich.output_path = 'test_output'
rich.url = 'https://dldir1.qq.com/qqfile/qq/QQ9.0.4/23786/QQ9.0.4.exe'


def cbk_stall(_: DownloadWrapper):
    print('\r' + ' ' * 79 + '\r', end='')
    print('Stalled >.<', end='')
    stdout.flush()


def cbk_progress_update(wrapper: DownloadWrapper):
    print('\r' + ' ' * 79 + '\r', end='')
    print('Downloading...  progress: {}%  current speed: {}'.format(
        wrapper.progress(), pretty(wrapper.instant_speed(), is_speed=True),
    ), end='')
    stdout.flush()


rich.callback.register_progress_update(cbk_progress_update)
rich.callback.register_stall(cbk_stall)

print(rich.cmdline)
rich.start()

rich.wait()

print('\nFinished!')
print(rich.state)
print(pretty(rich.average_speed(), is_speed=True))
