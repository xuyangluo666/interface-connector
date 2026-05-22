"""
A 系统数据提取模块（纷享销客）
根据纷享销客接口文档实现具体调用逻辑
"""
from typing import List, Dict, Any, Optional
from loguru import logger
import requests
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from utils.retry import retry_if_http_error
from sync.config import settings
import time


class AExtractor:
    """A 系统数据提取器（纷享销客）"""

    def __init__(self):
        self.base_url = settings.a_system_base_url
        self.app_id = settings.a_system_app_id
        self.permanent_code = settings.a_system_permanent_code
        self.app_secret = settings.a_system_app_secret
        self.default_mobile = settings.a_system_default_mobile
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })
        self.corp_access_token = None
        self.corp_id = None
        self.token_expire_time = 0
        self.open_user_id = None
        self.user_id_cache: Dict[str, str] = {}

    def _get_corp_access_token(self) -> str:
        """
        获取企业访问令牌
        API: POST /cgi/corpAccessToken/get/V2
        """
        url = f"{self.base_url}/cgi/corpAccessToken/get/V2"
        payload = json.dumps({
            "appId": self.app_id,
            "permanentCode": self.permanent_code,
            "appSecret": self.app_secret
        })

        logger.info("获取纷享销客 corpAccessToken...")
        response = requests.post(url, headers={"Content-Type": "application/json"}, data=payload, timeout=30)
        response.raise_for_status()
        
        # 输出完整响应以便调试
        logger.debug(f"响应状态码: {response.status_code}")
        logger.debug(f"响应内容: {response.text}")
        
        try:
            result = response.json()
        except ValueError as e:
            raise Exception(f"响应不是有效的 JSON: {response.text[:200]}")

        error_code = result.get("errorCode", result.get("code"))
        if error_code != 0:
            message = result.get("errorMessage", result.get("message", result.get("msg", "未知错误")))
            raise Exception(f"获取 token 失败 (code={error_code}): {message}")

        # 纷享销客 API 返回的数据直接在根级别，不在 data 字段中
        self.corp_access_token = result.get("corpAccessToken", result.get("data", {}).get("corpAccessToken"))
        self.corp_id = result.get("corpId", result.get("data", {}).get("corpId"))
        expires_in = result.get("expiresIn", result.get("data", {}).get("expiresIn"))
        self.token_expire_time = time.time() + expires_in - 60  # 提前1分钟过期

        logger.info(f"获取 token 成功，corpId: ***，有效期: {expires_in} 秒")
        return self.corp_access_token

    def _ensure_token_valid(self):
        """确保 token 有效，过期则重新获取"""
        if not self.corp_access_token or time.time() >= self.token_expire_time:
            self._get_corp_access_token()

    @retry(
        retry=retry_if_http_error,
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """带重试的请求方法，自动处理 token"""
        self._ensure_token_valid()

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "accessToken": self.corp_access_token
        }

        logger.debug(f"请求 A 系统: {method} {url}")
        resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_user_id_by_mobile(self, mobile: str, use_cache: bool = True) -> Optional[str]:
        """
        通过手机号查询用户ID
        API: POST /cgi/user/getByMobile

        Args:
            mobile: 手机号
            use_cache: 是否使用缓存，默认为 True

        Returns:
            openUserId，如果查询失败返回 None
        """
        # 检查缓存
        if use_cache and mobile in self.user_id_cache:
            logger.debug(f"从缓存获取用户ID，手机号: {mobile}")
            return self.user_id_cache[mobile]

        self._ensure_token_valid()

        url = f"{self.base_url}/cgi/user/getByMobile"
        payload = json.dumps({
            "corpAccessToken": self.corp_access_token,
            "corpId": self.corp_id,
            "mobile": mobile
        })

        logger.info(f"通过手机号查询用户ID: ***")
        response = requests.post(url, headers={"Content-Type": "application/json"}, data=payload, timeout=30)
        response.raise_for_status()
        
        # 输出响应以便调试
        logger.debug(f"响应状态码: {response.status_code}")
        logger.debug(f"响应内容: {response.text}")
        
        result = response.json()

        # 纷享销客 API 使用 errorCode 而不是 code
        error_code = result.get("errorCode", result.get("code"))
        if error_code != 0:
            message = result.get("errorMessage", result.get("message", "未知错误"))
            logger.warning(f"查询用户ID失败，手机号: {mobile}，错误: {message}")
            return None

        # 纷享销客 API 返回的数据在 empList 数组中
        emp_list = result.get("empList", [])
        if emp_list:
            open_user_id = emp_list[0].get("openUserId")
        else:
            open_user_id = result.get("openUserId", result.get("data", {}).get("openUserId"))
        
        # 保存到实例属性（用于单用户场景）
        self.open_user_id = open_user_id
        
        # 缓存到字典（用于多用户场景）
        self.user_id_cache[mobile] = open_user_id
        
        logger.info(f"查询用户ID成功，手机号: ***，openUserId: ***")
        return open_user_id

    def get_crm_data(self, 
                      data_object_api_name: str = "AccountObj",
                      offset: int = 0, 
                      limit: int = 100,
                      start_time: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        查询 CRM 数据
        API: POST /cgi/crm/v2/data/query

        Args:
            data_object_api_name: 数据对象 API 名称，如 "AccountObj"（客户）、"ContactsObj"（联系人）等
            offset: 分页偏移量，从 0 开始
            limit: 每页数量，最大 100
            start_time: 查询起始时间（毫秒时间戳），默认当天 00:00:00

        Returns:
            数据列表
        """
        self._ensure_token_valid()

        if not self.open_user_id:
            logger.error("未设置 openUserId，请先调用 get_user_id_by_mobile()")
            return []

        # 默认使用当天 00:00:00 的毫秒时间戳
        if start_time is None:
            today = time.localtime()
            start_time = int(time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, 0)) * 1000)

        url = f"{self.base_url}/cgi/crm/v2/data/query"
        payload = json.dumps({
            "corpAccessToken": self.corp_access_token,
            "currentOpenUserId": self.open_user_id,
            "corpId": self.corp_id,
            "data": {
                "find_explicit_total_num": True,
                "search_query_info": {
                    "offset": offset,
                    "limit": limit,
                    "orders": [
                        {
                            "fieldName": "create_time",
                            "isAsc": True
                        }
                    ],
                    "fieldProjection": [
                        "_id",
                        "name",
                        "owner",
                        "account_level",
                        "address",
                        "data_own_department"
                    ],
                    "filters": [
                        {
                            "operator": "GT",
                            "field_name": "create_time",
                            "field_values":[start_time]
                            #以下测试勿删
                            # "operator": "EQ",
                            # "field_name": "name",
                            # "field_values": ["云南云电同方科技有限公司"]
                        }
                    ]
                },
                "dataObjectApiName": data_object_api_name
            }
        })

        logger.info(f"查询 CRM 数据: {data_object_api_name}, offset={offset}, limit={limit}, start_time={start_time}")
        response = requests.post(url, headers={"Content-Type": "application/json"}, data=payload, timeout=60)
        response.raise_for_status()
        
        # 输出响应以便调试
        logger.debug(f"响应状态码: {response.status_code}")
        logger.debug(f"响应内容: {response.text}")
        
        result = response.json()

        # 纷享销客 API 使用 errorCode 而不是 code
        error_code = result.get("errorCode", result.get("code"))
        if error_code != 0:
            message = result.get("errorMessage", result.get("message", "未知错误"))
            logger.error(f"查询 CRM 数据失败 (code={error_code}): {message}")
            return []

        # 纷享销客 API 返回的数据在 dataList 字段中
        return result.get("data", {}).get("dataList", result.get("data", {}).get("items", []))


    def get_opportunity_by_account_id(self, account_id: str) -> List[Dict[str, Any]]:
        """
        根据客户ID查询商机信息
        API: POST /cgi/crm/v2/data/query

        Args:
            account_id: 客户ID（_id字段）

        Returns:
            商机列表，包含 name 和 field_4dH68__c（商机编号）等字段
        """
        self._ensure_token_valid()

        if not self.open_user_id:
            logger.error("未设置 openUserId，请先调用 get_user_id_by_mobile()")
            return []

        url = f"{self.base_url}/cgi/crm/v2/data/query"
        payload = json.dumps({
            "corpAccessToken": self.corp_access_token,
            "currentOpenUserId": self.open_user_id,
            "corpId": self.corp_id,
            "data": {
                "find_explicit_total_num": True,
                "search_query_info": {
                    "offset": 0,
                    "limit": 100,
                    "orders": [
                        {
                            "fieldName": "create_time",
                            "isAsc": True
                        }
                    ],
                    "fieldProjection": [
                        "name",
                        "field_4dH68__c"
                    ],
                    "filters": [
                        {
                            "operator": "EQ",
                            "field_name": "account_id",
                            "field_values": [account_id]
                        }
                    ]
                },
                "dataObjectApiName": "NewOpportunityObj"
            }
        })

        logger.debug(f"查询商机信息，account_id: {account_id}")
        try:
            response = requests.post(url, headers={"Content-Type": "application/json"}, data=payload, timeout=60)
            response.raise_for_status()
            
            logger.debug(f"商机响应内容: {response.text}")
            result = response.json()

            error_code = result.get("errorCode", result.get("code"))
            if error_code != 0:
                message = result.get("errorMessage", result.get("message", "未知错误"))
                logger.warning(f"查询商机失败 (code={error_code}): {message}")
                return []

            return result.get("data", {}).get("dataList", result.get("data", {}).get("items", []))
        except Exception as e:
            logger.error(f"查询商机异常，account_id: {account_id}，错误: {e}")
            return []

    def get_companies_with_opportunities(self, modified_since: Optional[str] = None, limit: int = 100, query_all: bool = False) -> List[Dict[str, Any]]:
        """
        获取客户数据并关联商机信息

        Args:
            modified_since: 增量时间戳
            limit: 每页数量
            query_all: 是否查询所有数据（不限制时间），默认 False

        Returns:
            客户数据列表，每个客户包含商机信息字段
        """
        # 获取客户数据
        if query_all:
            companies = self.get_crm_data(data_object_api_name="AccountObj", limit=limit, start_time=0)
        else:
            companies = self.get_crm_data(data_object_api_name="AccountObj", limit=limit)
        logger.info(f"获取到 {len(companies)} 条客户数据")

        # 为每个客户查询商机
        for company in companies:
            account_id = company.get("_id")
            if account_id:
                opportunities = self.get_opportunity_by_account_id(account_id)
                company["商机信息"] = opportunities if opportunities else []
            else:
                company["商机信息"] = []

        return companies

    def enrich_with_opportunities(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        为客户数据列表添加商机信息
        
        Args:
            companies: 客户数据列表（必须包含 _id 字段）
            
        Returns:
            添加了商机信息的客户数据列表
        """
        for company in companies:
            account_id = company.get("_id")
            if account_id:
                opportunities = self.get_opportunity_by_account_id(account_id)
                company["商机信息"] = opportunities if opportunities else []
            else:
                company["商机信息"] = []
        
        return companies
