from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db, engine, Base, database_mongo, redis_client
from app import models, schemas
from bson import ObjectId
import json

# Crear las tablas en PostgreSQL automáticamente
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Multibase")

# --- RUTAS PARA USUARIOS (POSTGRESQL) ---

# 1. POST: Crear Usuario
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Verificar si el email ya existe
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    # Crear objeto usuario
    new_user = models.User(
        name=user.name, 
        email=user.email, 
        password=user.password, # En la vida real, esto se encripta
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# 2. GET: Obtener todos (Solo los NO borrados)
@app.get("/users/", response_model=list[schemas.UserResponse])
def read_users(db: Session = Depends(get_db)):
    # Filtramos por is_active == True. Los "borrados" no aparecen.
    users = db.query(models.User).filter(models.User.is_active == True).all()
    return users

# 3. GET: Obtener uno por ID
@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    # Si no existe o está marcado como borrado, lanzamos 404
    if user is None or user.is_active == False:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

# 4. DELETE: Borrado Lógico
@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # No usamos db.delete(user). Solo cambiamos el estado.
    user.is_active = False 
    db.commit()
    
    return {"message": "Usuario eliminado lógicamente (Soft Delete)"}

# 5. PATCH: Restaurar Usuario (Opcional, pero útil para probar)
@app.patch("/users/{user_id}/restore")
def restore_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_active = True
        db.commit()
        return {"message": "Usuario restaurado"}
    return {"error": "Usuario no encontrado"}

# --- RUTAS PARA RESEÑAS (MONGODB) ---

# 1. POST: Crear una Reseña
@app.post("/reviews/", response_model=schemas.ReviewResponse)
async def create_review(review: schemas.ReviewCreate):
    review_dict = review.model_dump()
    review_dict["active"] = True  # Por defecto está activa
    
    # Insertar en la colección 'reviews'
    result = await database_mongo.reviews.insert_one(review_dict)
    
    # Recuperar el objeto creado para devolverlo (convertimos _id a str)
    new_review = await database_mongo.reviews.find_one({"_id": result.inserted_id})
    
    return schemas.ReviewResponse(
        id=str(new_review["_id"]),
        user_email=new_review["user_email"],
        product_name=new_review["product_name"],
        content=new_review["content"],
        rating=new_review["rating"],
        active=new_review["active"]
    )

# 2. GET: Leer todas las reseñas activas
@app.get("/reviews/", response_model=list[schemas.ReviewResponse])
async def read_reviews():
    reviews = []
    # Buscamos solo donde "active" sea true
    cursor = database_mongo.reviews.find({"active": True})
    
    async for doc in cursor:
        reviews.append(schemas.ReviewResponse(
            id=str(doc["_id"]),
            user_email=doc["user_email"],
            product_name=doc["product_name"],
            content=doc["content"],
            rating=doc["rating"],
            active=doc["active"]
        ))
    return reviews

# 3. GET: Leer una reseña por ID
@app.get("/reviews/{review_id}", response_model=schemas.ReviewResponse)
async def read_review(review_id: str):
    # Verificamos que el ID tenga formato válido de Mongo
    if not ObjectId.is_valid(review_id):
        raise HTTPException(status_code=400, detail="ID de Mongo inválido")
        
    review = await database_mongo.reviews.find_one({"_id": ObjectId(review_id), "active": True})
    
    if review is None:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
        
    return schemas.ReviewResponse(
        id=str(review["_id"]),
        user_email=review["user_email"],
        product_name=review["product_name"],
        content=review["content"],
        rating=review["rating"],
        active=review["active"]
    )

# 4. DELETE: Borrado Lógico en Mongo
@app.delete("/reviews/{review_id}")
async def delete_review(review_id: str):
    if not ObjectId.is_valid(review_id):
        raise HTTPException(status_code=400, detail="ID de Mongo inválido")

    # BUSCAR Y ACTUALIZAR (No eliminar)
    result = await database_mongo.reviews.update_one(
        {"_id": ObjectId(review_id)},
        {"$set": {"active": False}}  # Aquí está la magia del borrado lógico
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Reseña no encontrada o ya eliminada")
        
    return {"message": "Reseña eliminada lógicamente (Soft Delete en Mongo)"}

# 5. PATCH: Actualizar contenido de la reseña
@app.patch("/reviews/{review_id}")
async def update_review_content(review_id: str, content: str):
    if not ObjectId.is_valid(review_id):
        raise HTTPException(status_code=400, detail="ID de Mongo inválido")
        
    result = await database_mongo.reviews.update_one(
        {"_id": ObjectId(review_id), "active": True},
        {"$set": {"content": content}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No se pudo actualizar (quizás no existe)")
        
    return {"message": "Contenido actualizado"}

    # --- RUTAS PARA CARRITO DE COMPRAS (REDIS) ---

# 1. POST: Guardar/Actualizar el carrito de un usuario
@app.post("/cart/{user_id}", response_model=schemas.CartResponse)
def save_cart(user_id: str, cart: schemas.CartCreate):
    # Estructura que guardaremos en Redis
    cart_data = {
        "user_id": user_id,
        "items": [item.model_dump() for item in cart.items],
        "is_active": True # Para cumplir con el borrado lógico
    }
    
    # Guardamos en Redis.
    # La CLAVE será "cart_usuarioID"
    # El VALOR es el JSON convertido a string
    redis_client.set(f"cart_{user_id}", json.dumps(cart_data))
    
    return cart_data

# 2. GET: Obtener el carrito
@app.get("/cart/{user_id}", response_model=schemas.CartResponse)
def get_cart(user_id: str):
    # Buscamos en Redis por la clave
    data = redis_client.get(f"cart_{user_id}")
    
    if data is None:
        raise HTTPException(status_code=404, detail="Carrito vacío o no encontrado")
    
    cart_dict = json.loads(data)
    
    # Verificar borrado lógico
    if not cart_dict.get("is_active"):
        raise HTTPException(status_code=404, detail="El carrito fue eliminado")
        
    return cart_dict

# 3. DELETE: Borrado Lógico en Redis
@app.delete("/cart/{user_id}")
def delete_cart(user_id: str):
    # 1. Obtener el carrito actual
    data = redis_client.get(f"cart_{user_id}")
    
    if data is None:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    cart_dict = json.loads(data)
    
    # 2. Cambiar el flag a False (Borrado Lógico)
    cart_dict["is_active"] = False
    
    # 3. Sobreescribir en Redis con el nuevo estado
    redis_client.set(f"cart_{user_id}", json.dumps(cart_dict))
    
    return {"message": "Carrito eliminado lógicamente (Soft Delete en Redis)"}