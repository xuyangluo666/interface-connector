from pydantic import BaseModel, Field
from typing import List, Optional


class CustomField(BaseModel):
    """自定义字段模型"""
    key: str
    value: str


class BCompanyInner(BaseModel):
    """B 系统公司内部对象"""
    companyName: str = Field(..., alias="companyName")
    custom_fields: List[CustomField] = Field(..., alias="custom_fields")


class BCompany(BaseModel):
    """B 系统公司数据模型（符合 PUT 请求体格式）"""
    company: BCompanyInner

    model_config = {
        "populate_by_name": True
    }