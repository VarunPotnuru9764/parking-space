import bcrypt
from jose import JWTError, jwt
from dotenv import dotenv_values
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import get_db
from app.models.users import User

bearer_scheme = HTTPBearer()
config = dotenv_values(".env")
SECRET_KEY = config["SECRET_KEY"]
ALGORITHM = "HS256"
EXPTOKEN = 60

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    return hashed_password.decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    password_bytes = password.encode("utf-8")
    hash_bytes = password_hash.encode("utf-8")

    return bcrypt.checkpw(password_bytes, hash_bytes)

def create_access_token(user_id: int, role: str) -> str:
    expire_time = datetime.now(timezone.utc) + timedelta(minutes = EXPTOKEN)

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire_time
    }

    return jwt.encode(payload, SECRET_KEY, algorithm = ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code = 401,
        detail = "Could not validate credentials",
        headers = {"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.user_id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user