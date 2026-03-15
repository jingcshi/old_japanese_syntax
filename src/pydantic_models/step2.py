from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict

from ._model_utils import ListDedupeMixin
from .step1 import DocumentMetadata
from ..scoring import AdditionalRoutePropertiesScoringMixin


class FamilySettlementProperties(BaseModel, ListDedupeMixin):
    """
    Properties related to family-based settlement policies.
    Includes information about family members who can settle together,
    required relationships, and required proof documents.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    成员种类: Optional[List[Literal['父母', '退休父母', '岳父母', '配偶', '子女', '未成年子女', '未婚子女', '外祖父母', '同户人员']]] = Field(
        default=None,
        description="允许落户的亲友类型，可多选"
    )
    成员总数: Optional[int] = Field(default=None, description="允许随迁落户的成员总人数，为空表示不限制或政策未说明")


class AdditionalRouteProperties(BaseModel, ListDedupeMixin, AdditionalRoutePropertiesScoringMixin):
    """
    Additional properties for policy routes.
    Includes settlement condition for families, settlement location, and hukou type.
    """
    允许落户的亲友: Optional[FamilySettlementProperties] = Field(
        default=None,
        description="落户条件中允许与本人一同随迁的亲友（如配偶、子女等），不是可以投靠的对象，也不包括在落户要求中的身份（如学生、工作人员）"
    )
    允许落户地点: Optional[List[Literal['居住地', '居住地社区', '学校', '工作地', '人才交流中心', '挂靠亲友']]] = Field(
        default=None,
        description="可多选。如允许落户地点与所属政策渠道的适用地区相同，则忽略此项"
    )
    允许落户户口类别: Optional[List[Literal['常住户口', '学校集体户口', '单位集体户口', '社区集体户口', '人才交流中心集体户口']]] = Field(
        default=None,
        description="可多选"
    )


class RawPolicyRoute(BaseModel):
    """
    Step 2/2.5: Independent settlement requirement (partially organized).

    Represents a single independent condition where meeting all requirements allows settlement.
    This is an intermediate format before full DNF categorization. The document has been dissected into a disjunction of independent routes.
    However, each route is still in free-text form without further breakdown into conjunctions of requirements.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    适用地区: str = Field(default="", description="该落户渠道适用的地区，如无具体说明则默认为全市")
    落户要求: str = Field(default="", description="申请人落户的具体要求，申请者满足其中所有的要求才视作满足此渠道")
    额外政策属性: Optional[AdditionalRouteProperties] = Field(
        default=None,
        description="落户渠道中可能包含的额外属性，如允许落户的亲友、允许落户地点、允许落户户口类别等"
    )

    # @model_validator(mode='after')
    # def check_nonempty_requirement(self) -> 'RawPolicyRoute':
    #     """Ensure at least one requirement is provided (empty conjunction not allowed)"""
    #     if len(self.落户要求.strip()) == 0:
    #         raise ValueError("Policy route must have at least one requirement (empty conjunction represents infinitely relaxed policy)")
    #     return self


class DisjunctivePolicyList(BaseModel, ListDedupeMixin):
    """Collection of partially organized requirements."""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[RawPolicyRoute] = Field(
        default_factory=list,
        description="每个落户渠道独立描述一个允许申请人落户的所有具体要求，申请者满足其中所有要求才视作满足此渠道"
    )

    def is_empty(self) -> bool:
        """Check if there are no settlement routes and no definitions"""
        return len(self.落户渠道) == 0

    def count_routes(self) -> int:
        """Count the number of independent settlement routes"""
        return len(self.落户渠道)


class BasePartialPolicyDocument(BaseModel, ListDedupeMixin):
    """Step 2/2.5 output document with file metadata and partially organized requirements"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: DocumentMetadata = Field(default_factory=DocumentMetadata)
    相关定义: List[str] = Field(
        default_factory=list,
        description='文件中与落户政策相关名词（如"合法稳定住所"，"合法稳定就业"）的定义和解释。'
    )
    落户政策: DisjunctivePolicyList = Field(default_factory=DisjunctivePolicyList, description="将落户政策拆分为若干并列的渠道，申请者满足任意一渠道中的所有要求即可落户")

    def is_empty(self) -> bool:
        """Check if the extracted hukou-related content is empty"""
        return self.落户政策.is_empty()


class PartialPolicyDocument(BasePartialPolicyDocument): 
    """Step 2/2.5 output document with file metadata and partially organized requirements"""


class PartialPolicyDocumentWithRawText(BasePartialPolicyDocument):
    """Step 2.5 input document with file metadata, partially organized requirements, and raw text for validation"""
    原文文本: str = Field(
        default="",
        description="摘录后的政策原文，用于参考和验证"
    )

    def is_empty(self) -> bool:
        """Check if all of the original text and extracted content are empty"""
        return self.原文文本 == "" and self.落户政策.is_empty()
