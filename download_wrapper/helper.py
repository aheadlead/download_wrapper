from typing import Union

_SCALE = 1024.0


def _mutiply(value):
    return value * _SCALE


def _divide_by(value):
    return value / _SCALE


bytes_to_kilobytes = _divide_by
kilobytes_to_megabytes = _divide_by
megabytes_to_gigabytes = _divide_by
gigabytes_to_terabytes = _divide_by

terabytes_to_gigabytes = _mutiply
gigabytes_to_megabytes = _mutiply
megabytes_to_kilobytes = _mutiply
kilobytes_to_bytes = _mutiply


def pretty(value: Union[int, float], is_speed: bool=False):
    ret = value
    suffix = 'B'

    if ret > _SCALE:
        ret = bytes_to_kilobytes(ret)
        suffix = 'KiB'

    if ret > _SCALE:
        ret = kilobytes_to_megabytes(ret)
        suffix = 'MiB'

    if ret > _SCALE:
        ret = megabytes_to_gigabytes(ret)
        suffix = 'GiB'

    if ret > _SCALE:
        ret = gigabytes_to_terabytes(ret)
        suffix = 'TiB'

    if is_speed:
        suffix += '/s'

    return '{:.2f}'.format(ret) + suffix
