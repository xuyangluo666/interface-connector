"""
重试相关工具函数
"""
from tenacity import retry_if_exception_type
import requests

def retry_if_http_error(exception):
    """判断是否应该重试：HTTP 5xx 或 429（限流）"""
    if isinstance(exception, requests.exceptions.HTTPError):
        status = exception.response.status_code
        return 500 <= status < 600 or status == 429
    return False