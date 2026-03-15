import json
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

from ._model_utils import ListDedupeMixin, ResidenceConditionConflictError
from .step1 import DocumentMetadata
from .step2 import AdditionalRouteProperties
from .step4 import PolicyRegion
from ..scoring import (
    AgeAndSexScoringMixin, PreviousHukouScoringMixin,
    HouseAndResidenceScoringMixin, EmploymentScoringMixin,
    InvestmentScoringMixin, TaxScoringMixin,
    EducationScoringMixin, ProfessionalQualificationScoringMixin,
    SocialSecurityScoringMixin, OtherScoringMixin,
    RichRequirementScoringMixin, ClassifiedRouteScoringMixin,
    ClassifiedDNFScoringMixin, ClassifiedDocumentScoringMixin
)


class BaseDetailsModel(BaseModel):
    """Base model for detailed requirement annotations"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    def is_empty(self) -> bool:
        """Check if all fields are None"""
        return all(
            getattr(self, field_name) is None
            for field_name in self.__class__.model_fields.keys()
        )

    def count_sub_requirements(self) -> int:
        """Count the number of non-empty fields (non-empty lists count as one)

        For nested DetailsBaseModel objects, recursively counts their sub-requirements
        instead of counting them as a single field.
        """
        count = 0
        for field_name in self.__class__.model_fields.keys():
            value = getattr(self, field_name)
            if value is not None:
                # If it's a nested DetailsBaseModel, recursively count its sub-requirements
                if isinstance(value, BaseDetailsModel):
                    if not value.is_empty():
                        count += value.count_sub_requirements()
                # For lists, just count as 1 if non-empty
                elif isinstance(value, list):
                    if len(value) > 0:
                        count += 1
                # For other non-list values, count if not empty string, NaN, or zero
                else:
                    if not (
                        (isinstance(value, str) and value.strip() == '') or 
                        (isinstance(value, float) and (value != value) or (value == 0.0)) or # value != value checks for NaN
                        (isinstance(value, int) and value == 0)
                        ):
                        count += 1
        return count


class AgeAndSexDetails(BaseDetailsModel, AgeAndSexScoringMixin):
    最小周岁: Optional[int] = Field(default=None)
    最大周岁: Optional[int] = Field(default=None)
    性别: Optional[Literal['男', '女']] = Field(default=None)
    备注: Optional[str] = Field(default=None)


class PreviousHukouDetails(BaseDetailsModel, PreviousHukouScoringMixin):
    范围: Literal['城市户口','农村户口', '本市农村户口', '本省农村户口', '本市城市户口', '本省城市户口', '本省', '本市', '外省'] = Field(
        ...,
        description="农业户口、进城务工人员记为农村户口；非农业户口、城镇户口记为城市户口"
        )
    备注: Optional[str] = Field(default=None)


class HouseOwnershipDetails(BaseDetailsModel, ListDedupeMixin):
    面积_平米: Optional[int] = Field(default=None)
    人均面积_平米: Optional[int] = Field(default=None)
    金额_万元: Optional[float] = Field(default=None)
    住房额外要求: Optional[List[Literal['该地址无人落户', '取得房产证', '购房合同', '购房发票', '最低面积或最低金额', '无面积金额要求', '具体标准未明确', '其他']]] = Field(
        default=None,
        description='可多选。\'最低面积或最低金额\'指，在原文中提到面积和金额满足其一即可；\'无面积金额要求\'指，任意面积、金额的住房都可以落户；\'具体标准未明确\'指，政策条件提出"有一定要求"、"达到一定标准"的住房，但未给出具体数额或年限；如提出对住房面积、金额均无要求，则无需记录在额外要求中。如有\'其他\'，需在备注中说明'
        )
    备注: Optional[str] = Field(default=None)


class HouseRentalDetails(BaseDetailsModel, ListDedupeMixin):
    租赁年限: Optional[float] = Field(
        default=None,
        description="在对住所的居住时间基础上，对租赁时间的额外要求"
        )
    租赁额外要求: Optional[List[Literal['房主同意', '登记备案', '成套住房', '该地址无人落户', '同一地址', '其他']]] = Field(
        default=None,
        description="可多选。如有'其他'，需在备注中说明"
        )
    备注: Optional[str] = Field(default=None)


class HouseAndResidenceDetails(BaseDetailsModel, ListDedupeMixin, HouseAndResidenceScoringMixin):
    住房类别: Literal['购买新房', '购房', '拥有房产', '公租房或单位住房', '私有住房租赁', '居住意愿'] = Field(
        ...,
        description="结合相关定义判断，如无特殊说明，合法固定住所默认为'拥有房产'，合法稳定住所默认为'公租房或单位住房'。'购买新房'指仅能通过购买新房落户，'购房'指仅能通过购买房产落户（包括各类房产）；'拥有房产'包括非购买的合法方式获得住房；'居住意愿'仅在文中提到时记录，有任何居住时间要求的不属于此类。如有多项并列则取最宽松的要求，宽松到严格的顺序依次为：居住意愿、私有住房租赁、公租房或单位住房、拥有房产、购房、购买新房"
        )
    拥有住房属性: Optional[HouseOwnershipDetails] = Field(default=None, description="如住房类别为'购买新房'、'购房'或'拥有房产'，则填写此项；不能同时填写'租赁住房属性'。")
    租赁住房属性: Optional[HouseRentalDetails] = Field(default=None, description="如住房类别为'公租房或单位住房'或'私有住房租赁'，则填写此项；不能同时填写'拥有住房属性'。")
    居住年限: Optional[float] = Field(default=None, description="实际居住年限要求，包括持有居住证、暂住证等的时间。")
    其他居住要求: Optional[List[Literal['实际居住', '持居住证', '其他']]] = Field(
        default=None,
        description="可多选。如有'其他'，需在备注中说明"
        )
    备注: Optional[str] = Field(default=None)

    @model_validator(mode='wrap')
    @classmethod
    def validate_mutually_exclusive_housing(cls, values: Any, handler: Any) -> 'HouseAndResidenceDetails':
        """Ensure at most one of 拥有住房属性 and 租赁住房属性 is non-empty.

        A reasonable policy would not simultaneously require an applicant to own
        and rent property, as requirements within each Details object are conjunctive.

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
        ownership_empty = instance.拥有住房属性 is None or instance.拥有住房属性.is_empty()
        rental_empty = instance.租赁住房属性 is None or instance.租赁住房属性.is_empty()

        if not ownership_empty and not rental_empty:
            raise ResidenceConditionConflictError(
                "Cannot have both non-empty 拥有住房属性 and 租赁住房属性.\nA policy cannot simultaneously require ownership and rental of property.",
                raw_input=raw_input_str
            )

        return instance


