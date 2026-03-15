import json
from pathlib import Path
from typing import Optional, List, Literal, Dict, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator

from ..io import load_json
from ._model_utils import ListDedupeMixin
from .step2 import AdditionalRouteProperties
from .step4 import PolicyRegion
from .step5 import BaseDetailsModel, RichRequirement, ClassifiedRichPolicyDocument
from ..scoring import ClassifiedDNFScoringMixin, ClassifiedRouteScoringMixin


def urban_in_region(region: PolicyRegion) -> bool:
    """Check if the policy region includes urban areas (cities or districts)"""
    return "全市" in region.可落户区划 or "市区" in region.可落户区划 or "开发区" in region.可落户区划

def county_in_region(region: PolicyRegion) -> bool:
    """Check if the policy region includes counties"""
    return "全市" in region.可落户区划 or "县区" in region.可落户区划

def rural_in_region(region: PolicyRegion) -> bool:
    """Check if the policy region includes rural areas (townships or villages)"""
    return "农村" in region.可落户区划


class IndependentRouteMetadata(BaseModel):
    """
    Metadata for an IndependentRichPolicyRoute.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    文件出处: str = Field(default="", description="政策文件的名称或编号")
    发文时间: str = Field(default="", description="文件的发布日期，尽可能以接近ISO格式输出")
    实施时间: Optional[str] = Field(default=None, description="文件中政策开始实施的日期 (YYYY-MM-DD)")
    失效时间: Optional[str] = Field(default=None, description="文件中政策失效的日期 (YYYY-MM-DD)")


class IndependentRichPolicyRoute(BaseModel, ClassifiedRouteScoringMixin, ListDedupeMixin):
    """
    ClassifiedRichPolicyRoute with date information.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: IndependentRouteMetadata = Field(default_factory=IndependentRouteMetadata)
    渠道类型: Literal['投资型', '房产型', '人才型', '纳税型', '就业型', '租房型', '其他型'] = Field(default="其他型")
    落户要求: RichRequirement = Field(default_factory=RichRequirement)
    额外政策属性: Optional[AdditionalRouteProperties] = Field(default=None)
    相关定义: List[str] = Field(default_factory=list)

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


class BaseIndependentRichPolicy(BaseModel, ListDedupeMixin):
    """
    Base class for policy documents with independent route properties.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    落户渠道: List[IndependentRichPolicyRoute] = Field(default_factory=list)

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
    
    def count_by_classification(self) -> Dict[str, int]:
        """Count the number of routes by classification label"""
        classification_counts = {k: 0 for k in ['投资型', '房产型', '人才型', '纳税型', '就业型', '租房型', '其他型']}
        for route in self.落户渠道:
            classification_counts[route.渠道类型] += 1
        return classification_counts
    

class IndependentRichPolicy(BaseIndependentRichPolicy):
    """
    Does not assume DNF structure within each list of routes: the routes may not be in strict disjunction.
    """
    pass


class IndependentRichPolicyDNF(BaseIndependentRichPolicy, ClassifiedDNFScoringMixin):
    """
    Assumes DNF structure within each list of routes: the routes must be in strict disjunction.
    """
    pass


class CityPolicy(BaseModel):
    """
    Collection of policy routes for a city. 
    Note that we do *not* assume DNF structure within each list of routes: the routes may not be in strict disjunction.
    This is partially because each route has its own timeframe, and may act on different periods, or override previous policies.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    城市名: str = Field(default="")
    市区: IndependentRichPolicy = Field(default_factory=IndependentRichPolicy)
    县区: IndependentRichPolicy = Field(default_factory=IndependentRichPolicy)
    农村: IndependentRichPolicy = Field(default_factory=IndependentRichPolicy)


