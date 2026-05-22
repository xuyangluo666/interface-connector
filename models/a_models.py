from pydantic import BaseModel, Field
from typing import List, Optional, Any


class ACompany(BaseModel):
    """A 系统公司数据模型（纷享销客 CRM）"""
    id: str = Field(..., alias="_id")  # 客户唯一标识
    name: str = Field(..., alias="name")  # 公司名称
    address: Optional[str] = Field(None, alias="address")  # 公司地址
    account_level: Optional[str] = Field(None, alias="account_level")  # 客户级别（1-6）
    owner: Optional[List[str]] = Field(default_factory=list, alias="owner")  # 负责人ID列表
    data_own_department: Optional[List[str]] = Field(default_factory=list, alias="data_own_department")  # 所属部门ID列表
    商机信息: Optional[List[Any]] = Field(default_factory=list, alias="商机信息")  # 商机信息列表

    model_config = {
        "populate_by_name": True,
        "extra": "allow"  # 允许额外字段
    }


class OpportunityInfo(BaseModel):
    """商机信息模型"""
    name: Optional[str] = None  # 商机名称
    field_4dH68__c: Optional[str] = None  # 商机编号

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }