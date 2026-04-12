from typing import Optional, List, Literal, Union
from pydantic import BaseModel, Field, ConfigDict


class Syllable(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    vowel: Literal['a', 'i', 'u', 'e', 'o', 'ye', 'wo', 'wi'] = Field(description="The vowel component of the syllable")
    consonant: Optional[Literal['k', 'g', 's', 'z', 't', 'd', 'n', 'p', 'b', 'm', 'y', 'r', 'w']] = Field(default=None, description="The consonant component of the syllable, if any")

    def __str__(self):
        return f"{self.consonant or ''}{self.vowel}"


class BaseTranscribedCharacter(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    char: str = Field(min_length=1, max_length=1, description="The original character as it appears in the document")
    transcription: List[Syllable] = Field(default_factory=list, description="The phonetic transcription of the character as a sequence of zero, one or more syllables. Can be empty, but such cases are expected to be rare.")

    def spell(self) -> List[str]:
        return [str(syllable) for syllable in self.transcription]


class TranscribedPhonograph(BaseTranscribedCharacter):
    type: Literal['PHON'] = Field(description="The type of the character, which is 'PHON' for phonographs")
    transcription: List[Syllable] = Field(default_factory=list, min_length=1, description="The syllable(s) representing the phonograph.")


class TranscribedLogograph(BaseTranscribedCharacter):
    type: Literal['LOG'] = Field(description="The type of the character, which is 'LOG' for logographs")
    transcription: List[Syllable] = Field(default_factory=list, description="The phonetic transcription of the logograph as a sequence of zero, one or more syllables. Can be empty, but such cases are expected to be rare.")


class TranscribedUncertainCharacter(BaseTranscribedCharacter):
    type: Literal['UNC'] = Field(description="The type of the character, which is 'UNC' for uncertain characters")
    transcription: List[Syllable] = Field(default_factory=list, description="The phonetic transcription of the uncertain character as a sequence of zero, one or more syllables. Can be empty, but such cases are expected to be rare.")


TranscribedCharacter = Union[TranscribedPhonograph, TranscribedLogograph, TranscribedUncertainCharacter]


class TranscribedOldJapanese(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    text: List[TranscribedCharacter] = Field(default_factory=list, description="The transcribed text decomposed into characters with annotations")
    reasoning: Optional[str] = Field(default=None, description="Reason for the transcription")

    def get_full_transcription(self, concat: bool = False) -> Union[List[str], str]:
        """Get the full transcription of the text as a list of syllables or a concatenated string"""
        full_transcription = []
        for char in self.text:
            full_transcription.extend(char.spell())
                
        if concat:
            return ''.join(full_transcription)
        return full_transcription