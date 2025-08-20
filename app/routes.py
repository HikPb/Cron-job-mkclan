from app import app
from flask import render_template, redirect, url_for, session, request, flash
from functools import wraps

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from werkzeug.exceptions import HTTPException
import json
import io

try:
    client_secret_json = json.loads(app.config['CLIENT_CONFIG'])
except (json.JSONDecodeError, TypeError):
    print("Lỗi: Không thể tải GOOGLE_CLIENT_SECRET_JSON từ biến môi trường.")
    client_secret_json = None

SCOPES = ["https://www.googleapis.com/auth/drive.file",  'https://www.googleapis.com/auth/userinfo.email']

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

@app.route('/dotask')
@login_required
def dotask():
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
        # Xây dựng dịch vụ Google Drive API
        drive_service = build('drive', 'v3', credentials=creds)

        # Tạo nội dung cho tệp a.txt
        file_content = "This is a test file created by the Flask app."
        file_name = "a.txt"
        
        # Metadata cho tệp, bao gồm ID thư mục cha
        file_metadata = {
            'name': file_name,
            'parents': [app.config['DRIVE_FOLDER_ID']]
        }
        
        # Tải tệp lên Google Drive
        media = MediaIoBaseUpload(io.BytesIO(file_content.encode('utf-8')),
                                  mimetype='text/plain',
                                  resumable=True)
        
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        flash(f"Đã tải thành công tệp {file_name} với ID: {uploaded_file.get('id')} lên Google Drive!", "success")
        return redirect(url_for('home'))
        
    except Exception as e:
        flash(f"Lỗi khi tải tệp lên Google Drive: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/cron_task')
def cron_task():
    secret_from_request = request.args.get('secret')
    if secret_from_request != app.config['CRON_SECRET_KEY']:
        print("Unauthorized access. Secret key does not match.")
        return {"message": "Unauthorized access"}, 403
    try:
        with open('token.json', 'r') as f:
            credentials_data = json.load(f)
    except FileNotFoundError:
        print("token.json not found. Please log in first to create the file.")
        return {"message": "Token file not found. Please log in first."}, 401
    credentials = Credentials(**credentials_data)
    if not credentials.valid:
        if credentials.refresh_token:
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
        else:
            print("Refresh token is missing or invalid.")
            return {"message": "Refresh token is missing. Please re-authenticate."}, 401
    
   
    return {"message": "Task executed successfully."}, 200