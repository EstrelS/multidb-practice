from pydantic import BaseModel, EmailStr

# Esquema para recibir datos (Crear Usuario)
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

# Esquema para responder datos (Ocultamos el password)
class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_active: bool

    class Config:
        from_attributes = True # Antes conocido como orm_mode