from .. import app, cache
import requests
import json
import urllib.parse

MEMBER_EXCLUDED_KEYS = ['playerHouse', 'clan', 'achievements', 'labels', 'troops', 'heroes', 'heroEquipment', 'spells']

def fetch_data(url, params=None, headers=None, timeout=10):
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return {"data": response.json()}
    except requests.exceptions.Timeout:
        # Ghi log lỗi vào file của Flask
        app.logger.error(f"Error: The request to {url} timed out after {timeout} seconds.")
        return {"error": f"Request to {url} timed out."}
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"HTTPError: {e.response.status_code} - {e.response.text}")
        return {"error": f"HTTPError {e.response.status_code}: {e.response.text}"}
    except requests.exceptions.RequestException as e:
        app.logger.error(f"RequestException: Error fetching data from {url}: {e}")
        return {"error": f"Failed to fetch data from {url}: {e}"}
    except Exception as e:
        app.logger.error(f"An unexpected error occurred while fetching data from {url}: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

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
        return {"data": response.json()}
    except requests.exceptions.RequestException as e:
        app.logger.error(f"RequestException: Error calling login API: {e}")
        return {"error": f"Failed to call coc login API: {e}"}
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during coc login: {e}")
        return {"error": f"An unexpected error occurred during coc login: {e}"}

def getCocApiToken():
    token = cache.get('coc_api_token')
    if token is None:
        email = app.config.get('EMAIL')
        password = app.config.get('PASSWORD')
        if not email or not password:
            app.logger.error("COC_EMAIL or COC_PASSWORD not found in config.")
            return {"error": "Authentication credentials not configured."}
            
        login_response = login_coc(email, password)
        # Sửa lỗi: Kiểm tra nếu phản hồi là lỗi
        if 'error' in login_response:
            app.logger.error(f"Login failed: {login_response['error']}")
            return {"error": "Login to COC API failed."}
            
        # Sửa lỗi: Kiểm tra key trước khi truy cập để tránh TypeError
        if 'temporaryAPIToken' not in login_response['data']:
            app.logger.error("temporaryAPIToken not found in login response.")
            return {"error": "temporaryAPIToken not found in login response."}

        token = login_response['data']['temporaryAPIToken']
        cache.set('coc_api_token', token, timeout=3500)
    return {"data": token}

def deep_merge(target, source):
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            target[key] = deep_merge(target[key], value)
        elif key in target and isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(value)
        else:
            target[key] = value
    return target

def fetch_clan_info(token, clan_tag):
    if not token or not clan_tag:
        return {"error": "Token or clan tag is missing."}
        
    url = f"https://api.clashofclans.com/v1/clans/{urllib.parse.quote(clan_tag)}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    clan_data_res = fetch_data(url, headers=headers)

    if 'error' in clan_data_res:
        return {"error": f"Failed to fetch clan info: {clan_data_res['error']}"}

    clan_data = clan_data_res['data']
    
    # Sửa lỗi: Kiểm tra 'memberList' thay vì 'members'
    if 'memberList' in clan_data and len(clan_data['memberList']) > 0:
        new_member_list = []
        for member in clan_data['memberList']:
            player_data_res = fetch_data(f"https://api.clashofclans.com/v1/players/{urllib.parse.quote(member['tag'])}", headers=headers)
            
            if 'error' in player_data_res:
                app.logger.warning(f"Failed to fetch player data for tag {member['tag']}: {player_data_res['error']}")
                continue 

            merge_data = deep_merge(member.copy(), player_data_res['data'])
            final_member_data = {key: value for key, value in merge_data.items() if key not in MEMBER_EXCLUDED_KEYS}
            new_member_list.append(final_member_data)
            
        clan_data['memberList'] = new_member_list
    return {"data": clan_data}

def fetch_war_log(token, clan_tag, drive_service):
    if not token or not clan_tag:
        return {"error": "Token or clan tag is missing."}
        
    url = f"https://api.clashofclans.com/v1/clans/{urllib.parse.quote(clan_tag)}/warlog"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    api_warlog_res = fetch_data(url, headers=headers)

    if 'error' in api_warlog_res:
        app.logger.error(f"Failed to fetch warlog: {api_warlog_res['error']}")
        return {"error": f"Failed to fetch warlog: {api_warlog_res['error']}"}

    api_warlog_data = api_warlog_res['data']
    
    if 'items' not in api_warlog_data:
        app.logger.warning("No 'items' key found in API warlog data.")
        return {"error": "No 'items' key found in API warlog data."}

    new_warlogs = api_warlog_data.get('items', [])
    combined_warlogs = {}

    for war in new_warlogs:
        war_id = war.get('endTime', str(war))
        combined_warlogs[war_id] = war

    existing_warlog_content = drive_service.get_json_file_from_folder(app.config.get('CLAN_INFO_FILE_NAME'), app.config.get('DRIVE_FOLDER_ID'))

    if existing_warlog_content:
        try:
            existing_warlog_data = json.loads(existing_warlog_content)
            if isinstance(existing_warlog_data, list):
                for war in existing_warlog_data:
                     war_id = war.get('endTime', str(war))
                     if war_id not in combined_warlogs:
                        combined_warlogs[war_id] = war
            else:
                app.logger.warning("Old warlog file format is invalid (not a list).")
        except json.JSONDecodeError:
            app.logger.error("JSON decode error when reading old warlog file.")
        except Exception as e:
            app.logger.error(f"Error processing old warlog data: {e}")

    final_warlog_list = list(combined_warlogs.values())
    try:
        final_warlog_list.sort(key=lambda x: x.get('endTime', ''), reverse=True)
    except Exception as e:
        app.logger.error(f"Could not sort warlogs: {e}")

    return {"data": final_warlog_list}