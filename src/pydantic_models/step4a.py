from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from ._model_utils import ListDedupeMixin, clean_string_value
from .step2 import AdditionalRouteProperties
from .step4 import PolicyRegion, PolicyRoute4, PolicyDNF4


class Requirement4A(BaseModel):
    """Requirements with explicit fields for each category"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    年龄性别: Optional[str] = Field(default=None)
    原有户籍: Optional[str] = Field(default=None)
    住房居住: Optional[str] = Field(default=None)
    就业: Optional[str] = Field(default=None)
    投资: Optional[str] = Field(default=None)
    纳税: Optional[str] = Field(default=None)
    学历: Optional[str] = Field(default=None)
    职业资格: Optional[str] = Field(default=None)
    社保: Optional[str] = Field(default=None)
    其他: Optional[str] = Field(default=None)

    def clean_placeholder_values(self) -> 'Requirement4A':
        """Remove placeholder values like '无', 'null', etc."""
        for field_name in self.__class__.model_fields.keys():
            value = getattr(self, field_name)
            cleaned = clean_string_value(value)
            # Directly modify __dict__ to avoid triggering validate_assignment
            object.__setattr__(self, field_name, cleaned)
        return self

    # @model_validator(mode='after')
    # def check_at_least_one_requirement(self) -> 'Requirement3A':
    #     """Ensure at least one requirement is provided (empty conjunction not allowed)"""
    #     req_dict = self.model_dump()
    #     if all(value is None or str(value).strip() == "" for value in req_dict.values()):
    #         raise ValueError("Policy route must have at least one requirement (empty conjunction represents infinitely relaxed policy)")
    #     return self


class PolicyRoute4A(BaseModel):
    """Step 4 variant of PolicyRouteA where region is modelled as a structured object."""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    适用区域: PolicyRegion = Field(default_factory=PolicyRegion)
    落户要求: Requirement4A = Field(
        default_factory=Requirement4A,
        description="该落户渠道中包含的具体要求（按照给定分类记录）。申请者满足其中所有的具体要求才视作满足此渠道"
    )
    额外政策属性: Optional[AdditionalRouteProperties] = Field(
        default=None,
        description="落户渠道中可能包含的额外属性，如允许落户的亲友、允许落户地点、允许落户户口类别等"
    )

    def is_empty(self) -> bool:
        """Check if there are no requirements in this route"""
        req_dict = self.落户要求.model_dump()
        return all(value is None or str(value).strip() == "" for value in req_dict.values())

    def count_requirements(self) -> int:
        """Count the number of non-empty requirements in this route"""
        req_dict = self.落户要求.model_dump()
        return sum(1 for value in req_dict.values() if value is not None and str(value).strip() != "")
    
    def convert_to_unified(self) -> PolicyRoute4:
        """Convert Style A route to unified PolicyRoute"""
        # Extract non-None requirements from fixed schema
        requirements = {}
        req_dict = self.落户要求.model_dump()

        for category, value in req_dict.items():
            if value is not None and str(value).strip():
                requirements[category] = value

        return PolicyRoute4(
            适用区域=self.适用区域,
            落户要求=requirements,
            额外政策属性=self.额外政策属性
        )


class PolicyDNF4A(BaseModel, ListDedupeMixin):
    """
    PolicyDNF with region properties.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[PolicyRoute4A] = Field(
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
        return sum(route.count_requirements() for route in self.落户渠道)
    
    def convert_to_unified(self) -> PolicyDNF4:
        """Convert Style A policy document to unified DNF"""
        routes = [route.convert_to_unified() for route in self.落户渠道]
        return PolicyDNF4(落户渠道=routes)
