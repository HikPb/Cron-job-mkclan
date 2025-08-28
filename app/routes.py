from app import app
from flask import render_template, redirect, url_for, session, request, g, flash
from functools import wraps
from app.services.drive_service import DriveService
from app.services.api_service import *

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from werkzeug.exceptions import HTTPException
import json
import io

try:
    client_secret_json = json.loads(app.config['CLIENT_CONFIG'])
except (json.JSONDecodeError, TypeError):
    print("Lỗi: Không thể tải GOOGLE_CLIENT_SECRET_JSON từ biến môi trường.")
    client_secret_json = None

SCOPES = ["https://www.googleapis.com/auth/drive.file",  'https://www.googleapis.com/auth/userinfo.email']
CLAN_TAG = '%232QCV8UJ8Q'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'credentials' not in session:
            flash("Bạn cần đăng nhập để truy cập trang này.", "warning")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    is_logged_in = 'credentials' in session
    return render_template('index.html', is_logged_in=is_logged_in, title='Welcome')


@app.route('/auth')
def auth():
    flow = Flow.from_client_config(
        client_secret_json,
        scopes=SCOPES,
        redirect_uri=url_for('auth_callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )    
    session['state'] = state
    return redirect(authorization_url)

@app.route('/auth/callback')
def auth_callback():
    state = session.get('state')
    if not state or request.args.get('state') != state:
        flash("Trạng thái không hợp lệ.", "danger")
        return redirect(url_for('index'))

    flow = Flow.from_client_config(
        client_secret_json,
        scopes=SCOPES,
        redirect_uri=url_for('auth_callback', _external=True)
    )

    try:
        flow.fetch_token(authorization_response=request.url)        
        credentials = flow.credentials
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        user_email = user_info.get('email')

        if user_email not in app.config['AUTHORIZED_EMAILS']:
            flash("Tài khoản Google của bạn không được phép truy cập ứng dụng này.", "danger")
            session.clear()
            return redirect(url_for('index'))

        # Lưu thông tin xác thực vào session (backend)
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        with open('token.json', 'w') as f:
            json.dump(session['credentials'], f)

        flash("Đăng nhập thành công!", "success")
        return redirect(url_for('home'))
        
    except HTTPException as e:
        flash(f"Lỗi khi xác thực: {e.description}", "danger")
        session.clear()
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Đã xảy ra lỗi: {str(e)}", "danger")
        session.clear()
        return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for('index'))

@app.route('/home')
@login_required
def home():
    return render_template('home.html', title='Trang chủ')

@app.route('/update-clan-info')
@login_required
def update_clan_info():
    creds_data = session.get('credentials')
    if not creds_data:
        flash("Không tìm thấy thông tin xác thực.", "danger")
        return redirect(url_for('index'))      
    creds = Credentials(**creds_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['credentials'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }  
    try:
        drive_service = DriveService(credentials=creds)
        token = getCocApiToken()
        if token == None:
            flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
            return redirect(url_for('home'))
        clan_info = fetch_clan_info(token, CLAN_TAG)
        if clan_info == None:
            flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
            return redirect(url_for('home'))

        with open(app.config['CLAN_INFO_FILE_NAME'], 'w') as f:
            json.dump(clan_info, f, indent=4)
        uploaded_response = drive_service.upload_json_to_drive(app.config['CLAN_INFO_FILE_NAME'], app.config['DRIVE_FOLDER_ID'], num_backups_to_keep=1)
        if uploaded_response.status == "error":
            flash(f"File {app.config['CLAN_INFO_FILE_NAME']}: Upload thất bại! Error: {uploaded_response.message}", "danger")
        flash(f"Đã tải thành công tệp {app.config['CLAN_INFO_FILE_NAME']} với ID: {uploaded_response.id} lên Google Drive!", "success")
        return redirect(url_for('home'))    
    except Exception as e:
        flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/update-warlog')
@login_required
def update_warlog():
    creds_data = session.get('credentials')
    if not creds_data:
        flash("Không tìm thấy thông tin xác thực.", "danger")
        return redirect(url_for('index'))      
    creds = Credentials(**creds_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['credentials'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }  
    try:
        drive_service = DriveService(credentials=creds)
        token = getCocApiToken()
        if token == None:
            flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
            return redirect(url_for('home'))
        warlog = fetch_war_log(token, CLAN_TAG, drive_service)
        if warlog == None:
            flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
            return redirect(url_for('home'))

        with open(app.config['WARLOG_FILE_NAME'], 'w') as f:
            json.dump(warlog, f, indent=4)
        uploaded_response = drive_service.upload_json_to_drive(app.config['WARLOG_FILE_NAME'], app.config['DRIVE_FOLDER_ID'], num_backups_to_keep=1)
        if uploaded_response.status == "error":
            flash(f"File {app.config['WARLOG_FILE_NAME']}: Upload thất bại! Error: {uploaded_response.message}", "danger")
        flash(f"Đã tải thành công tệp {app.config['WARLOG_FILE_NAME']} với ID: {uploaded_response.id} lên Google Drive!", "success")
        return redirect(url_for('home'))    
    except Exception as e:
        flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/api/update-clan-info')
def update_clan_info_api():
    secret_from_request = request.args.get('key')
    print(f"Key: {secret_from_request} - {app.config['CRON_SECRET_KEY']}")
    if secret_from_request != app.config['CRON_SECRET_KEY']:
        print("Unauthorized access. Secret key does not match.")
        return {"status": "error", "message": "Unauthorized access"}, 403
    try:
        with open('token.json', 'r') as f:
            credentials_data = json.load(f)
    except FileNotFoundError:
        print("token.json not found. Please log in first to create the file.")
        return {"status": "error", "message": "Token file not found. Please log in first."}, 401
    credentials = Credentials(**credentials_data)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(request.url)
        with open('token.json', 'w') as f:
            json.dump({
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }, f)
    try:
        drive_service = DriveService(credentials=credentials)
        token = getCocApiToken()
        if token == None:
            return {"status": "error" ,"message": "Coc API Token is None"}
        clan_info = fetch_clan_info(token, CLAN_TAG)
        if clan_info == None:
            return {"status": "error" ,"message": "Data is None"}
        with open(app.config['CLAN_INFO_FILE_NAME'], 'w') as f:
            json.dump(clan_info, f, indent=4)
        uploaded_response = drive_service.upload_json_to_drive(app.config['CLAN_INFO_FILE_NAME'], app.config['DRIVE_FOLDER_ID'], num_backups_to_keep=1)
        return uploaded_response, 200    
    except Exception as e:
        return {"status": "error" ,"message": e}

@app.route('/api/update-war-log')
def update_war_log_api():
    secret_from_request = request.args.get('key')
    if secret_from_request != app.config['CRON_SECRET_KEY']:
        print("Unauthorized access. Secret key does not match.")
        return {"status": "error", "message": "Unauthorized access"}, 403
    try:
        with open('token.json', 'r') as f:
            credentials_data = json.load(f)
    except FileNotFoundError:
        print("token.json not found. Please log in first to create the file.")
        return {"status": "error", "message": "Token file not found. Please log in first."}, 401
    credentials = Credentials(**credentials_data)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(request.url)
        with open('token.json', 'w') as f:
            json.dump({
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }, f)
    try:
        drive_service = DriveService(credentials=credentials)
        token = getCocApiToken()
        if token == None:
            return {"status": "error" ,"message": "Coc API Token is None"}
        warlog = fetch_war_log(token, CLAN_TAG, drive_service)
        if warlog == None:
            return {"status": "error" ,"message": "Data is None"}
        with open(app.config['WARLOG_FILE_NAME'], 'w') as f:
            json.dump(warlog, f, indent=4)
        uploaded_response = drive_service.upload_json_to_drive(app.config['WARLOG_FILE_NAME'], app.config['DRIVE_FOLDER_ID'], num_backups_to_keep=1)
        return uploaded_response, 200    
    except Exception as e:
        return {"status": "error" ,"message": e}