class EmploymentDetails(BaseDetailsModel, EmploymentScoringMixin):
    就业类别: Literal['合法稳定就业', '签订劳动合同', '灵活就业', '有生活来源', '就业意愿'] = Field(
        ..., description="如无特殊说明，“就业”默认为合法稳定就业。合法稳定就业包括合法稳定经营；“灵活就业”仅在原文中提到“灵活就业”时使用；'就业意愿'仅在不要求有合法稳定职业、签订劳动合同、有生活来源的情况下，且政策提出类似于“有意愿就业”、“拟来就业”时使用。如有多项并列则取最宽松的要求，宽松到严格的顺序依次为：就业意愿、有生活来源、灵活就业、签订劳动合同、合法稳定就业"
        )
    就业年限: Optional[float] = Field(default=None)
    劳动合同年限: Optional[float] = Field(default=None)
    年收入要求: Optional[float] = Field(default=None, description="单位为万元")
    备注: Optional[str] = Field(default=None)


class InvestmentDetails(BaseDetailsModel, ListDedupeMixin, InvestmentScoringMixin):
    累计投资_万元: Optional[float] = Field(default=None)
    累计投资年限: Optional[float] = Field(default=None)
    年投资_万元: Optional[float] = Field(default=None)
    其他投资要求: Optional[List[Literal['无投资金额要求', '无投资年限要求', '营业执照', '固定经营场所','具体标准未明确', '其他']]] = Field(
        default=None,
        description="如没有对投资金额（年限）的要求，则选择'无投资金额（年限）要求'；'具体标准未明确'指，有一定要求但未给出具体数额或年限；如有未列出的要求选择'其他'，并在备注中说明"
        )
    备注: Optional[str] = Field(default=None)


