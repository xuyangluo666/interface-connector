"""
B 系统数据加载模块
基于用户提供的 POST 请求示例实现
"""
import requests
from typing import Dict, Any, Optional, List
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from utils.retry import retry_if_http_error
from sync.config import settings


class BLoader:
    """B 系统数据加载器"""

    def __init__(self):
        self.base_url = settings.b_system_base_url
        self.authorization = settings.b_system_authorization
        self.cookie = settings.b_system_cookie
        self.session = requests.Session()
        headers = {
            'Authorization': self.authorization,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        if self.cookie:
            headers['Cookie'] = self.cookie
        self.session.headers.update(headers)
        logger.info(f"B 系统加载器初始化完成: base_url={self.base_url}")

    def _log_request_details(self, url: str, payload: Dict[str, Any], method: str = "POST"):
        """记录请求详细信息用于调试（隐藏敏感信息）"""
        logger.debug(f"请求方法: {method}")
        logger.debug(f"请求 URL: {url}")
        
        # 隐藏敏感头部信息
        headers = dict(self.session.headers)
        if 'Authorization' in headers:
            headers['Authorization'] = '***'
        if 'Cookie' in headers:
            headers['Cookie'] = '***'
        logger.debug(f"请求头部: {headers}")
        
        logger.debug(f"请求体: {payload}")

    def _log_response_details(self, response: requests.Response):
        """记录响应详细信息用于调试"""
        logger.debug(f"响应状态码: {response.status_code}")
        logger.debug(f"响应头部: {dict(response.headers)}")
        try:
            logger.debug(f"响应内容: {response.text[:500]}")
        except:
            logger.debug(f"响应内容: 无法解析")

    @retry(
        retry=retry_if_http_error,
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def search_company_by_name(self, company_name: str) -> Optional[str]:
        """
        根据公司名称查询 B 系统中的公司，返回 uId
        
        Args:
            company_name: 公司名称
            
        Returns:
            公司的 uId，如果未找到返回 None
        """
        url = f"{self.base_url}/api/v1/companies/search.json?query=companyName:{company_name}"
        
        logger.info(f"查询 B 系统公司: companyName={company_name}")
        self._log_request_details(url, {}, method="GET")
        
        try:
            response = self.session.get(url, timeout=30)
            self._log_response_details(response)
            response.raise_for_status()
            result = response.json()
            
            results = result.get("results", [])
            if results:
                u_id = results[0].get("uId")
                logger.info(f"查询到公司: companyName={company_name}, uId={u_id}")
                return u_id
            else:
                logger.info(f"未查询到公司: companyName={company_name}")
                return None
                
        except requests.exceptions.HTTPError as e:
            logger.error(f"B 系统查询错误: {e}")
            raise

    @retry(
        retry=retry_if_http_error,
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def create_company(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建单个公司数据到 B 系统（使用 POST 方法）

        Args:
            company_data: B 系统期望的公司字段，包含 companyName, address, custom_fields

        Returns:
            B 系统返回的 JSON 响应
        """
        url = f"{self.base_url}/api/v1/companies.json"
        
        # 构建 payload - 参考用户提供的格式
        payload = {
            "company": {
                "companyName": company_data.get("companyName", ""),
                "address": company_data.get("address", ""),
                "custom_fields": company_data.get("custom_fields", [])
            }
        }

        # 记录请求详情
        company_name = payload['company']['companyName']
        logger.info(f"创建公司到 B 系统: companyName={company_name}")
        self._log_request_details(url, payload)

        try:
            response = self.session.post(url, json=payload, timeout=30)
            self._log_response_details(response)
            
            # 先尝试解析响应，无论状态码如何
            try:
                result = response.json()
            except:
                result = {}
            
            # 检查是否是公司已存在的错误（status=110026）
            if result.get("status") == "110026" and "already exists" in result.get("errorMsg", ""):
                company_id = result.get("data", {}).get("companyId")
                logger.info(f"公司已存在: {company_name}, 使用已存在的 companyId: {company_id}")
                return {"company": {"uId": company_id}}
            
            # 检查其他业务错误
            if "errorMsg" in result:
                logger.error(f"B 系统业务错误: {result.get('errorMsg')}")
                raise Exception(f"B 系统错误: {result.get('errorMsg')}")
            
            # 如果是 HTTP 错误，尝试获取响应内容
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # 尝试获取响应内容用于调试
                try:
                    error_body = response.text[:500]
                    logger.error(f"B 系统返回错误: {e}, 响应内容: {error_body}")
                except:
                    logger.error(f"B 系统返回错误: {e}")
                raise
            
            logger.info(f"B 系统创建成功")
            return result
        except requests.exceptions.HTTPError as e:
            logger.error(f"B 系统返回错误: {e}")
            raise

    def create_companies_batch(self, companies: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量创建公司数据到 B 系统，并查询返回的 uId

        Args:
            companies: 字典，key=company_id, value=company_data（包含 companyName, address, custom_fields）

        Returns:
            统计信息: {"total": n, "success": n, "failed": [], "created": []}
            created 列表包含 {"company_id": "...", "b_system_uId": "...", "companyName": "..."}
        """
        stats = {
            "total": len(companies), 
            "success": 0, 
            "failed": [],
            "created": []  # 记录创建成功的公司及其 B 系统 uId
        }
        logger.info(f"开始批量创建公司到 B 系统: 共 {stats['total']} 条数据")
        
        for company_id, data in companies.items():
            try:
                # 从 transformer 返回的格式中提取数据
                # transformer 返回的格式: {"company": {"companyName": "...", "custom_fields": [...]}}
                company_info = data.get("company", data)
                
                # 提取 address（如果在 custom_fields 中）
                address = ""
                custom_fields = company_info.get("custom_fields", [])
                for field in custom_fields:
                    if field.get("key") == "address":
                        address = field.get("value", "")
                        break
                
                # 构建创建请求的数据
                create_data = {
                    "companyName": company_info.get("companyName", ""),
                    "address": address,
                    "custom_fields": [f for f in custom_fields if f.get("key") != "address"]
                }
                
                # 创建公司
                create_result = self.create_company(create_data)
                
                # 获取创建后的 uId
                company_name = create_data["companyName"]
                u_id = create_result.get("company", {}).get("uId")
                
                # 如果创建结果中没有 uId，尝试通过查询获取
                if not u_id:
                    u_id = self.search_company_by_name(company_name)
                
                stats["success"] += 1
                stats["created"].append({
                    "company_id": company_id,
                    "b_system_uId": u_id,
                    "companyName": company_name
                })
                logger.info(f"第 {stats['success']}/{stats['total']} 条创建成功: companyName={company_name}, uId={u_id}")
                
            except Exception as e:
                logger.error(f"创建 company_id={company_id} 失败: {e}")
                stats["failed"].append({"company_id": company_id, "error": str(e)})
        
        return stats

    @retry(
        retry=retry_if_http_error,
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def search_business_opportunities(self, owner: str) -> List[str]:
        """
        查询公司已有的商机编号
        
        Args:
            owner: 公司 ID（B 系统中的 uId）
            
        Returns:
            已存在的商机编号列表（field_3 值）
        """
        url = f"{self.base_url}/api/v1/forms/asset_form/9154740/search.json?query=owner:{owner} ownerType:company&page=1&per_page=100"
        
        logger.info(f"查询公司已有的商机编号: owner={owner}")
        logger.info(f"请求 URL: {url}")
        self._log_request_details(url, {}, method="GET")
        
        try:
            response = self.session.get(url, timeout=30)
            self._log_response_details(response)
            response.raise_for_status()
            result = response.json()
            
            existing_codes = []
            datas = result.get("asset_table", {}).get("datas", [])
            for item in datas:
                field_3 = item.get("field_3")
                if field_3:
                    existing_codes.append(field_3)
            
            logger.info(f"已存在的商机编号: {existing_codes}")
            
            # 打印每个已存在的商机编号详情
            if existing_codes:
                logger.info("B 系统已存在的商机编号列表:")
                for idx, code in enumerate(existing_codes, 1):
                    logger.info(f"  {idx}. {code}")
            
            return existing_codes
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"B 系统查询商机编号错误: {e}")
            raise

    @retry(
        retry=retry_if_http_error,
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def create_business_opportunities(self, company_uId: str, opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量写入商机编号到 B 系统（自动去重）
        
        Args:
            company_uId: B 系统中的公司 ID（用于查询已存在的商机）
            opportunities: 商机列表，包含 name（商机名称）和 field_4dH68__c（商机编号）
            
        Returns:
            统计信息: {"total": n, "created": n, "skipped": n}
        """
        # 先查询已存在的商机编号
        existing_codes = self.search_business_opportunities(company_uId)
        
        # 过滤已存在的商机
        new_opportunities = []
        skipped_count = 0
        for opp in opportunities:
            code = opp.get("field_4dH68__c")
            if code and code not in existing_codes:
                new_opportunities.append(opp)
            elif code:
                logger.info(f"商机编号已存在，跳过: {code}")
                skipped_count += 1
        
        if not new_opportunities:
            logger.info("没有新的商机编号需要写入")
            return {"total": len(opportunities), "created": 0, "skipped": len(opportunities)}
        
        url = f"{self.base_url}/api/v1/forms/asset_form/9154740.json"
        
        # 构建请求体
        items_data = []
        for opp in new_opportunities:
            items_data.append({
                "owner": company_uId,
                "ownerType": "company",
                "field_3": opp.get("field_4dH68__c", ""),
                "field_4": opp.get("name", "")
            })
        
        payload = {
            "items_data": items_data
        }
        
        logger.info(f"写入商机编号: company_uId={company_uId}, 商机数量={len(items_data)}（{skipped_count} 条已存在跳过）")
        self._log_request_details(url, payload)
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            self._log_response_details(response)
            
            try:
                result = response.json()
            except:
                result = {}
            
            if "errorMsg" in result:
                logger.error(f"B 系统商机写入错误: {result.get('errorMsg')}")
                raise Exception(f"B 系统错误: {result.get('errorMsg')}")
            
            response.raise_for_status()
            logger.info(f"商机编号写入成功")
            return {
                "total": len(opportunities),
                "created": len(new_opportunities),
                "skipped": len(opportunities) - len(new_opportunities)
            }
        except requests.exceptions.HTTPError as e:
            logger.error(f"B 系统商机写入错误: {e}")
            raise