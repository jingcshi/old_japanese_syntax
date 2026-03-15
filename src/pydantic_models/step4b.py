import json
from typing import List, Literal, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

from ._model_utils import ListDedupeMixin, DuplicateCategoryError
from .step2 import AdditionalRouteProperties
from .step4 import PolicyRegion, PolicyRoute4, PolicyDNF4


class AtomicRequirement4B(BaseModel):
    """Style B: Atomic requirement with category label"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    分类: Literal["年龄性别", "原有户籍", "住房居住", "就业", "投资",
                "纳税", "学历", "职业资格", "社保", "其他"] = Field(default="其他")
    要求: str = Field(default="")


class PolicyRoute4B(BaseModel, ListDedupeMixin):
    """
    Step 4 variant of PolicyRouteB where region is modelled as a structured object.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    适用区域: PolicyRegion = Field(default_factory=PolicyRegion)
    落户要求: List[AtomicRequirement4B] = Field(default_factory=list, description="该落户渠道中包含的具体要求（按照给定分类记录）。申请者满足其中所有的具体要求才视作满足此渠道")
    额外政策属性: Optional[AdditionalRouteProperties] = Field(
        default=None,
        description="落户渠道中可能包含的额外属性，如允许落户的亲友、允许落户地点、允许落户户口类别等"
    )

    @model_validator(mode='wrap')
    @classmethod
    def validate_unique_categories(cls, values: Any, handler: Any) -> 'PolicyRoute4B':
        """Ensure all requirement categories are unique within this policy.

        Uses wrap mode to access raw input and attach it to ConversationRetryError.
        """
        # Get raw JSON string for error reporting
        raw_input_str = None
        if isinstance(values, dict):
            try:
                raw_input_str = json.dumps(values, ensure_ascii=False)
            except:
                raw_input_str = str(values)

        # Call the default validation handler
        instance = handler(values)

        # Now validate the parsed instance
        if instance.落户要求:
            categories = [req.分类 for req in instance.落户要求]
            duplicates = [cat for cat in set(categories) if categories.count(cat) > 1]

            if duplicates:
                raise DuplicateCategoryError(
                    f"Duplicate 落户要求分类 found: {duplicates}. \nEach 落户要求分类 must appear at most once per 落户渠道.",
                    raw_input=raw_input_str
                )

        return instance

    # @model_validator(mode='after')
    # def check_at_least_one_requirement(self) -> 'PolicyRouteB':
    #     """Ensure at least one requirement is provided (empty conjunction not allowed)"""
    #     if len(self.落户要求) == 0:
    #         raise ValueError("Policy route must have at least one requirement (empty conjunction represents infinitely relaxed policy)")
    #     return self

    def is_empty(self) -> bool:
        """Check if there are no requirements in this route"""
        return len(self.落户要求) == 0

    def count_requirements(self) -> int:
        """Count the number of requirements in this route"""
        return len(self.落户要求)
    
    def convert_to_unified(self) -> PolicyRoute4:
        """Convert Style B route to unified PolicyRoute"""
        # Convert list of atomic requirements to dictionary
        requirements = {req.分类: req.要求 for req in self.落户要求}

        return PolicyRoute4(
            适用区域=self.适用区域,
            落户要求=requirements,
            额外政策属性=self.额外政策属性
        )


class PolicyDNF4B(BaseModel, ListDedupeMixin):
    """
    PolicyDNF with region properties.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[PolicyRoute4B] = Field(
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
