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

# --- ESQUEMAS PARA MONGODB (RESEÑAS) ---

class ReviewCreate(BaseModel):
    user_email: EmailStr  # Quién escribe la reseña
    product_name: str     # Qué producto reseña
    content: str          # El texto
    rating: int           # Calificación 1-5

class ReviewResponse(BaseModel):
    id: str               # Mongo devuelve el ID como string aquí
    user_email: EmailStr
    product_name: str
    content: str
    rating: int
    active: bool          # Para el borrado lógico

    class Config:
        from_attributes = True

    # --- ESQUEMAS PARA REDIS (CARRITO) ---

class CartItem(BaseModel):
    product_name: str
    quantity: int

class CartCreate(BaseModel):
    items: list[CartItem]

class CartResponse(BaseModel):
    user_id: str
    items: list[CartItem]
    is_active: bool