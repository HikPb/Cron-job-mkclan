from flask import Flask
from flask_caching import Cache
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import os

load_dotenv()

# Thiết lập các biến môi trường cho OAuthlib
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
cache.init_app(app)

# Cấu hình Logger cho ứng dụng
file_handler = RotatingFileHandler('app.log', maxBytes=1024000, backupCount=5)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Cấu hình ứng dụng từ biến môi trường
app.secret_key = os.environ.get('SECRET_KEY')
app.config['AUTHORIZED_EMAILS'] = os.environ.get('AUTHORIZED_EMAILS')
app.config['DRIVE_FOLDER_ID'] = os.environ.get('DRIVE_FOLDER_ID')
app.config['WL_DRIVE_FOLDER_ID'] = os.environ.get('WL_DRIVE_FOLDER_ID')
app.config['WL_RP_DRIVE_FOLDER_ID'] = os.environ.get('WL_RP_DRIVE_FOLDER_ID')
app.config['CLIENT_CONFIG'] = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
app.config['CRON_SECRET_KEY'] = os.environ.get('CRON_SECRET_KEY')
app.config['EMAIL'] = os.environ.get('COC_EMAIL')
app.config['PASSWORD'] = os.environ.get('COC_PASSWORD')
app.config['CLAN_INFO_FILE_NAME'] = os.environ.get('CLAN_INFO_FILE_NAME')
app.config['WARLOG_FILE_NAME'] = os.environ.get('WARLOG_FILE_NAME')

from app import routes