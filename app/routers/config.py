from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List

from app.auth import get_current_user
from app.models.user import User
from app.schemas.config import (
    UserConfigRequest, UserConfigResponse, DeleteConfigResponse, ConfigValueResponse,
    VoicePersonaConfig, VoicePersonaResponse, PrebuiltPersonaInfo, InstructionPresetInfo,
    PREBUILT_PERSONAS, INSTRUCTION_PRESETS, VALID_VOICES,
)
from app.services.user_config_manager import UserConfigManager

router = APIRouter()

# Initialize config manager
config_manager = UserConfigManager()


def _resolve_voice_persona(raw: dict) -> VoicePersonaResponse:
    """Resolve a stored voice_persona dict into a full response with defaults applied."""
    persona_id = raw.get("persona_id") or "default"
    persona = PREBUILT_PERSONAS.get(persona_id, PREBUILT_PERSONAS["default"])

    voice_name = raw.get("voice_name") or persona["default_voice"]
    persona_name = raw.get("persona_name") or persona["name"]

    # Resolve custom_instructions: if it matches a preset ID, expand it
    custom_instructions = raw.get("custom_instructions")
    if custom_instructions and custom_instructions in INSTRUCTION_PRESETS:
        custom_instructions = INSTRUCTION_PRESETS[custom_instructions]["instructions"]

    return VoicePersonaResponse(
        persona_id=persona_id,
        voice_name=voice_name,
        custom_instructions=custom_instructions,
        persona_name=persona_name,
        language=persona.get("default_language") or "Match user's language",
        enable_transcription=raw.get("enable_transcription", True),
        persona_description=persona["description"],
        persona_style_prompt=persona["style_prompt"],
    )


@router.get("/voice-personas", response_model=List[PrebuiltPersonaInfo])
async def list_voice_personas():
    """List all available prebuilt personas."""
    return [
        PrebuiltPersonaInfo(
            id=pid,
            name=p["name"],
            default_voice=p["default_voice"],
            description=p["description"],
        )
        for pid, p in PREBUILT_PERSONAS.items()
    ]


@router.get("/instruction-presets", response_model=List[InstructionPresetInfo])
async def list_instruction_presets():
    """List all available instruction presets."""
    return [
        InstructionPresetInfo(id=pid, label=p["label"], instructions=p["instructions"])
        for pid, p in INSTRUCTION_PRESETS.items()
    ]


@router.get("/user/voice-persona", response_model=VoicePersonaResponse)
async def get_voice_persona(user: User = Depends(get_current_user)):
    """Get current user's voice persona configuration with resolved defaults."""
    user_id = user.id
    try:
        config = await config_manager.get_config(user_id)
        raw = config.get("voice_persona", {})
        return _resolve_voice_persona(raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve voice persona: {str(e)}")


@router.put("/user/voice-persona", response_model=VoicePersonaResponse)
async def update_voice_persona(
    request: VoicePersonaConfig,
    user: User = Depends(get_current_user),
):
    """Update voice persona settings. Only provided fields are updated."""
    user_id = user.id

    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No voice persona updates provided")

    # Validate persona_id
    if "persona_id" in updates and updates["persona_id"] not in PREBUILT_PERSONAS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid persona_id. Valid options: {list(PREBUILT_PERSONAS.keys())}",
        )

    # Validate voice_name
    if "voice_name" in updates and updates["voice_name"] not in VALID_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice_name. Valid options: {VALID_VOICES}",
        )

    try:
        # Merge with existing voice_persona config
        config = await config_manager.get_config(user_id)
        current_vp = config.get("voice_persona", {})

        # When switching persona, drop any stale voice override so the new persona's
        # default_voice takes effect — unless the request explicitly supplies a new voice.
        if (
            "persona_id" in updates
            and updates["persona_id"] != current_vp.get("persona_id")
            and "voice_name" not in updates
        ):
            current_vp["voice_name"] = None

        current_vp.update(updates)

        success = await config_manager.update_config(user_id, {"voice_persona": current_vp})
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update voice persona")

        return _resolve_voice_persona(current_vp)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update voice persona: {str(e)}")


@router.get("/user/config", response_model=UserConfigResponse)
async def get_user_config(user: User = Depends(get_current_user)):
    """
    Get current user configuration
    Returns default values if no configuration exists
    """
    user_id = user.id
    
    try:
        config = await config_manager.get_config(user_id)
        return UserConfigResponse(**config)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user configuration: {str(e)}"
        )


@router.put("/user/config", response_model=UserConfigResponse)
async def update_user_config(
    config_request: UserConfigRequest,
    user: User = Depends(get_current_user)
):
    """
    Update user configuration
    Only provided fields will be updated, others remain unchanged
    """
    user_id = user.id
    
    try:
        # Convert request to dictionary, excluding None values
        updates = config_request.model_dump(exclude_none=True)
        
        if not updates:
            raise HTTPException(
                status_code=400,
                detail="No configuration updates provided"
            )
        
        # Validate configuration values
        if "auto_mark_as_read" in updates and not isinstance(updates["auto_mark_as_read"], bool):
            raise HTTPException(
                status_code=400,
                detail="auto_mark_as_read must be a boolean value"
            )
        
        if "auto_send_drafts" in updates and not isinstance(updates["auto_send_drafts"], bool):
            raise HTTPException(
                status_code=400,
                detail="auto_send_drafts must be a boolean value"
            )
        
        # Update configuration
        success = await config_manager.update_config(user_id, updates)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update user configuration"
            )

        # Return updated configuration
        updated_config = await config_manager.get_config(user_id)
        return UserConfigResponse(**updated_config)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user configuration: {str(e)}"
        )


@router.delete("/user/config", response_model=DeleteConfigResponse)
async def delete_user_config(user: User = Depends(get_current_user)):
    """
    Delete user configuration
    User will revert to default configuration values
    """
    user_id = user.id

    try:
        success = await config_manager.delete_config(user_id)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete user configuration"
            )

        return DeleteConfigResponse(
            message="User configuration deleted successfully",
            user_id=user_id,
            note="Default configuration values will be used going forward"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user configuration: {str(e)}"
        )


@router.get("/user/config/{config_key}", response_model=ConfigValueResponse)
async def get_config_value(config_key: str, user: User = Depends(get_current_user)):
    """
    Get specific configuration value
    Useful for checking individual settings
    """
    user_id = user.id

    # Validate config key
    valid_keys = ["auto_mark_as_read", "auto_send_drafts", "voice_persona"]
    if config_key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration key. Valid keys: {valid_keys}"
        )

    try:
        value = await config_manager.get_config_value(user_id, config_key)

        return ConfigValueResponse(
            key=config_key,
            value=value,
            user_id=user_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve configuration value: {str(e)}"
        )