import os
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

class DriveService:
    def __init__(self, credentials):
        if not isinstance(credentials, Credentials):
            raise TypeError("Credentials phải là một đối tượng google.oauth2.credentials.Credentials")   
        self.credentials = credentials
        self.service = build('drive', 'v3', credentials=self.credentials)

    def create_text_file(self, file_name, content):
        try:
            file_metadata = {'name': file_name, 'mimeType': 'text/plain'}
            media = MediaFileUpload(content, mimetype='text/plain', resumable=True)
            
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            print(f"Đã tạo tệp '{file_name}' với ID: {file.get('id')}")
            return file.get('id')
        except Exception as e:
            print(f"Lỗi khi tạo tệp trên Drive: {e}")
            return None
    
    def upload_file(self, file_path, folder_id=None):
        """
        Tải một tệp cục bộ lên Google Drive.
        
        Args:
            file_path (str): Đường dẫn đến tệp tin trên máy tính.
            folder_id (str, optional): ID của thư mục cha. Mặc định là thư mục gốc.
        """
        try:
            # Lấy tên tệp từ đường dẫn
            file_name = file_path.split('/')[-1]
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            media = MediaFileUpload(file_path, resumable=True)
            
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            print(f"Đã tải tệp '{file_name}' lên với ID: {file.get('id')}")
            return file.get('id')
        except Exception as e:
            print(f"Lỗi khi tải tệp lên Drive: {e}")
            return None

    def download_file(self, file_id, destination_path):
        try:
            request = self.service.files().get_media(fileId=file_id)
            with open(destination_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    print(f"Tiến độ tải xuống: {int(status.progress() * 100)}%")
            print(f"Đã tải tệp với ID '{file_id}' về '{destination_path}' thành công.")
            return True
        except Exception as e:
            print(f"Lỗi khi tải tệp từ Drive: {e}")
            return False

    def upload_json_to_drive(self, file_path, folder_id, num_backups_to_keep=2):
        file_name = os.path.basename(file_path)
        base_file_name, file_extension = os.path.splitext(file_name)
        backup_pattern = f"{base_file_name}_backup_" # Pattern to identify backup files
        uploaded_file_id = None  # Variable to store the ID of the uploaded file

        try:
            # 1. Search for existing file by name in the folder
            query = f"name= '{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query,
                                                spaces='drive',
                                                fields='files(id, name, createdTime)').execute() # Added createdTime to fields
            existing_files = results.get('files', [])

            if existing_files:
                # 2. If file exists, handle it based on num_backups_to_keep
                existing_file = existing_files[0]
                existing_file_id = existing_file['id']

                if num_backups_to_keep > 0:
                    # Rename the existing file as a backup if backups are kept
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"{base_file_name}_backup_{timestamp}{file_extension}"

                    print(f"Đã tìm thấy tệp '{file_name}' hiện có. Đang đổi tên thành '{backup_name}'...")
                    self.service.files().update(fileId=existing_file_id,
                                                body={'name': backup_name}).execute()
                    print(f"Đã đổi tên tệp hiện có.")
                else:
                    # If no backups are kept, just delete the existing file
                    print(f"Đã tìm thấy tệp '{file_name}' hiện có. Đang xóa tệp...")
                    self.service.files().delete(fileId=existing_file_id).execute()
                    print(f"Đã xóa tệp hiện có.")


            # 3. Upload the new file
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(file_path, mimetype='application/json')
            file = self.service.files().create(body=file_metadata,
                                                media_body=media,
                                                fields='id').execute()
            uploaded_file_id = file.get('id') # Get the uploaded file ID
            print(f"Đã tải lên tệp mới {file_name} (ID: {uploaded_file_id}) vào thư mục Drive.")

            # 4. Clean up old backup files (only if num_backups_to_keep > 0)
            if num_backups_to_keep > 0:
                print(f"Đang kiểm tra các tệp sao lưu cũ của '{file_name}'...")
                backup_query = f"name contains '{backup_pattern}' and '{folder_id}' in parents and trashed=false"
                backup_results = self.service.files().list(q=backup_query,
                                                            spaces='drive',
                                                            fields='files(id, name, createdTime)').execute()
                backup_files = backup_results.get('files', [])

                if len(backup_files) > num_backups_to_keep:
                    # Sort backup files by creation time (oldest first)
                    backup_files.sort(key=lambda x: x['createdTime'])

                    # Delete older backups, keeping only the most recent ones
                    files_to_delete = backup_files[:-num_backups_to_keep]
                    print(f"Tìm thấy {len(backup_files)} tệp sao lưu. Giữ lại {num_backups_to_keep} bản gần nhất và xóa {len(files_to_delete)} bản cũ hơn.")

                    for old_file in files_to_delete:
                        print(f"Đang xóa tệp sao lưu cũ: {old_file['name']} (ID: {old_file['id']})")
                        self.service.files().delete(fileId=old_file['id']).execute()
                    print("Đã xóa các tệp sao lưu cũ.")
                else:
                    print(f"Số lượng tệp sao lưu ({len(backup_files)}) không vượt quá giới hạn ({num_backups_to_keep}). Không cần xóa tệp nào.")
            else:
                print("Không giữ lại tệp sao lưu cũ.")


        except Exception as e:
            print(f"Lỗi khi xử lý tệp và tải lên Drive: {e}")
            return {"status": "error", "message": e}

        return {"status": "success", "id": uploaded_file_id }

    def get_json_file_from_folder(self, file_name, folder_id):
        try:
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query,
                                                spaces='drive',
                                                fields='files(id)').execute()
            items = results.get('files', [])
            if not items:
                print(f"Không tìm thấy tệp '{file_name}' trong thư mục Drive.")
                return None

            file_id = items[0]['id']
            request = self.service.files().get_media(fileId=file_id)
            file_content = request.execute()
            return file_content
        except Exception as e:
            print(f"Lỗi khi tải tệp từ Drive: {e}")
            return None