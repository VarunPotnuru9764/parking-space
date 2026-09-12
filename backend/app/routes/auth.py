from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.users import User
from app.schemas.auth import UserRegister, UserLogin
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
@router.post("/register", status_code = 201)
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    new_user = User(
        name = user.name,
        email = user.email,
        password_hash = hash_password(user.password),
        role = "user"
    )

    try:
        db.add(new_user)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code = 409,
            detail = "A user with this email already exists"
        )
    
    return {
        "message": "User registered successfully",
        "user_id": new_user.user_id
    }

@router.post("/login", status_code = 200)
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user is None:
        raise HTTPException(
            status_code = 401,
            detail = "Invalid email or password"
        )

    if not verify_password(user.password, existing_user.password_hash):
        raise HTTPException(
            status_code = 401,
            detail = "Invalid email or password"
        )

    access_token = create_access_token(
        existing_user.user_id,
        existing_user.role
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    }