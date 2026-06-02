from __future__ import annotations

from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, Field, HttpUrl

URL_MAX_LENGTH = 2048


class CreateURLRequest(BaseModel):
    url: HttpUrl

    @property
    def url_str(self) -> str:
        return str(self.url)


class CreateURLResponse(BaseModel):
    short_url: Annotated[AnyHttpUrl, Field(description="Public short URL pointing at the stored mapping.")]


def assert_under_length(url: str) -> None:
    if len(url) > URL_MAX_LENGTH:
        raise ValueError(f"url length {len(url)} exceeds maximum of {URL_MAX_LENGTH} characters")
