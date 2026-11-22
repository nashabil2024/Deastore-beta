"""Robux package models. Keep in sync with frontend/src/lib/types.ts (Package)."""

from pydantic import BaseModel, Field


class PackageOut(BaseModel):
    id: str
    robux: int
    price_idr: int
    tag: str | None = None
    active: bool = True
    sort: int = 0


class PackageIn(BaseModel):
    robux: int = Field(gt=0)
    price_idr: int = Field(gt=0)
    tag: str | None = None
    active: bool = True
    sort: int = 0
