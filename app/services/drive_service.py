import os
import io
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from .. import app 

class DriveService:
    def __init__(self, credentials):
        if not isinstance(credentials, Credentials):
            app.logger.error("TypeError: Credentials must be a google.oauth2.credentials.Credentials object.")
            raise TypeError("Credentials must be a google.oauth2.credentials.Credentials object.")
        try:
            self.credentials = credentials
            self.service = build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            app.logger.critical(f"Failed to build Drive service: {e}")
            raise RuntimeError(f"Failed to build Drive service: {e}")

    def upload_json_to_drive(self, file_path, folder_id, num_backups_to_keep=2):
        if not os.path.exists(file_path):
            app.logger.error(f"File not found at path: {file_path}")
            return {"error" : f"File not found at path: {file_path}"}
            
        file_name = os.path.basename(file_path)
        base_file_name, file_extension = os.path.splitext(file_name)
        backup_pattern = f"{base_file_name}_backup_"
        uploaded_file_id = None

        try:
            # 1. Tìm kiếm tệp hiện có
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query,
                                                spaces='drive',
                                                fields='files(id, name, createdTime)').execute()
            existing_files = results.get('files', [])

            if existing_files:
                existing_file = existing_files[0]
                existing_file_id = existing_file['id']

                if num_backups_to_keep > 0:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{base_file_name}_backup_{timestamp}{file_extension}"
                    self.service.files().update(fileId=existing_file_id, body={'name': backup_name}).execute()
                else:
                    self.service.files().delete(fileId=existing_file_id).execute()

            # 2. Tải lên tệp mới
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(file_path, mimetype='application/json')
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            uploaded_file_id = file.get('id')
            app.logger.info(f"New file {file_name} (ID: {uploaded_file_id}) uploaded to Drive folder.")

            # 3. Xóa các bản sao lưu cũ
            if num_backups_to_keep >= 0:
                backup_query = f"name contains '{backup_pattern}' and '{folder_id}' in parents and trashed=false"
                backup_results = self.service.files().list(q=backup_query,
                                                            spaces='drive',
                                                            fields='files(id, name, createdTime)').execute()
                backup_files = backup_results.get('files', [])

                if len(backup_files) > num_backups_to_keep:
                    backup_files.sort(key=lambda x: x['createdTime'])
                    files_to_delete = backup_files[:-num_backups_to_keep]
                    for old_file in files_to_delete:
                        self.service.files().delete(fileId=old_file['id']).execute()

        except Exception as e:
            app.logger.error(f"Error processing and uploading file to Drive: {e}")
            return {"error" : f"Error processing and uploading file to Drive: {e}"}

        return {"id": uploaded_file_id }

    def upload_string_to_drive(self, data_str, file_name, folder_id, num_backups_to_keep=2):
        base_file_name, file_extension = os.path.splitext(file_name)
        backup_pattern = f"{base_file_name}_backup_"
        uploaded_file_id = None

        try:
            # 1. Tìm kiếm tệp hiện có
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query,
                                                spaces='drive',
                                                fields='files(id, name, createdTime)').execute()
            existing_files = results.get('files', [])

            if existing_files:
                existing_file_id = existing_files[0]['id']

                # 2. Xử lý tệp hiện có: sao lưu hoặc xóa
                if num_backups_to_keep > 0:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{base_file_name}_backup_{timestamp}{file_extension}"
                    
                    # Cập nhật tên và thêm metadata is_backup: true cho tệp
                    metadata_body = {
                        'name': backup_name,
                        'properties': {'is_backup': 'true'}
                    }
                    self.service.files().update(fileId=existing_file_id, body=metadata_body).execute()
                    app.logger.info(f"Existing file {file_name} renamed to backup {backup_name} and marked as backup.")
                else: # num_backups_to_keep is 0
                    self.service.files().delete(fileId=existing_file_id).execute()
                    app.logger.info(f"Existing file {file_name} deleted as per backup policy.")
            
            # 3. Tải lên tệp mới
            data_bytes = data_str.encode('utf-8')
            data_io = io.BytesIO(data_bytes)
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaIoBaseUpload(data_io, mimetype='application/json', resumable=True)
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            uploaded_file_id = file.get('id')
            app.logger.info(f"New file {file_name} (ID: {uploaded_file_id}) uploaded from string to Drive folder.")

            # 4. Xóa các bản sao lưu cũ dựa trên cả metadata và tên tệp
            if num_backups_to_keep > 0: # Chỉ dọn dẹp nếu có chính sách sao lưu
                backup_query = (
                    f"properties has {{key='is_backup' and value='true'}} "
                    f"and name contains '{backup_pattern}' "
                    f"and '{folder_id}' in parents and trashed=false"
                )
                backup_results = self.service.files().list(q=backup_query,
                                                            spaces='drive',
                                                            fields='files(id, name, createdTime)').execute()
                backup_files = backup_results.get('files', [])
                
                if len(backup_files) > num_backups_to_keep:
                    # Sắp xếp các bản sao lưu theo thời gian tạo
                    backup_files.sort(key=lambda x: x['createdTime'])
                    files_to_delete = backup_files[:-num_backups_to_keep]
                    for old_file in files_to_delete:
                        self.service.files().delete(fileId=old_file['id']).execute()
                        app.logger.info(f"Deleted old backup file with ID: {old_file['id']}.")

        except Exception as e:
            app.logger.error(f"Error processing and uploading string to Drive: {e}")
            return {"error" : f"Error processing and uploading string to Drive: {e}"}

        return {"id": uploaded_file_id}

    def get_json_file_from_folder(self, file_name, folder_id):
        try:
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query,
                                                spaces='drive',
                                                fields='files(id)').execute()
            items = results.get('files', [])
            if not items:
                app.logger.warning(f"File '{file_name}' not found in Drive folder.")
                return {"error": f"File '{file_name}' not found in Drive folder."}

            file_id = items[0]['id']
            request = self.service.files().get_media(fileId=file_id)
            file_content = request.execute()
            
            return {"data": file_content.decode('utf-8')}
        except Exception as e:
            app.logger.error(f"Error downloading file from Drive: {e}")
            return {"error": f"Error downloading file from Drive: {e}"}