class CityPolicyDNF(BaseModel):
    """
    Collection of policy routes for a city. 
    Note that we *do* assume DNF structure within each list of routes: the routes must be in strict disjunction.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    城市名: str = Field(default="")
    市区: IndependentRichPolicyDNF = Field(default_factory=IndependentRichPolicyDNF)
    县区: IndependentRichPolicyDNF = Field(default_factory=IndependentRichPolicyDNF)
    农村: IndependentRichPolicyDNF = Field(default_factory=IndependentRichPolicyDNF)

    def set_scoring_params(self, params: dict) -> None:
        """Set scoring parameters for all areas"""
        self.市区.scoring_params = params
        self.县区.scoring_params = params
        self.农村.scoring_params = params

    def model_dump_with_scores(self) -> Dict:
        """Dump the model including computed scores for each area"""
        data = self.model_dump()
        data['市区'] = self.市区.model_dump_with_score()
        data['县区'] = self.县区.model_dump_with_score()
        data['农村'] = self.农村.model_dump_with_score()
        return data


class PolicyCollection(BaseModel):
    """
    Collection of policy routes for multiple cities.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    政策: Dict[str, CityPolicy] = Field(default_factory=dict)

    def add_document(self, document: ClassifiedRichPolicyDocument) -> None:
        """Add a ClassifiedRichPolicyDocument to the collection under the specified city"""
        for route in document.政策.落户渠道:
            route_metadata = IndependentRouteMetadata(
                文件出处=document.元数据.标题,
                发文时间=document.元数据.发文时间,
                实施时间=document.元数据.实施时间,
                失效时间=document.元数据.失效时间
            )
            independent_route = IndependentRichPolicyRoute(
                元数据=route_metadata,
                渠道类型=route.渠道类型,
                落户要求=route.落户要求,
                额外政策属性=route.额外政策属性,
                相关定义=document.相关定义
            )
            region = route.适用区域
            add_urban = urban_in_region(region)
            add_county = county_in_region(region)
            add_rural = rural_in_region(region)
            for city in region.可落户城市:
                if city not in self.政策:
                    self.政策[city] = CityPolicy(城市名=city)
                if add_urban:
                    self.政策[city].市区.落户渠道.append(independent_route)
                if add_county:
                    self.政策[city].县区.落户渠道.append(independent_route)
                if add_rural:
                    self.政策[city].农村.落户渠道.append(independent_route)

    @classmethod
    def from_documents(cls, documents: List[ClassifiedRichPolicyDocument]) -> 'PolicyCollection':
        """Create a PolicyCollection from a list of ClassifiedRichPolicyDocument"""
        collection = cls()
        for document in documents:
            collection.add_document(document)
        return collection
    
    @classmethod
    def from_document_json(cls, json_file: Union[str, Path]) -> 'PolicyCollection':
        """Create a PolicyCollection from a JSON file containing a list of ClassifiedRichPolicyDocument"""
        data = load_json(json_file)
        documents = []
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of documents")
        for item in data:
            try:
                doc = ClassifiedRichPolicyDocument(**item)
                documents.append(doc)
            except Exception as e:
                print(f"Warning: Ignoring invalid document:\n{e}")
                continue
        return cls.from_documents(documents)


class PolicyCollectionDNF(BaseModel):
    """
    Collection of policy routes for multiple cities, assuming DNF.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    政策: Dict[str, CityPolicyDNF] = Field(default_factory=dict)

    def add_document(self, document: ClassifiedRichPolicyDocument) -> None:
        """Add a ClassifiedRichPolicyDocument to the collection under the specified city"""
        for route in document.政策.落户渠道:
            route_metadata = IndependentRouteMetadata(
                文件出处=document.元数据.标题,
                发文时间=document.元数据.发文时间,
                实施时间=document.元数据.实施时间,
                失效时间=document.元数据.失效时间
            )
            independent_route = IndependentRichPolicyRoute(
                元数据=route_metadata,
                渠道类型=route.渠道类型,
                落户要求=route.落户要求,
                额外政策属性=route.额外政策属性,
                相关定义=document.相关定义
            )
            region = route.适用区域
            add_urban = urban_in_region(region)
            add_county = county_in_region(region)
            add_rural = rural_in_region(region)
            for city in region.可落户城市:
                if city not in self.政策:
                    self.政策[city] = CityPolicyDNF(城市名=city)
                if add_urban:
                    self.政策[city].市区.落户渠道.append(independent_route)
                if add_county:
                    self.政策[city].县区.落户渠道.append(independent_route)
                if add_rural:
                    self.政策[city].农村.落户渠道.append(independent_route)

    @classmethod
    def from_documents(cls, documents: List[ClassifiedRichPolicyDocument]) -> 'PolicyCollectionDNF':
        """Create a PolicyCollection from a list of ClassifiedRichPolicyDocument"""
        collection = cls()
        for document in documents:
            collection.add_document(document)
        return collection
    
    @classmethod
    def from_document_json(cls, json_file: Union[str, Path]) -> 'PolicyCollectionDNF':
        """Create a PolicyCollection from a JSON file containing a list of ClassifiedRichPolicyDocument"""
        data = load_json(json_file)
        documents = []
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of documents")
        for item in data:
            try:
                doc = ClassifiedRichPolicyDocument(**item)
                documents.append(doc)
            except Exception as e:
                print(f"Warning: Ignoring invalid document:\n{e}")
                continue
        return cls.from_documents(documents)
    
    def set_scoring_params(self, params: dict) -> None:
        """Set scoring parameters for all city policies and their areas"""
        for city_policy in self.政策.values():
            city_policy.set_scoring_params(params)

    def model_dump_with_scores(self) -> Dict:
        """Dump the model including computed scores for each city and area"""
        data = self.model_dump()
        for city_name in data['政策']:
            data['政策'][city_name] = self.政策[city_name].model_dump_with_scores()
        return data