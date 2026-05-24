from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DocumentResponse(BaseModel):
    success: bool
    document_id: str
    filename: str
    upload_time: datetime
    status: str
