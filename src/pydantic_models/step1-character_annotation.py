from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict


class AnnotatedCharacter(BaseModel):
    """Annotated character with its original form and modern equivalent"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    char: str = Field(min_length=1, max_length=1, description="The original character as it appears in the document")
    annotation: Literal['PHON', 'LOG', 'UNC'] = Field(description="'PHON' for phonographic, 'LOG' for logographic, 'UNC' for uncertain")
    reasoning: Optional[str] = Field(default=None, description="Reason for the annotation")


class CharAnnotatedOldJapanese(BaseModel):
    """Raw text extracted from old Japanese documents"""
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    text: List[AnnotatedCharacter] = Field(default_factory=list, description="The original text decomposed into characters with annotations")

