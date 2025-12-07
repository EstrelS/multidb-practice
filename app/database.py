from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from motor.motor_asyncio import AsyncIOMotorClient
import redis

# ---------------------------------------------------------
# 1. Configuración de PostgreSQL (Relacional)
# ---------------------------------------------------------
# Formato: postgresql://usuario:password@host:puerto/nombre_bd
SQLALCHEMY_DATABASE_URL = "postgresql://user_pg:password_pg@localhost:5433/tienda_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependencia para obtener la sesión de BD en cada petición
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------
# 2. Configuración de MongoDB (NoSQL)
# ---------------------------------------------------------
# Formato: mongodb://usuario:password@host:puerto
MONGO_URL = "mongodb://user_mongo:password_mongo@localhost:27017"

client_mongo = AsyncIOMotorClient(MONGO_URL)
database_mongo = client_mongo.tienda_mongo_db  # Nombre de la BD en Mongo

# ---------------------------------------------------------
# 3. Configuración de Redis (Clave-Valor)
# ---------------------------------------------------------
# decode_responses=True hace que Redis nos devuelva texto en lugar de bytes
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)