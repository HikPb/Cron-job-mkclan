from flask import Flask
from flask_caching import Cache
from dotenv import load_dotenv
import os

load_dotenv()
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
app = Flask(__name__)
cache.init_app(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['SCOPES'] = os.environ.get('GOOGLE_SCOPES')
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
app.config['MEMBER_EXCLUDED_KEYS'] = os.environ.get('MEMBER_EXCLUDED_KEYS')

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from app import routes