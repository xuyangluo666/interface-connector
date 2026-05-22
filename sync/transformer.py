"""
将 A 系统数据结构转换为 B 系统所需结构
"""
from typing import Dict, Any, List
from models.a_models import ACompany
from models.b_models import BCompany, BCompanyInner, CustomField

# 客户级别映射表
ACCOUNT_LEVEL_MAP = {
    "1": "品牌【年综合销售额大于10亿（含）】",
    "2": "KA【综合销售额大于1亿（含）】",
    "3": "基石客户（S）",
    "4": "重点客户（A）",
    "5": "一般客户（B）",
    "6": "其他【综合销售额小于1亿（含）】"
}


def transform_company(a_company: Dict[str, Any]) -> Dict[str, Any]:
    """
    将单个 A 系统公司数据转换为 B 系统公司格式
    
    Args:
        a_company: A 系统原始数据字典，包含 name, address, account_level 等字段
    
    Returns:
        符合 B 系统公司格式的字典
    """
    # 使用 pydantic 模型进行解析与校验
    a_obj = ACompany(**a_company)
    
    # 提取字段
    company_name = a_obj.name
    address = a_obj.address or ""
    account_level = a_obj.account_level or ""
    
    # 客户级别转换
    level_text = ACCOUNT_LEVEL_MAP.get(account_level, account_level)
    
    # 构建 B 系统格式
    b_data = {
        "company": {
            "companyName": company_name,
            "custom_fields": [
                {
                    "key": "field_1",
                    "value": level_text
                },
                {
                    "key": "address",
                    "value": address
                }
            ]
        }
    }
    
    return b_data


def transform_companies(a_companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """批量转换"""
    return [transform_company(item) for item in a_companies]