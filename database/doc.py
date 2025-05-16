from docarray.typing import NdArray
from docarray import BaseDoc

class Document(BaseDoc):
    _id: str
    timestamp: int
    query: str
    title: str
    press: str
    summary: Optional[str] = None
    content: str
    url: str
    origin: str
    embedding: NdArray[1024] = Field(is_embedding=True)