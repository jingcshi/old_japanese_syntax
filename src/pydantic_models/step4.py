from typing import List, Literal, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict

from ._model_utils import ListDedupeMixin
from .step1 import DocumentMetadata
from .step2 import AdditionalRouteProperties


class PolicyRegion(BaseModel, ListDedupeMixin):
    """
    Properties related to the applicable regions for settlement policies.
    Includes city and subdivisions within the city.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    可落户城市: List[str] = Field(default_factory=list, description="该落户渠道适用的城市，对于省级文件发表的政策可多选。原文未详细说明的默认为文件所属城市或所属省辖的全部城市（记作“全省”）")
    可落户区划: List[Literal['全市', '市区', '开发区', '县区', '农村']] = Field(
        default_factory=list,
        description="该落户渠道适用的“适用城市”下辖区划，可多选。原文未详细说明的默认为全市。市区包括市辖区、开发区（不包括县区的城市），县区包括所有县级区划（县级市市区、县人民政府驻地镇和其他建制镇、小城镇），农村指农村地区、农业户口。"
    )

    
class PolicyRoute4(BaseModel):
    """
    Base model for independent settlement route (conjunction of requirements).
    This model is missing the field for policy region, which has different implementations in step 3 / 3.5 and step 4 / 4.5.

    Represents a single route to obtaining hukou. All requirements in this route
    must be satisfied (AND relationship).
    Requirements are organized by category
    in a dictionary where each category can appear at most once.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    适用区域: PolicyRegion = Field(default_factory=PolicyRegion)
    落户要求: Dict[Literal["年龄性别", "原有户籍", "住房居住", "就业", "投资", "纳税", "学历", "职业资格", "社保", "其他"], str] = Field(
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

class PolicyDNF4(BaseModel, ListDedupeMixin):
    """
    PolicyDNF with region properties.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[PolicyRoute4] = Field(
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
    

class BasePolicyDocument4(BaseModel, ListDedupeMixin):
    """
    Base class for policy documents with region properties.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: DocumentMetadata = Field(default_factory=DocumentMetadata)
    相关定义: List[str] = Field(
        default_factory=list,
        description='文件中与落户政策相关名词（如"合法稳定住所"，"合法稳定就业"）的定义和解释。'
    )
    政策: PolicyDNF4 = Field(default_factory=PolicyDNF4, description="主析取范式格式的落户政策")

    def is_empty(self) -> bool:
        """Check if the policy has no settlement routes"""
        return self.政策.is_empty()
    

class PolicyDocument4(BasePolicyDocument4):
    """
    PolicyDocument with region properties.
    """
    pass


class PolicyDocumentWithRawText4(BasePolicyDocument4):
    """
    PolicyDocumentWithRawText with region properties
    """
    原文文本: str = Field(
        default="",
        description="摘录后的政策原文，用于参考和验证"
    )

    def is_empty(self) -> bool:
        """Check if all of the original text and extracted content are empty"""
        return self.原文文本 == "" and self.政策.is_empty()
    

class PolicyDNFCrossCheck(BaseModel, ListDedupeMixin):
    """Step 4.5 input document with DNF policies from both step 4a and 4b for cross-validation"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: DocumentMetadata = Field(default_factory=DocumentMetadata)
    相关定义: List[str] = Field(
        default_factory=list,
        description='文件中与落户政策相关名词（如"合法稳定住所"，"合法稳定就业"）的定义和解释。'
    )
    原文文本: str = Field(
        default="",
        description="摘录后的政策原文，用于参考和验证"
    )
    版本A: PolicyDNF4 = Field(default_factory=PolicyDNF4)
    版本B: PolicyDNF4 = Field(default_factory=PolicyDNF4)

    def is_empty(self) -> bool:
        """Check if all of the original text, version A, and version B are empty"""
        return self.原文文本 == "" and self.版本A.is_empty() and self.版本B.is_empty()
