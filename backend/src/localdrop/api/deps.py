"""Dépendances FastAPI partagées."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from localdrop.core.config import Settings


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
