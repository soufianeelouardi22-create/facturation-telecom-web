import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

_default_db       = os.path.join(os.path.dirname(__file__), 'config', 'database_web.db')
_default_settings = os.path.join(BASE_DIR, 'config', 'settings.json')

class Config:
    SECRET_KEY    = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production-2026')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', _default_db)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.environ.get('DATABASE_PATH', _default_db)}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SETTINGS_PATH = os.environ.get('SETTINGS_PATH', _default_settings)
    EXPORTS_PATH  = os.path.join(BASE_DIR, 'data', 'exports')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
