from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Session, select, col
from sqlalchemy import func

from Salva.models import (
    User,
    UserPreferences
)

class UserRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son email."""
        return self.session.exec(select(User).where(User.email == email)).first()

    def create_user(self, 
                    email: str,
                    **kwargs) -> User:
        """Crée un nouvel utilisateur avec les préférences par défaut."""
        user = User(email=email, **kwargs)

        exist_user = self.get_user_by_email(email)
        if exist_user:
            raise ValueError(f"Cette utilisateur existe déjà : {email}")
        
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        return user

