from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base  

# ============ SQLAlchemy Models ============

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="organization")
    projects = relationship("Project", back_populates="organization")


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    github_token = Column(String(500), nullable=True)
    github_username = Column(String(255), nullable=True)
    github_repo = Column(String(255), nullable=True)
    github_connected_at = Column(DateTime, nullable=True)
    
    organization = relationship("Organization", back_populates="users")
    projects = relationship("Project", back_populates="owner")


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    settings = Column(JSON, default={})
    
    organization = relationship("Organization", back_populates="projects")
    owner = relationship("User", back_populates="projects")
    errors = relationship("Error", back_populates="project")
    api_keys = relationship("APIKey", back_populates="project")


class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    error_count = Column(Integer, default=0)
    last_used = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    project = relationship("Project", back_populates="api_keys")
    errors = relationship("Error", back_populates="api_key")


class Error(Base):
    __tablename__ = "errors"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(255), nullable=True)
    user_email = Column(String(255), nullable=True)
    type = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    severity = Column(String(20), default="error")
    url = Column(Text)
    line_no = Column(Integer)
    col_no = Column(Integer)
    file_name = Column(String(1024))
    method_name = Column(String(255))
    environment = Column(String(50), default="production")
    release_version = Column(String(100))
    extra_data = Column(JSON, default={})
    status = Column(String(20), default="unresolved")
    has_ai_analysis = Column(Boolean, default=False)
    fixed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="errors")
    ai_analysis = relationship("AIAnalysis", back_populates="error", uselist=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True)
    api_key = relationship("APIKey", back_populates="errors")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    error_id = Column(Integer, ForeignKey("errors.id"), nullable=False)
    root_cause = Column(Text)
    suggested_fix = Column(Text)
    fix_explanation = Column(Text)
    confidence = Column(Float)
    fix_pr_url = Column(Text)
    status = Column(String(20), default="pending")
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    fixed_at = Column(DateTime)
    
    error = relationship("Error", back_populates="ai_analysis")