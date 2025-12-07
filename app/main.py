from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db, engine, Base, database_mongo, redis_client
from app import models, schemas

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
    
    # AQUÍ OCURRE LA MAGIA DEL REQUISITO
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