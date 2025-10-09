from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional

from app.auth import get_current_user
from app.models.user import User
from app.schemas.config import UserConfigRequest, UserConfigResponse, DeleteConfigResponse, ConfigValueResponse
from app.services.user_config_manager import UserConfigManager

router = APIRouter()

# Initialize config manager
config_manager = UserConfigManager()


@router.get("/user/config", response_model=UserConfigResponse)
async def get_user_config(user: User = Depends(get_current_user)):
    """
    Get current user configuration
    Returns default values if no configuration exists
    """
    user_id = user.id
    
    try:
        config = config_manager.get_config(user_id)
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
        success = config_manager.update_config(user_id, updates)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update user configuration"
            )
        
        # Return updated configuration
        updated_config = config_manager.get_config(user_id)
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
        success = config_manager.delete_config(user_id)

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
    valid_keys = ["auto_mark_as_read", "auto_send_drafts"]
    if config_key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration key. Valid keys: {valid_keys}"
        )

    try:
        value = config_manager.get_config_value(user_id, config_key)

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