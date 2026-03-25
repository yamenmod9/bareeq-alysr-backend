"""
Authentication Router
POST /auth/login - Login endpoint
POST /auth/register - Registration endpoint (bonus)
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import app_context
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
    UpdateProfileRequest,
    ChangePasswordRequest,
    Enable2FARequest,
    TwoFactorResponse
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService
from app.utils.auth import get_current_user, TokenInfo, create_access_token
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=APIResponse[LoginResponse],
    summary="User Login",
    description="""
    Authenticate customers & merchants via Nafath simulation (email/password).
    
    Returns JWT token valid for 24 hours.
    
    **Nafath Simulation**: Optionally provide `national_id` for verification.
    """
)
async def login(request: LoginRequest):
    """
    Login endpoint - authenticate user and return JWT token
    
    - **email**: User's email address
    - **password**: User's password
    - **national_id**: Optional Saudi National ID (10 digits) for Nafath simulation
    """
    try:
        with app_context():
            user, token = AuthService.authenticate(
                email=request.email,
                password=request.password,
                national_id=request.national_id
            )
            
            # Build user response
            user_response = UserResponse.model_validate(user)
            
            login_response = LoginResponse(
                access_token=token,
                token_type="bearer",
                expires_in=TokenInfo.get_expiry_seconds(),
                user=user_response
            )
            
            return success_response(
                data=login_response.model_dump(),
                message="Login successful"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post(
    "/register",
    response_model=APIResponse[RegisterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Register a new customer or merchant account."
)
async def register(request: RegisterRequest):
    """
    Registration endpoint - create new user account
    
    - **email**: User's email address
    - **password**: Password (min 6 characters)
    - **full_name**: User's full name
    - **phone**: Optional phone number
    - **role**: 'customer' or 'merchant'
    - **national_id**: Optional Saudi National ID
    - **shop_name**: Required for merchants
    """
    try:
        with app_context():
            if request.role == "merchant":
                if not request.shop_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="shop_name is required for merchant registration"
                    )
                
                user, merchant = AuthService.register_merchant(
                    email=request.email,
                    password=request.password,
                    full_name=request.full_name,
                    shop_name=request.shop_name,
                    phone=request.phone_number,
                    national_id=request.national_id,
                    shop_name_ar=request.shop_name_ar,
                    commercial_registration=request.commercial_registration,
                    vat_number=request.vat_number,
                    business_phone=request.business_phone,
                    business_email=request.business_email,
                    address=request.address,
                    city=request.city
                )
            else:
                user, customer = AuthService.register_customer(
                    email=request.email,
                    password=request.password,
                    full_name=request.full_name,
                    phone=request.phone_number,
                    national_id=request.national_id
                )
            
            # Create access token for auto-login
            token = create_access_token(
                user_id=user.id,
                email=user.email,
                role=user.role
            )
            
            # Build user response
            user_response = UserResponse.model_validate(user)
            
            register_response = RegisterResponse(
                access_token=token,
                token_type="bearer",
                expires_in=TokenInfo.get_expiry_seconds(),
                user=user_response,
                message="Registration successful"
            )
            
            return success_response(
                data=register_response.model_dump(),
                message="Registration successful"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get(
    "/me",
    response_model=APIResponse[UserResponse],
    summary="Get Current User",
    description="Get the currently authenticated user's information."
)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current user info endpoint
    
    Requires authentication (Bearer token)
    """
    try:
        with app_context():
            user = AuthService.get_user_by_id(current_user["user_id"])
            
            return success_response(
                data=user.to_dict(),
                message="User info retrieved"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/verify-nafath",
    response_model=APIResponse,
    summary="Verify Nafath",
    description="Simulate Nafath (Saudi government) verification."
)
async def verify_nafath(
    national_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Nafath verification simulation
    
    - **national_id**: Saudi National ID (10 digits)
    """
    try:
        with app_context():
            if len(national_id) != 10 or not national_id.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="National ID must be exactly 10 digits"
                )
            
            result = AuthService.simulate_nafath_verification(
                user_id=current_user["user_id"],
                national_id=national_id
            )
            
            return success_response(
                data={"verified": result},
                message="Nafath verification successful"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/profile",
    response_model=APIResponse[UserResponse],
    summary="Update Profile",
    description="Update the current user's profile information."
)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update user profile endpoint
    
    - **full_name**: New full name (optional)
    - **phone**: New phone number (optional)
    - **email**: New email address (optional)
    """
    try:
        with app_context():
            user = AuthService.update_profile(
                user_id=current_user["user_id"],
                full_name=request.full_name,
                phone=request.phone,
                email=request.email
            )
            
            return success_response(
                data=user.to_dict(),
                message="Profile updated successfully"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/change-password",
    response_model=APIResponse,
    summary="Change Password",
    description="Change the current user's password."
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Change password endpoint
    
    - **current_password**: Current password
    - **new_password**: New password (min 6 characters)
    - **confirm_password**: Confirm new password
    """
    try:
        if request.new_password != request.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New passwords do not match"
            )
        
        with app_context():
            AuthService.change_password(
                user_id=current_user["user_id"],
                old_password=request.current_password,
                new_password=request.new_password
            )
            
            return success_response(
                data={"changed": True},
                message="Password changed successfully"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/2fa",
    response_model=APIResponse[TwoFactorResponse],
    summary="Toggle 2FA",
    description="Enable or disable two-factor authentication."
)
async def toggle_2fa(
    request: Enable2FARequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Enable or disable 2FA endpoint
    
    - **enabled**: True to enable, False to disable
    """
    try:
        with app_context():
            if request.enabled:
                result = AuthService.enable_2fa(current_user["user_id"])
            else:
                result = AuthService.disable_2fa(current_user["user_id"])
            
            return success_response(
                data=result,
                message="2FA " + ("enabled" if request.enabled else "disabled") + " successfully"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