class TaxDetails(BaseDetailsModel, ListDedupeMixin, TaxScoringMixin):
    累计纳税_万元: Optional[float] = Field(default=None)
    累计纳税年限: Optional[float] = Field(default=None)
    年纳税_万元: Optional[float] = Field(default=None)
    经营年限: Optional[float] = Field(default=None)
    其他纳税要求: Optional[List[Literal['无纳税金额要求', '无纳税年限要求', '营业执照', '固定经营场所', '具体标准未明确', '其他']]] = Field(
        default=None,
        description="如没有对纳税金额（年限）的要求，则选择'无纳税金额（年限）要求'；'具体标准未明确'指，有一定要求但未给出具体数额或年限；如有未列出的要求选择'其他'，并在备注中说明"
        )
    备注: Optional[str] = Field(default=None)


class EducationDetails(BaseDetailsModel, ListDedupeMixin, EducationScoringMixin):
    学位: Literal['博士', '硕士', '本科', '大专', '高中', '中专', '初中', '小学'] = Field(
        ...,
        description="如有多项，取最低学位要求。高校默认为大专，职业院校默认为中专。宽松到严格的顺序依次为：小学、初中、中专、高中、大专、本科、硕士、博士"
        )
    毕业年限: Optional[float] = Field(
        default=None,
        description="毕业时间在几年以内"
        )
    其他学历要求: Optional[List[Literal['入学迁入', '本市高校', '本省高校', '其他']]] = Field(
        default=None,
        description="可多选。'入学迁入'指学生入学时可迁入户口（对应学校集体户为落户类别）。如有'其他'，需在备注中说明"
        )
    备注: Optional[str] = Field(default=None)


class ProfessionalQualificationDetails(BaseDetailsModel, ProfessionalQualificationScoringMixin):
    职称: Optional[Literal['初级', '中级', '高级', '其他']] = Field(default=None, description="如有多项，取最低职称要求。无特殊说明时，‘取得职称’记为初级。若有'其他'，需在备注中说明具体内容")
    职业等级: Optional[Literal['技术工人', '初级工', '中级工', '高级工', '技师', '其他']] = Field(default=None, description="如有多项，取最低职业等级要求。‘取得职业资格’记为初级工。若有'其他'，需在备注中说明具体内容")
    备注: Optional[str] = Field(default=None)


class SocialSecurityDetails(BaseDetailsModel, ListDedupeMixin, SocialSecurityScoringMixin):
    社保种类: List[Literal['社会保险', '养老保险', '医疗保险', '工伤保险', '生育保险', '失业保险']] = Field(
        ..., description="需要缴纳的社保种类，可多选。如无特殊说明默认为社会保险")
    缴纳年限: Optional[float] = Field(default=None)
    备注: Optional[str] = Field(default=None)


class OtherRequirements(BaseDetailsModel, ListDedupeMixin, OtherScoringMixin):
    标签: List[Literal['本人意愿', '零门槛', '奖励补贴', '优先办理', '其他']] = Field(
        ..., description='可多选。"零门槛"仅在所有落户要求为零门槛时使用（不要求就业、住房、学历、职称等）。其他要求的标签分类，若有\'其他\'则需在备注中说明具体内容')
    备注: Optional[str] = Field(default=None)


