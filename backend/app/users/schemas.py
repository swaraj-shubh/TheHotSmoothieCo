import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9]{7,15}$")]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    avatar_url: str | None
    preferences: dict
    is_active: bool
    email_verified: bool = Field(validation_alias="is_email_verified")
    roles: list[str] = Field(validation_alias="role_list")
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: Name | None = None
    phone: Phone | None = None
    preferences: dict | None = Field(default=None, max_length=50)


Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptLine = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
Place = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AddressIn(BaseModel):
    full_name: Name
    phone: Phone
    line1: Line
    line2: OptLine | None = None
    landmark: OptLine | None = None
    city: Place
    state: Place
    postal_code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9 -]{3,12}$")]
    country: Annotated[str, StringConstraints(to_upper=True, pattern=r"^[A-Za-z]{2}$")] = "IN"
    is_default_shipping: bool = False
    is_default_billing: bool = False

    @model_validator(mode="after")
    def _indian_pincode(self) -> "AddressIn":
        if self.country == "IN" and not re.fullmatch(r"[1-9][0-9]{5}", self.postal_code):
            raise ValueError("Indian PIN code must be 6 digits")
        return self


class AddressOut(AddressIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
