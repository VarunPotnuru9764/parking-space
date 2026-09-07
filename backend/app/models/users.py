from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key = True, index = True, autoincrement = True)
    name = Column(String(100), nullable = False)
    email = Column(String(150), unique = True, nullable = False)
    password_hash = Column(String(255), nullable = False)
    role = Column(Enum("user", "admin"), nullable = False, default = "user")
    created_at = Column(DateTime, server_default = func.now())