class RichRequirement(BaseModel, RichRequirementScoringMixin):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    年龄性别: Optional[AgeAndSexDetails] = Field(default=None)
    原有户籍: Optional[PreviousHukouDetails] = Field(
        default=None,
        description="对外来人口的户籍要求，如仅为本市或本地区以外人员则不记录"
        )
    住房居住: Optional[HouseAndResidenceDetails] = Field(
        default=None,
        description="'拥有住房属性'与'租赁住房属性'至多填写一项"
        )
    就业: Optional[EmploymentDetails] = Field(default=None)
    投资: Optional[InvestmentDetails] = Field(default=None)
    纳税: Optional[TaxDetails] = Field(default=None)
    学历: Optional[EducationDetails] = Field(default=None)
    职业资格: Optional[ProfessionalQualificationDetails] = Field(default=None)
    社保: Optional[SocialSecurityDetails] = Field(default=None)
    其他: Optional[OtherRequirements] = Field(default=None)

    # @model_validator(mode='after')
    # def check_at_least_one_requirement(self) -> 'RichRequirement':
    #     """Ensure at least one requirement is provided (empty conjunction not allowed)"""
    #     # Check if there are any non-None, non-empty requirements
    #     has_requirement = False
    #     for field_name in self.__class__.model_fields.keys():
    #         field_value = getattr(self, field_name)
    #         if field_value is not None:
    #             # If the field is a Details object, check if it's empty
    #             if isinstance(field_value, DetailsBaseModel):
    #                 if not field_value.is_empty():
    #                     has_requirement = True
    #                     break
    #             else:
    #                 # Non-Details field is present
    #                 has_requirement = True
    #                 break

    #     if not has_requirement:
    #         raise ValueError("Policy route must have at least one requirement (empty conjunction represents infinitely relaxed policy)")
    #     return self

    def count_sub_requirements(self) -> int:
        """Count total number of sub-requirements across all categories"""
        total = 0
        for field_name in self.__class__.model_fields.keys():
            field_value = getattr(self, field_name)
            if field_value is not None and isinstance(field_value, BaseDetailsModel):
                if not field_value.is_empty():
                    # Add the count from this Details object
                    total += field_value.count_sub_requirements()
        return total


class BaseRichPolicyRoute(BaseModel):
    """Base class for enriched settlement route with detailed requirement annotations"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    适用区域: PolicyRegion = Field(default_factory=PolicyRegion)
    落户要求: RichRequirement = Field(default_factory=RichRequirement, description='落户要求的各类别之间，与每个类别的各项细分要求之间均服从逻辑“与”关系：申请者需满足该条件中所有非空项才视作满足此渠道')
    额外政策属性: Optional[AdditionalRouteProperties] = Field(default=None)

    def is_empty(self) -> bool:
        """Check if there are no requirements in this route"""
        # Check if all requirements are None or empty Details objects
        for field_name in RichRequirement.model_fields.keys():
            field_value = getattr(self.落户要求, field_name)
            if field_value is not None:
                # If the field is a Details object, check if it's empty
                if isinstance(field_value, BaseDetailsModel):
                    if not field_value.is_empty():
                        return False
                else:
                    # Non-Details field is present
                    return False
        return True

    def count_requirements(self) -> int:
        """Count the number of non-None, non-empty requirements in this route"""
        count = 0
        for field_name in RichRequirement.model_fields.keys():
            field_value = getattr(self.落户要求, field_name)
            if field_value is not None:
                # If the field is a Details object, check if it's not empty
                if isinstance(field_value, BaseDetailsModel):
                    if not field_value.is_empty():
                        count += 1
                else:
                    # Non-Details field is present
                    count += 1
        return count

    def count_sub_requirements(self) -> int:
        """Count the total number of sub-requirements in this route"""
        return self.落户要求.count_sub_requirements()


class RichPolicyRoute(BaseRichPolicyRoute):
    """Rich settlement route with detailed requirement annotations"""
    pass


class ClassifiedRichPolicyRoute(BaseRichPolicyRoute, ClassifiedRouteScoringMixin):
    """Rich settlement route with detailed requirement annotations and classification labels"""
    渠道类型: Literal['投资型', '房产型', '人才型', '纳税型', '就业型', '租房型', '其他型'] = Field(default="其他型")


class BaseRichPolicyDNF(BaseModel, ListDedupeMixin):
    """Rich policy in DNF with detailed requirement annotations"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[BaseRichPolicyRoute] = Field(default_factory=list, description='将落户政策拆分为若干并列的渠道，申请者满足任意一渠道中的所有要求即可落户')

    def is_empty(self) -> bool:
        """Check if there are no settlement routes"""
        return len(self.落户渠道) == 0

    def count_routes(self) -> int:
        """Count the number of independent settlement routes"""
        return len(self.落户渠道)

    def count_total_requirements(self) -> int:
        """Get the total number of requirements across all routes"""
        return sum(route.count_requirements() for route in self.落户渠道)

    def count_sub_requirements(self) -> int:
        """Get the total number of sub-requirements across all routes"""
        return sum(route.count_sub_requirements() for route in self.落户渠道)


