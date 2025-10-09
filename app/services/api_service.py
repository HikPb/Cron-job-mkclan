from .. import app, cache
import json
import datetime
import asyncio
import aiohttp
import requests
import urllib.parse
from .data_processor import process_wl_data, deep_merge

MEMBER_EXCLUDED_KEYS = ['playerHouse', 'clan', 'achievements', 'labels', 'troops', 'heroes', 'heroEquipment', 'spells']

async def fetch_data(session, url, semaphore, params=None, headers=None, timeout=10):
    async with semaphore:
        try:
            async with session.get(url, params=params, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                data = await response.json()
                return {"data": data}
        except asyncio.TimeoutError:
            app.logger.error(f"Error: The request to {url} timed out after {timeout} seconds.")
            return {"error": f"Request to {url} timed out."}
        except aiohttp.ClientResponseError as e:
            app.logger.error(f"RequestException: Error fetching data from {url}: {e}")
            return {"error": f"Failed to fetch data from {url}: {e}"}
        except Exception as e:
            app.logger.error(f"An unexpected error occurred while fetching data from {url}: {e}")
            return {"error": f"An unexpected error occurred: {e}"}

async def login_coc(email, password):
    login_url = "https://developer.clashofclans.com/api/login"
    payload = {
        "email": email,
        "password": password
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(login_url, data=json.dumps(payload), headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                return {"data": data}
    except aiohttp.ClientResponseError as e:
        app.logger.error(f"RequestException: Error calling login API: {e}")
        return {"error": f"Failed to call coc login API: {e}"}
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during coc login: {e}")
        return {"error": f"An unexpected error occurred during coc login: {e}"}

async def getCocApiToken():
    token = cache.get('coc_api_token')
    if token is None:
        email = app.config.get('EMAIL')
        password = app.config.get('PASSWORD')
        if not email or not password:
            app.logger.error("COC_EMAIL or COC_PASSWORD not found in config.")
            return {"error": "Authentication credentials not configured."}
            
        login_response = await login_coc(email, password)
        if 'error' in login_response:
            app.logger.error(f"Login failed: {login_response['error']}")
            return {"error": "Login to COC API failed."}
            
        if 'temporaryAPIToken' not in login_response['data']:
            app.logger.error("temporaryAPIToken not found in login response.")
            return {"error": "temporaryAPIToken not found in login response."}

        token = login_response['data']['temporaryAPIToken']
        cache.set('coc_api_token', token, timeout=3500)
    return {"data": token}

async def fetch_clan_info(token, clan_tag):
    if not token or not clan_tag:
        return {"error": "Token or clan tag is missing."}
        
    url = f"https://api.clashofclans.com/v1/clans/{urllib.parse.quote(clan_tag)}"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(6)
        clan_data_res = await fetch_data(session, url, semaphore=semaphore, headers=headers)
        if 'error' in clan_data_res:
            return {"error": f"Failed to fetch clan info: {clan_data_res['error']}"}

        clan_data = clan_data_res['data']
        if 'memberList' in clan_data and len(clan_data['memberList']) > 0:
            new_member_list = []
            member_tasks = []
            for member in clan_data['memberList']:
                member_tasks.append(fetch_data(session, f"https://api.clashofclans.com/v1/players/{urllib.parse.quote(member['tag'])}", semaphore=semaphore, headers=headers))
                
            member_data_results = await asyncio.gather(*member_tasks)

            for member, member_data in zip(clan_data['memberList'], member_data_results):
                if member_data is not None and 'error' not in member_data:
                    merge_data = deep_merge(member.copy(), member_data['data'])
                    final_member_data = {key: value for key, value in merge_data.items() if key not in MEMBER_EXCLUDED_KEYS}
                    new_member_list.append(final_member_data)

            clan_data['memberList'] = new_member_list
        return {"data": clan_data}

async def fetch_war_log(token, clan_tag, drive_service):
    if not token or not clan_tag:
        return {"error": "Token or clan tag is missing."}
        
    url = f"https://api.clashofclans.com/v1/clans/{urllib.parse.quote(clan_tag)}/warlog"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(4)
        api_warlog_res = await fetch_data(session, url, semaphore=semaphore, headers=headers)

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

        
        json_data = drive_service.get_json_file_from_folder(app.config.get('WARLOG_FILE_NAME'), app.config.get('DRIVE_FOLDER_ID'))

        if "error" in json_data:
            return {"error": "An unexpected error occurred during load old war_log.json from drive"}
        else:
            existing_warlog_content = json_data.get('data')
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

        return {"data": final_warlog_list, "last50": new_warlogs}

def process_wldata_and_upload(drive_service):
    current_time = datetime.datetime.now()
    season = current_time.strftime('%Y-%m')
    wl_file_name = season + '.json'
    query = f"name='{wl_file_name}' and '{app.config['WL_DRIVE_FOLDER_ID']}' in parents and trashed=false"
    results = drive_service.service.files().list(q=query,
                                        spaces='drive',
                                        fields='files(id, name, createdTime)').execute()
    existing_files = results.get('files', [])
    if len(existing_files)>0:
        return {"info":"Cancel upload, file already exists in directory."}
    
    try:
        api_url = "https://api.clashofstats.com/clans/2QCV8UJ8Q/cwl/seasons/" + season
        response = requests.get(url=api_url)
        response.raise_for_status()
        data = response.json()
        return process_wl_data(season, data, drive_service)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching data from {api_url}: {e}")
        return {"error": f"Error fetching data from {api_url}: {e}"}
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"An unexpected error occurred: {e}"}
    
def get_token():
    try:
        response = requests.get(url=app.config.get('API_URL'))
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching data from GAS Api: {e}")
        return {"error": f"Error fetching data from GAS Api: {e}"}
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return {"error": f"An unexpected error occurred: {e}"}    