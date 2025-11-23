from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TeamMember(BaseModel):
    user_id: str
    username: str
    is_active: bool


class TeamCreate(BaseModel):
    team_name: str
    members: List[TeamMember]


class TeamResponse(BaseModel):
    team_name: str
    members: List[TeamMember]


class User(BaseModel):
    user_id: str
    username: str
    team_name: str
    is_active: bool


class SetActiveRequest(BaseModel):
    user_id: str
    is_active: bool


class CreatePRRequest(BaseModel):
    pull_request_id: str
    pull_request_name: str
    author_id: str


class MergePRRequest(BaseModel):
    pull_request_id: str


class ReassignRequest(BaseModel):
    pull_request_id: str
    old_user_id: str


class PullRequest(BaseModel):
    pull_request_id: str
    pull_request_name: str
    author_id: str
    status: str
    assigned_reviewers: List[str]
    createdAt: Optional[datetime] = None
    mergedAt: Optional[datetime] = None


class PullRequestShort(BaseModel):
    pull_request_id: str
    pull_request_name: str
    author_id: str
    status: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class GetReviewResponse(BaseModel):
    user_id: str
    pull_requests: List[PullRequestShort]


class ReassignResponse(BaseModel):
    pr: PullRequest
    replaced_by: str
