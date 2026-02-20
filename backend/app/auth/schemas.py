import uuid

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_admin: bool
    role: str = "admin"
    tenant_id: uuid.UUID
    tenant_name: str | None = None

    model_config = {"from_attributes": True}


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "viewer"  # admin, operator, viewer
    password: str  # temporary password


class UpdateUserRoleRequest(BaseModel):
    role: str  # admin, operator, viewer


class UserListResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}
