import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

load_dotenv(Path(__file__).with_name(".env"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./alumni_connect.db")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-before-production")
if ENVIRONMENT in {"production", "preview"} or os.getenv("VERCEL_ENV"):
    if DATABASE_URL.startswith("sqlite:"):
        raise RuntimeError("DATABASE_URL must point to Neon/PostgreSQL outside local development")
    if JWT_SECRET == "change-this-before-production" or len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must be a unique value of at least 32 characters")
ALGORITHM = "HS256"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class Base(DeclarativeBase): pass
class Alumni(Base):
    __tablename__ = "alumni"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    student_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    degree: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    major: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    batch_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")
    directory_visible: Mapped[str] = mapped_column(String(20), default="alumni")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    degree: Optional[str] = None
    batch: Optional[int] = None
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
class ProfileUpdate(BaseModel):
    student_number: Optional[str] = None; degree: Optional[str] = None; major: Optional[str] = None
    batch_year: Optional[int] = None; job_title: Optional[str] = None; company: Optional[str] = None
    location: Optional[str] = None; bio: Optional[str] = None; directory_visible: Optional[str] = None

app = FastAPI(title="ISPSC Alumni Connect API")
allowed_origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()
def public(a: Alumni):
    return {"id":a.id,"name":a.name,"degree":a.degree,"major":a.major,"batch_year":a.batch_year,"job_title":a.job_title,"company":a.company,"location":a.location,"bio":a.bio,"role":a.role,"directory_visible":a.directory_visible}
def token_for(a: Alumni):
    exp=datetime.now(timezone.utc)+timedelta(days=7)
    return jwt.encode({"sub":str(a.id),"role":a.role,"exp":exp},JWT_SECRET,algorithm=ALGORITHM)
def current_user(credentials: HTTPAuthorizationCredentials=Depends(security), db: Session=Depends(db_session)):
    try: payload=jwt.decode(credentials.credentials,JWT_SECRET,algorithms=[ALGORITHM]); uid=int(payload.get("sub"))
    except (JWTError, TypeError, ValueError): raise HTTPException(401,"Invalid session")
    user=db.get(Alumni,uid)
    if not user: raise HTTPException(401,"Account not found")
    return user
def admin_only(user: Alumni=Depends(current_user)):
    if user.role != "admin": raise HTTPException(403,"Administrator access required")
    return user

@app.get("/api/health")
def health(): return {"status":"ok"}
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session=Depends(db_session)):
    if db.scalar(select(Alumni).where(Alumni.email==data.email)): raise HTTPException(409,"Email is already registered")
    alum=Alumni(name=data.name,email=data.email,password_hash=pwd_context.hash(data.password),degree=data.degree,batch_year=data.batch,consent_at=datetime.now(timezone.utc))
    db.add(alum); db.commit(); db.refresh(alum)
    return {"access_token":token_for(alum),"token_type":"bearer","user":public(alum)}
@app.post("/api/auth/login")
def login(data: LoginIn, db: Session=Depends(db_session)):
    alum=db.scalar(select(Alumni).where(Alumni.email==data.email))
    if not alum or not pwd_context.verify(data.password,alum.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":token_for(alum),"token_type":"bearer","user":public(alum)}
@app.get("/api/me")
def me(user: Alumni=Depends(current_user)): return public(user)
@app.patch("/api/me")
def update_me(data: ProfileUpdate, db: Session=Depends(db_session), user: Alumni=Depends(current_user)):
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(user,k,v)
    db.commit(); db.refresh(user); return public(user)
@app.get("/api/alumni")
def directory(q: str="", batch: Optional[int]=None, db: Session=Depends(db_session), _: Alumni=Depends(current_user)):
    stmt=select(Alumni).where(Alumni.directory_visible != "private")
    if batch: stmt=stmt.where(Alumni.batch_year==batch)
    if q:
        term=f"%{q.lower()}%"
        stmt=stmt.where((Alumni.name.ilike(term)) | (Alumni.degree.ilike(term)) | (Alumni.job_title.ilike(term)) | (Alumni.company.ilike(term)))
    return [public(a) for a in db.scalars(stmt.order_by(Alumni.name).limit(100)).all()]
@app.get("/api/admin/overview")
def admin_overview(db: Session=Depends(db_session), _: Alumni=Depends(admin_only)):
    people=db.scalars(select(Alumni)).all()
    return {"total_profiles":len(people),"employment_confirmed":sum(bool(x.job_title) for x in people),"recent": [public(x) for x in people[-10:]]}
