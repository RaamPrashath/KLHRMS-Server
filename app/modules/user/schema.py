from pydantic import BaseModel


class SetPasswordRequest(BaseModel):
    new_password: str


class SetPasswordResponse(BaseModel):
    success: bool
    message: str
