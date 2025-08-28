
from app import app, cache
import requests
import json
import urllib.parse

def fetch_data(url, params=None, headers=None, timeout=10):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Error: The request to {url} timed out after {timeout} seconds.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def login_coc(email, password):
    login_url = "https://developer.clashofclans.com/api/login"
    payload = {
        "email": email,
        "password": password
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(login_url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling login API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def getCocApiToken():
    token = cache.get('coc_api_token')
    if token is None:
        email = app.config['EMAIL']
        password = app.config['PASSWORD']
        if email == None or password == None:
            return None
        login_response = login_coc(email, password)
        if login_response == None:
            token = None
        token = login_response['temporaryAPIToken']
        cache.set('coc_api_token', token, timeout=3500)
    return token

def deep_merge(target, source):
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            target[key] = deep_merge(target[key], value)
        elif key in target and isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(value)
            # Hoặc loại bỏ trùng lặp nếu cần: target[key] = list(set(target[key] + value))
        else:
            target[key] = value
    return target

def fetch_clan_info(token, clan_tag):
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    clan_data = fetch_data(url, headers=headers)
    if clan_data is None:
        return None
    new_member_list = []
    if 'members' in clan_data and clan_data['members'] > 0:
        for member in clan_data['memberList']:
            member_data = fetch_data(f"https://api.clashofclans.com/v1/players/{urllib.parse.quote(member['tag'])}", headers=headers)
            if member_data is not None and 'reason' not in member_data:
                merge_data = deep_merge(member.copy(), member_data)
                final_member_data = {key: value for key, value in merge_data.items() if key not in app.config['MEMBER_EXCLUDED_KEYS']}
                new_member_list.append(final_member_data)
        clan_data['memberList'] = new_member_list
    return clan_data

def fetch_war_log(token, clan_tag, drive_service):
    url = f"https://api.clashofclans.com/v1/clans/{clan_tag}/warlog"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    api_warlog_data = fetch_data(url, headers=headers)

    if api_warlog_data is None or 'items' not in api_warlog_data:
        print("Không thể lấy dữ liệu warlog mới từ API hoặc dữ liệu không hợp lệ.")
        return None

    new_warlogs = api_warlog_data.get('items', [])
    combined_warlogs = {}

    for war in new_warlogs:
        war_id = war.get('endTime', str(war)) # Using endTime as a potential identifier
        combined_warlogs[war_id] = war

    existing_warlog_content = drive_service.get_json_file_from_folder(app.config['CLAN_INFO_FILE_NAME'] , app.config['DRIVE_FOLDER_ID'])

    if existing_warlog_content:
        try:
            existing_warlog_data = json.loads(existing_warlog_content)
            if isinstance(existing_warlog_data, list):
                for war in existing_warlog_data:
                     war_id = war.get('endTime', str(war))
                     if war_id not in combined_warlogs:
                        combined_warlogs[war_id] = war
            else:
                print("Định dạng tệp war_log.json cũ không hợp lệ (không phải danh sách).")
        except json.JSONDecodeError:
            print("Lỗi giải mã JSON khi đọc tệp war_log.json cũ.")
        except Exception as e:
            print(f"Lỗi khi xử lý dữ liệu warlog cũ: {e}")

    final_warlog_list = list(combined_warlogs.values())
    try:
        final_warlog_list.sort(key=lambda x: x.get('endTime', ''), reverse=True)
    except Exception as e:
        print(f"Không thể sắp xếp warlog: {e}")

    return final_warlog_list
