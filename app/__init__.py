from flask import Flask
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['SCOPES'] = os.getenv('GOOGLE_SCOPES')
app.config['AUTHORIZED_EMAILS'] = os.getenv('AUTHORIZED_EMAILS')
app.config['DRIVE_FOLDER_ID'] = os.getenv('DRIVE_FOLDER_ID')
app.config['CLIENT_CONFIG'] = os.getenv('GOOGLE_CLIENT_SECRET_JSON')

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from app import routes