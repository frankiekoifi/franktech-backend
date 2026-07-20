from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base  

# ============ SQLAlchemy Models ============

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_errors_ingested = Column(Integer, default=0)
    
    github_token = Column(String(500), nullable=True)
    github_username = Column(String(255), nullable=True)
    github_repo = Column(String(255), nullable=True)
    github_connected_at = Column(DateTime, nullable=True)
    email_notifications = Column(Boolean, default=True)
    role = Column(String(50), default="member")
    
    organization = relationship("Organization", foreign_keys=[organization_id], back_populates="users")
    owned_organizations = relationship("Organization", foreign_keys="Organization.owner_id", back_populates="owner")
    projects = relationship("Project", back_populates="owner")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.user_id", back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_organizations")
    users = relationship("User", foreign_keys="User.organization_id", back_populates="organization")
    projects = relationship("Project", back_populates="organization")
    invites = relationship("OrganizationInvite", back_populates="organization")


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    token = Column(String(255), unique=True, nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="invites")
    inviter = relationship("User", foreign_keys=[invited_by])


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
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.project_id", back_populates="project")


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
    session_replay = Column(JSON, nullable=True)
    has_session_replay = Column(Boolean, default=False)


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

class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    
    type = Column(String)  
    url = Column(String, nullable=True)
    method = Column(String, nullable=True)
    duration = Column(Float)
    status = Column(Integer, nullable=True)
    
    metrics = Column(JSON, nullable=True)  
    
    environment = Column(String)
    release_version = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    user_email = Column(String, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) 
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    action = Column(String(100), nullable=False)  
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[user_id], back_populates="audit_logs")
    project = relationship("Project", foreign_keys=[project_id], back_populates="audit_logs")
    
    __table_args__ = (
        Index('idx_audit_logs_project_timestamp', 'project_id', 'timestamp'),
        Index('idx_audit_logs_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_logs_action', 'action'),
        Index('idx_audit_logs_timestamp', 'timestamp'),
    )