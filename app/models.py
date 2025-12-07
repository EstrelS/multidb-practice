from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    
    # ESTO ES LA CLAVE DEL PROYECTO: Borrado Lógico
    # Si is_active es False, el usuario está "borrado" para el sistema, pero sigue en la BD.
    is_active = Column(Boolean, default=True)