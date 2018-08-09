from enum import unique, Enum


@unique
class HeaderName(Enum):
    Cookie = 'Cookie'
    UserAgent = 'User-Agent'
    Accept = 'Accept'
    Referer = 'Referer'
    AcceptEncoding = 'Accept-Encoding'
