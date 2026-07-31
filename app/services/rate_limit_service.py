from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User

class LoginAttemptTracker:
    _attempts = {}
    
    def __init__(self, max_attempts: int = 5, block_duration: int = 15):
        self.max_attempts = max_attempts
        self.block_duration = block_duration  # minutes
    
    def track_attempt(self, email: str) -> bool:
        """Returns True if allowed, False if blocked"""
        now = datetime.utcnow()
        key = email.lower()
        
        if key not in self._attempts:
            self._attempts[key] = {'count': 1, 'first_attempt': now}
            return True
        
        attempts = self._attempts[key]
        
        # Reset after block duration
        if (now - attempts['first_attempt']) > timedelta(minutes=self.block_duration):
            self._attempts[key] = {'count': 1, 'first_attempt': now}
            return True
        
        if attempts['count'] >= self.max_attempts:
            return False
        
        attempts['count'] += 1
        return True
    
    def reset_attempts(self, email: str):
        key = email.lower()
        if key in self._attempts:
            del self._attempts[key]

login_tracker = LoginAttemptTracker()