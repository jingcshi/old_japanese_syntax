from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from ._model_utils import ListDedupeMixin


class DocumentMetadata(BaseModel, ListDedupeMixin):
    """Metadata extracted from policy documents"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    标题: str = Field(default="", description="文件标题")
    发文地区: str = Field(default="", description="文件所属地区")
    发文时间: str = Field(default="", description="文件的发布日期，尽可能以接近ISO格式输出")
    实施时间: Optional[str] = Field(default=None, description="文件中政策开始实施的日期 (YYYY-MM-DD)")
    失效时间: Optional[str] = Field(default=None, description="文件中政策失效的日期 (YYYY-MM-DD)")
    相关文件: Optional[List[str]] = Field(default=None, description="与该文件相关的上级、前序文件")
    政策目标: Optional[str] = Field(default=None, description="文件中政策的主要目标和具体指标")


class RawDocument(BaseModel):
    """Raw document with filename and text content"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    文件名: str = Field(default="")
    原文: str = Field(default="")

    def is_empty(self) -> bool:
        """Check if the extracted hukou-related content is empty"""
        return not self.原文.strip()


class ExtractedDocument(BaseModel, ListDedupeMixin):
    """Step 1 extracted document with metadata and extracted content"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    元数据: DocumentMetadata = Field(default_factory=DocumentMetadata)
    落户政策相关内容: str = Field(
        default="",
        description="文件中与落户政策相关的内容。如文件中没有涉及落户政策的段落，则此项应为空。"
    )
    相关定义: List[str] = Field(
        default_factory=list,
        description='文件中与落户政策相关名词（如"合法稳定住所"，"合法稳定就业"）的定义和解释。'
    )

    def is_empty(self) -> bool:
        """Check if the extracted hukou-related content is empty"""
        return not self.落户政策相关内容.strip()

    def content_length(self) -> int:
        """Get the length of the hukou-related content"""
        return len(self.落户政策相关内容.strip())

    def count_lines(self) -> int:
        """Count the number of lines in the hukou-related content"""
        return len(self.落户政策相关内容.strip().splitlines())