class RichPolicyDNF(BaseRichPolicyDNF):
    """Rich policy in DNF with detailed requirement annotations"""
    pass
    
    
class ClassifiedRichPolicyDNF(BaseRichPolicyDNF, ClassifiedDNFScoringMixin):
    """Rich policy in DNF with detailed requirement annotations and classification labels"""
    落户渠道: List[ClassifiedRichPolicyRoute] = Field(default_factory=list, description='将落户政策拆分为若干并列的渠道，申请者满足任意一渠道中的所有要求即可落户')

    def count_by_classification(self) -> Dict[str, int]:
        """Count the number of routes by classification label"""
        classification_counts = {k: 0 for k in ['投资型', '房产型', '人才型', '纳税型', '就业型', '租房型', '其他型']}
        for route in self.落户渠道:
            classification_counts[route.渠道类型] += 1
        return classification_counts


class BaseRichPolicyDocument(BaseModel, ListDedupeMixin):
    """Base class for complete enriched policy document with metadata and detailed DNF routes"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: DocumentMetadata = Field(default_factory=DocumentMetadata)
    相关定义: List[str] = Field(
        default_factory=list,
        description='文件中与落户政策相关名词（如"合法稳定住所"，"合法稳定就业"）的定义和解释。'
    )
    政策: RichPolicyDNF = Field(default_factory=RichPolicyDNF, description="主析取范式格式的落户政策（含详细标注）")

    def is_empty(self) -> bool:
        """Check if the policy has no settlement routes"""
        return self.政策.is_empty()


class RichPolicyDocument(BaseRichPolicyDocument):
    """Complete enriched policy document with metadata and detailed DNF routes"""
    pass


class ClassifiedRichPolicyDocument(BaseRichPolicyDocument, ClassifiedDocumentScoringMixin):
    """Complete enriched policy document with metadata, detailed DNF routes, and classification labels"""
    政策: ClassifiedRichPolicyDNF = Field(default_factory=ClassifiedRichPolicyDNF, description="主析取范式格式的落户政策（含详细标注和渠道类型）")


class FullRichPolicyDocument(ClassifiedRichPolicyDocument):
    文件名: str = Field(default="")


class BaseRichPolicyDocumentWithRawText(BaseRichPolicyDocument):
    """Rich policy document with raw text for validation"""
    原文文本: str = Field(default="", description="摘录后的政策原文，用于参考和验证")

    def is_empty(self) -> bool:
        """Check if the extracted hukou-related content is empty"""
        return self.政策.is_empty() and not self.原文文本.strip()
    

class RichPolicyDocumentWithRawText(BaseRichPolicyDocumentWithRawText):
    """Rich policy document with raw text for validation"""
    pass


class ClassifiedRichPolicyDocumentWithRawText(BaseRichPolicyDocumentWithRawText):
    """Rich policy document with raw text for validation and classification labels"""
    政策: ClassifiedRichPolicyDNF = Field(default_factory=ClassifiedRichPolicyDNF, description="主析取范式格式的落户政策（含详细标注和渠道类型）")


def flatten_rich_policy_documents(
    documents: List[BaseRichPolicyDocument]
) -> Dict[str, List[Any]]:
    """Flatten a list of rich policy documents into a dictionary of lists of routes that's ready for DataFrame conversion

    Each row represents a policy route. Columns include:
    - Document-level metadata fields from 元数据
    - 相关定义 (list converted to comma-delimited string)
    - Route-level fields with path-based naming (e.g., 落户要求_住房居住_租赁住房属性_租赁年限)
    - Score fields for all scorable objects (e.g., 落户要求_住房居住_score, score)
    """
    # Initialize result dictionary
    result: Dict[str, List[Any]] = {}

    def _ensure_column(col_name: str) -> None:
        """Ensure a column exists in the result dictionary"""
        if col_name not in result:
            result[col_name] = []

    def _add_value(col_name: str, value: Any) -> None:
        """Add a value to a column"""
        _ensure_column(col_name)
        result[col_name].append(value)

    def _get_field_paths_from_class(model_class: type[BaseModel], prefix: str = "") -> List[str]:
        """Recursively extract all field paths from a Pydantic model class

        Returns a list of field paths (e.g., ['prefix_field1', 'prefix_nested_subfield'])
        """
        import typing
        field_paths = []

        for field_name, field_info in model_class.model_fields.items():
            full_key = f"{prefix}_{field_name}" if prefix else field_name

            # Check if the field type is a BaseModel subclass
            field_type = field_info.annotation

            # Handle Optional types and other generics
            if hasattr(field_type, '__origin__'):
                if field_type.__origin__ is typing.Union:
                    # For Optional[T] or Union types, get non-None types
                    args = [arg for arg in field_type.__args__ if arg is not type(None)]
                    if args:
                        field_type = args[0]

            # Check if it's a BaseModel subclass (nested model)
            # Use try-except to handle edge cases
            is_nested_model = False
            try:
                is_nested_model = isinstance(field_type, type) and issubclass(field_type, BaseModel)
            except TypeError:
                # Not a class or can't check subclass
                pass

            if is_nested_model:
                # Recursively get nested field paths (don't add parent key)
                nested_paths = _get_field_paths_from_class(field_type, full_key)
                field_paths.extend(nested_paths)
            else:
                # Atomic field or list
                field_paths.append(full_key)

        # Add score field if the class has scoring capability
        if hasattr(model_class, 'score'):
            score_key = f"{prefix}_score" if prefix else "score"
            field_paths.append(score_key)

        return field_paths

    def _add_placeholder_fields_for_class(model_class: type[BaseModel], prefix: str = "") -> None:
        """Add None values for all fields defined in a model class"""
        field_paths = _get_field_paths_from_class(model_class, prefix)
        for field_path in field_paths:
            _add_value(field_path, None)

    def _flatten_base_model(obj: BaseModel, prefix: str = "") -> Dict[str, Any]:
        """Recursively flatten a BaseModel into a flat dictionary with path-based keys

        Returns a dictionary where:
        - Atomic fields become {prefix_fieldname: value}
        - Nested BaseModel fields are recursively flattened (parent key not included)
        - List fields are converted to comma-delimited strings
        - Score fields are added for Scorable objects
        """
        import typing
        flat_dict = {}

        for field_name, field_info in obj.__class__.model_fields.items():
            field_value = getattr(obj, field_name)
            full_key = f"{prefix}_{field_name}" if prefix else field_name

            # Get the field type to check if it's a BaseModel
            field_type = field_info.annotation

            # Handle Optional types and other generics
            if hasattr(field_type, '__origin__'):
                if field_type.__origin__ is typing.Union:
                    # For Optional[T] or Union types, get non-None types
                    args = [arg for arg in field_type.__args__ if arg is not type(None)]
                    if args:
                        field_type = args[0]

            # Check if the field type is a BaseModel subclass
            is_nested_model = False
            try:
                is_nested_model = isinstance(field_type, type) and issubclass(field_type, BaseModel)
            except TypeError:
                # Not a class or can't check subclass
                pass

            if field_value is None and is_nested_model:
                # Field is None but should be a nested model - add placeholders for all nested fields
                nested_paths = _get_field_paths_from_class(field_type, full_key)
                for path in nested_paths:
                    flat_dict[path] = None
            elif field_value is not None and isinstance(field_value, BaseModel):
                # Recursively flatten nested BaseModel (don't include parent key)
                nested_dict = _flatten_base_model(field_value, full_key)
                flat_dict.update(nested_dict)
            elif isinstance(field_value, list):
                # Convert list to string using default representation (with brackets)
                flat_dict[full_key] = str(field_value)
            else:
                # Atomic value (including None for atomic fields)
                flat_dict[full_key] = field_value

        # Add score field if the object is scorable (has a score property)
        if hasattr(obj, 'score'):
            score_key = f"{prefix}_score" if prefix else "score"
            try:
                flat_dict[score_key] = str(obj.score)
            except:
                flat_dict[score_key] = None

        return flat_dict

    # Process each document
    for doc in documents:
        # Each route becomes a separate row
        routes = doc.政策.落户渠道 if hasattr(doc.政策, '落户渠道') else []

        # If no routes, skip this document
        if not routes:
            continue

        for route in routes:
            # 1. Add document-level metadata fields
            if hasattr(doc, '文件名'):
                _add_value("文件名", doc.文件名)
            metadata = doc.元数据
            for field_name in metadata.__class__.model_fields.keys():
                field_value = getattr(metadata, field_name)
                if isinstance(field_value, list):
                    _add_value(field_name, str(field_value))
                else:
                    _add_value(field_name, field_value)

            # 2. Add 相关定义
            _add_value("相关定义", str(doc.相关定义))

            # 3. Add 渠道类型 (may not exist for all route types)
            if hasattr(route, '渠道类型'):
                _add_value("渠道类型", route.渠道类型)
            else:
                _add_value("渠道类型", "")

            # 4. Add 适用区域 fields (PolicyRegion)
            region_dict = _flatten_base_model(route.适用区域, "适用区域")
            for key, value in region_dict.items():
                _add_value(key, value)

            # 5. Add all 落户要求 fields (RichRequirement with all detail categories)
            # We need to ensure ALL possible requirement categories exist as columns
            requirement_categories = [
                '年龄性别', '原有户籍', '住房居住', '就业',
                '投资', '纳税', '学历', '职业资格', '社保', '其他'
            ]

            for category in requirement_categories:
                category_obj = getattr(route.落户要求, category, None)
                category_prefix = f"落户要求_{category}"

                if category_obj is not None and isinstance(category_obj, BaseModel):
                    # Flatten this category
                    category_dict = _flatten_base_model(category_obj, category_prefix)
                    for key, value in category_dict.items():
                        _add_value(key, value)
                else:
                    # Category doesn't exist - need to add placeholders for all possible fields
                    # We'll determine the fields by looking at the corresponding Details class schema
                    category_class_map = {
                        '年龄性别': AgeAndSexDetails,
                        '原有户籍': PreviousHukouDetails,
                        '住房居住': HouseAndResidenceDetails,
                        '就业': EmploymentDetails,
                        '投资': InvestmentDetails,
                        '纳税': TaxDetails,
                        '学历': EducationDetails,
                        '职业资格': ProfessionalQualificationDetails,
                        '社保': SocialSecurityDetails,
                        '其他': OtherRequirements
                    }

                    if category in category_class_map:
                        details_class = category_class_map[category]
                        # Extract field names from the class schema instead of creating an instance
                        _add_placeholder_fields_for_class(details_class, category_prefix)

            # Add score for 落户要求 composite object
            if hasattr(route.落户要求, 'score'):
                try:
                    _add_value("落户要求_score", str(route.落户要求.score))
                except:
                    _add_value("落户要求_score", None)
            else:
                _add_value("落户要求_score", None)

            # 6. Add 额外政策属性 fields
            if route.额外政策属性 is not None:
                extra_dict = _flatten_base_model(route.额外政策属性, "额外政策属性")
                for key, value in extra_dict.items():
                    _add_value(key, value)
            else:
                # Add placeholders for all AdditionalRouteProperties fields
                _add_placeholder_fields_for_class(AdditionalRouteProperties, "额外政策属性")

            # 7. Add overall route score
            if hasattr(route, 'score'):
                try:
                    _add_value("score", str(route.score))
                except:
                    _add_value("score", None)
            else:
                _add_value("score", None)

    return result
