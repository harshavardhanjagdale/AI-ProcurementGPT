"""
Settings API endpoints for LLM provider configuration.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models.llm_settings import LLMSettings
from app.models.user import User
from app.ai.llm_client import llm_client, AVAILABLE_MODELS, PROVIDER_MAP

logger = logging.getLogger(__name__)

router = APIRouter()


class LLMSettingsUpdate(BaseModel):
    provider: str
    api_key: str
    model: str


class LLMValidateRequest(BaseModel):
    provider: str
    api_key: str
    model: str


@router.get("/llm")
async def get_llm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current LLM configuration (API key masked)."""
    result = await db.execute(
        select(LLMSettings)
        .where(LLMSettings.user_id == current_user.id, LLMSettings.is_active == True)
    )
    setting = result.scalar_one_or_none()

    if setting:
        return {
            "provider": setting.provider,
            "model": setting.model,
            "api_key_hint": f"****{setting.api_key[-4:]}" if len(setting.api_key) > 4 else "****",
            "is_configured": True,
        }

    return {
        "provider": llm_client.provider_name or "anthropic",
        "model": llm_client.model or "",
        "api_key_hint": "From .env" if llm_client.is_configured else "",
        "is_configured": llm_client.is_configured,
    }


@router.patch("/llm")
async def update_llm_settings(
    payload: LLMSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update LLM provider settings and switch the active provider."""
    if payload.provider not in PROVIDER_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {payload.provider}. Must be one of: {list(PROVIDER_MAP.keys())}",
        )

    valid_models = [m["id"] for m in AVAILABLE_MODELS.get(payload.provider, [])]
    if payload.model not in valid_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model for {payload.provider}. Must be one of: {valid_models}",
        )

    # Deactivate any existing settings for this user
    await db.execute(
        update(LLMSettings)
        .where(LLMSettings.user_id == current_user.id)
        .values(is_active=False)
    )

    # Create new active setting
    new_setting = LLMSettings(
        user_id=current_user.id,
        provider=payload.provider,
        api_key=payload.api_key,
        model=payload.model,
        is_active=True,
    )
    db.add(new_setting)
    await db.commit()

    # Switch the runtime LLM client
    try:
        llm_client.set_provider(payload.provider, payload.api_key, payload.model)
    except Exception as e:
        logger.error(f"Failed to switch LLM provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize provider: {str(e)}",
        )

    return {
        "message": f"LLM provider switched to {payload.provider} ({payload.model})",
        "provider": payload.provider,
        "model": payload.model,
    }


@router.post("/llm/validate")
async def validate_llm_key(
    payload: LLMValidateRequest,
    _current_user: User = Depends(get_current_user),
):
    """Validate an API key by making a test call to the provider."""
    if payload.provider not in PROVIDER_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {payload.provider}",
        )

    provider_class = PROVIDER_MAP[payload.provider]

    try:
        provider = provider_class(api_key=payload.api_key, model=payload.model)
        response = await provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'hello' in one word.",
            max_tokens=10,
        )
        return {
            "valid": True,
            "message": f"Key validated successfully. Provider responded: {response.strip()[:50]}",
        }
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid" in error_msg.lower() or "auth" in error_msg.lower():
            return {
                "valid": False,
                "message": "Invalid API key. Please check and try again.",
            }
        return {
            "valid": False,
            "message": f"Validation failed: {error_msg[:100]}",
        }


@router.get("/llm/models")
async def get_available_models(
    provider: str | None = None,
    _current_user: User = Depends(get_current_user),
):
    """List available models, optionally filtered by provider."""
    if provider:
        if provider not in AVAILABLE_MODELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown provider: {provider}",
            )
        return {
            "provider": provider,
            "models": AVAILABLE_MODELS[provider],
        }

    return {"providers": AVAILABLE_MODELS}


@router.delete("/llm")
async def remove_llm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove saved API key and revert to .env configuration."""
    from sqlalchemy import delete

    result = await db.execute(
        delete(LLMSettings).where(LLMSettings.user_id == current_user.id)
    )
    await db.commit()

    # Re-initialize from .env
    llm_client._initialize_from_env()

    rows_deleted = result.rowcount
    if rows_deleted > 0:
        return {
            "message": "API key removed. Reverted to .env configuration.",
            "provider": llm_client.provider_name,
            "model": llm_client.model,
        }
    return {
        "message": "No saved API key found. Using .env configuration.",
        "provider": llm_client.provider_name,
        "model": llm_client.model,
    }
