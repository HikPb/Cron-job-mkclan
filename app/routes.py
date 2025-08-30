from . import app
from flask import render_template, redirect, url_for, session, request, flash
from functools import wraps
from .services.drive_service import DriveService
from .services.api_service import getCocApiToken, fetch_clan_info, fetch_war_log
from .services.data_processor import process_wldata_and_upload

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from werkzeug.exceptions import HTTPException
import json

try:
    client_secret_json = json.loads(app.config['CLIENT_CONFIG'])
except (json.JSONDecodeError, TypeError):
    app.logger.error("Không thể tải GOOGLE_CLIENT_SECRET_JSON từ biến môi trường.")
    client_secret_json = None

SCOPES = ["https://www.googleapis.com/auth/drive.file",  'https://www.googleapis.com/auth/userinfo.email']
CLAN_TAG = '#2QCV8UJ8Q'

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

def process_data_and_upload(data_type, credentials):
    try:
        coc_token_res = getCocApiToken()
        if "error" in coc_token_res:
            return {"error": coc_token_res["error"]}
        drive_service = DriveService(credentials=credentials)
        if data_type == 'clan_info':
            data_res = fetch_clan_info(coc_token_res["data"], CLAN_TAG)
            file_name = app.config['CLAN_INFO_FILE_NAME']
        elif data_type == 'war_log':
            data_res = fetch_war_log(coc_token_res["data"], CLAN_TAG, drive_service)
            file_name = app.config['WARLOG_FILE_NAME']
        else:
            return {"error": "Invalid data type"}
        if "error" in data_res:
            return {"error": data_res["error"]}

        # Sử dụng io.StringIO để tránh ghi tệp ra đĩa
        data_str = json.dumps(data_res["data"], indent=4)
        uploaded_res = drive_service.upload_string_to_drive(data_str, file_name, app.config['DRIVE_FOLDER_ID'], num_backups_to_keep=1)
        
        return uploaded_res
    except Exception as e:
        return {"error": str(e)}

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
    uploaded_res = process_data_and_upload('clan_info', creds)
    if "error" in uploaded_res:
        flash(f"Upload thất bại! Error: {uploaded_res["error"]}", "danger")
    else:
        flash(f"Đã upload thành công với ID: {uploaded_res["id"]}", "success")
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
    uploaded_res = process_data_and_upload('war_log', creds)
    if "error" in uploaded_res:
        flash(f"Upload thất bại! Error: {uploaded_res["error"]}", "danger")
    else:
        flash(f"Đã upload thành công với ID: {uploaded_res["id"]}", "success")
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
        app.logger.error("token.json not found. Please log in first to create the file.")
        return {"error": "Token file not found. Please log in first."}, 401
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
    uploaded_res = process_data_and_upload('clan_info', credentials)
    return uploaded_res

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
    uploaded_res = process_data_and_upload('war_log', credentials)
    return uploaded_res

@app.route('/api/upload-current-war-league')
def upload_current_war_league_api():
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
    drive_service = DriveService(credentials=credentials)
    uploaded_res = process_wldata_and_upload(drive_service)
    return uploaded_res
