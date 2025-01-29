from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

load_dotenv()

security = HTTPBasic()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    username = os.getenv("API_USERNAME", "admin")
    stored_password_hash = os.getenv("API_PASSWORD_HASH")
    
    if stored_password_hash is None:
        # If no password hash is set, create one from the default or environment password
        default_password = os.getenv("API_PASSWORD", "changeme")
        stored_password_hash = get_password_hash(default_password)
    
    if not (credentials.username == username and 
            verify_password(credentials.password, stored_password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username