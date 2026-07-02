from pydantic import BaseModel


class IngestTriggerResponse(BaseModel):
    status: str
    session_key: int


class IngestStatusResponse(BaseModel):
    session_key: int
    status: str
    stages_complete: list[str]
    stages_remaining: list[str]
    rows_ingested: dict[str, int]
