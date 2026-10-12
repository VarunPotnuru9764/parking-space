import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from secrets import compare_digest

from app.database import get_db
from app.config import get_required_setting, get_setting
from app.models.users import User

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)
SECRET_KEY = get_required_setting("SECRET_KEY")
DETECTION_API_TOKEN = get_setting("DETECTION_API_TOKEN")
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

    try:
        resolved_user_id = int(user_id)
    except (TypeError, ValueError):
        raise credentials_exception
    user = db.query(User).filter(User.user_id == resolved_user_id).first()
    if user is None:
        raise credentials_exception

    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return current_user

def require_admin_or_detection_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    detection_token: str | None = Header(default=None, alias="X-Detection-Token"),
    db: Session = Depends(get_db),
):
    if DETECTION_API_TOKEN and detection_token and compare_digest(detection_token, DETECTION_API_TOKEN):
        return None
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Administrator or detection-service authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    current_user = get_current_user(credentials, db)
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return current_user
