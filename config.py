import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave_super_segura'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+mysqlconnector://jmu_user:Jmu12345*@127.0.0.1/jmu_bd_nueva'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}