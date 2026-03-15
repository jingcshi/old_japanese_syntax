from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field, ConfigDict

from ._model_utils import ListDedupeMixin
from .step1 import DocumentMetadata
from .step2 import AdditionalRouteProperties


class PolicyRoute3(BaseModel):
    """
    Base model for independent settlement route (conjunction of requirements).
    This model is missing the field for policy region, which has different implementations in step 3 / 3.5 and step 4 / 4.5.

    Represents a single route to obtaining hukou. All requirements in this route
    must be satisfied (AND relationship).
    Requirements are organized by category
    in a dictionary where each category can appear at most once.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    适用地区: str = Field(default="", description="该落户渠道适用的地区，如无具体说明则默认为全市")
    落户要求: Dict[Literal["年龄性别", "原有户籍", "住房居住", "就业", "投资", "纳税", "学历", "职业资格", "社保", "亲属投靠", "奖励荣誉", "其他"], str] = Field(
        default_factory=dict,
        description="该落户渠道中包含的具体要求（按照给定分类记录）。申请者满足其中所有的具体要求才视作满足此渠道。每个分类至多出现一次"
    )
    额外政策属性: Optional[AdditionalRouteProperties] = Field(
        default=None,
        description="落户渠道中可能包含的额外属性，如允许落户的亲友、允许落户地点、允许落户户口类别等"
    )

    def is_empty(self) -> bool:
        """Check if there are no requirements in this route"""
        return len(self.落户要求) == 0

    def count_requirements(self) -> int:
        """Count the number of requirements in this route"""
        return len(self.落户要求)
    
    # @model_validator(mode='after')
    # def check_at_least_one_requirement(self) -> 'PolicyRoute':
    #     """Ensure at least one requirement is provided (empty conjunction not allowed)"""
    #     if len(self.落户要求) == 0:
    #         raise ValueError("Policy route must have at least one requirement (empty conjunction represents infinitely relaxed policy)")
    #     return self
    

class PolicyDNF3(BaseModel, ListDedupeMixin):
    """
    Unified policy in DNF (disjunctive normal form).

    Contains multiple policy routes. Fulfillment of ANY route grants hukou (OR relationship).
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[PolicyRoute3] = Field(
        default_factory=list,
        description="将落户政策拆分为若干并列的渠道，申请者满足任意一渠道中的所有要求即可落户"
    )

    def is_empty(self) -> bool:
        """Check if there are no settlement routes"""
        return len(self.落户渠道) == 0

    def count_routes(self) -> int:
        """Count the number of independent settlement routes"""
        return len(self.落户渠道)

    def count_total_requirements(self) -> int:
        """Get the total number of requirements across all routes"""
        return sum(len(route.落户要求) for route in self.落户渠道)
    

class BasePolicyDocument3(BaseModel, ListDedupeMixin):
    """Base model for complete policy document with metadata and DNF routes"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: DocumentMetadata = Field(default_factory=DocumentMetadata)
    相关定义: List[str] = Field(
        default_factory=list,
        description='文件中与落户政策相关名词（如"合法稳定住所"，"合法稳定就业"）的定义和解释。'
    )
    政策: PolicyDNF3 = Field(default_factory=PolicyDNF3, description="主析取范式格式的落户政策")

    def is_empty(self) -> bool:
        """Check if the policy has no settlement routes"""
        return self.政策.is_empty()


class PolicyDocument3(BasePolicyDocument3):
    """Complete policy document with metadata and DNF routes"""
    pass


class PolicyDocumentWithRawText3(BasePolicyDocument3):
    """PolicyDocument with file metadata, policy DNFs, and raw text for validation"""
    原文文本: str = Field(
        default="",
        description="摘录后的政策原文，用于参考和验证"
    )

    def is_empty(self) -> bool:
        """Check if all of the original text and extracted content are empty"""
        return self.原文文本 == "" and self.政策.is_empty()
