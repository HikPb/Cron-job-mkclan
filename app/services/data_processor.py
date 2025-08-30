import json
import datetime
from .api_service import fetch_data
from .. import app
from collections import defaultdict

CLAN_TAG = '#2QCV8UJ8Q'

def handle_rounds_clan_player(memberList):
    """
    Trích xuất dữ liệu tấn công và phòng thủ của người chơi từ mỗi vòng đấu.
    """
    listMember = []
    if not isinstance(memberList, list):
        app.logger.warning("Warning: memberList is not a list.")
        return listMember

    for member in memberList:
        try:
            newMember = {
                'tag': member.get('tag'),
                'mapPosition': member.get('mapPosition')
            }
            if 'attack' in member and member['attack'] is not None:
                newMember['atkTag'] = member['attack'].get('defenderTag')
                newMember['atkStars'] = member['attack'].get('stars')
                newMember['atkDesPercent'] = member['attack'].get('destructionPercentage')

            if 'bestOpponentAttack' in member and member['bestOpponentAttack'] is not None:
                newMember['defTag'] = member['bestOpponentAttack'].get('attackerTag')
                newMember['defStars'] = member['bestOpponentAttack'].get('stars')
                newMember['defDesPercent'] = member['bestOpponentAttack'].get('destructionPercentage')

            listMember.append(newMember)
        except (KeyError, TypeError) as e:
            app.logger.error(f"Error processing member data: {e} in member: {member}")
            continue
        except Exception as e:
            app.logger.error(f"An unexpected error occurred while processing member data: {e} in member: {member}")
            continue
    return listMember

def get_players(data):
    """
    Trích xuất thông tin người chơi (tag, name, townHallLevel) từ dữ liệu API.
    """
    allplayer = {}
    if not isinstance(data, dict) or 'clans' not in data or not isinstance(data['clans'], list):
        app.logger.warning("Warning: Invalid data structure for getting players.")
        return allplayer
    try:
        for clan in data.get('clans', []):
            for member in clan.get('members', []):
                if 'tag' in member:
                    allplayer[member['tag']] = {
                        key: value for key, value in member.items() if key in ['name', 'townHallLevel']
                    }
                else:
                    app.logger.warning(f"Warning: Member without a tag found in clan: {clan.get('tag')}")
    except (KeyError, TypeError) as e:
        app.logger.error(f"Error processing clan or member data in get_players: {e}")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in get_players: {e}")
    return allplayer

def get_clans(data):
    """
    Trích xuất thông tin clan (tag, name, level, badge) từ dữ liệu API.
    """
    allclans = {}
    if not isinstance(data, dict) or 'clans' not in data or not isinstance(data['clans'], list):
        app.logger.warning("Warning: Invalid data structure for getting clans.")
        return allclans
    try:
        for clan in data.get('clans', []):
            if 'tag' in clan:
                allclans[clan['tag']] = {
                    "name": clan.get('name'),
                    "clanLevel": clan.get('clanLevel'),
                    "badgeUrl" : clan.get('badgeUrls', {}).get('small'),
                }
            else:
                app.logger.warning("Warning: Clan without a tag found.")
    except (KeyError, TypeError) as e:
        app.logger.error(f"Error processing clan data in get_clans: {e}")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in get_clans: {e}")
    return allclans

def get_all_clan_rounds(data):
    """
    Trích xuất kết quả từng vòng đấu của tất cả các clan.
    """
    allrounds = []
    if not isinstance(data, dict) or 'rounds' not in data or not isinstance(data['rounds'], list):
        app.logger.warning("Warning: Invalid data structure for getting rounds.")
        return allrounds
    try:
        for round_data in data.get('rounds', []):
            clans_in_round = {}
            for war in round_data.get('wars', []):
                try:
                    clan1_tag = war.get('clan', {}).get('tag')
                    clan2_tag = war.get('opponent', {}).get('tag')
                    if clan1_tag and clan2_tag:
                        clan1_info = war.get('clan', {})
                        clan2_info = war.get('opponent', {})
                        clan1 = {
                            "tag": clan1_tag,
                            "stars": clan1_info.get('stars'),
                            "desPercent": clan1_info.get('destructionPercentage'),
                            "attacks": clan1_info.get('attacks'),
                            "isWinning": clan1_info.get('isWinning'),
                            "opponentTag": clan2_tag,
                            "opponentStars": clan2_info.get('stars'),
                            "opponentDesPercent": clan2_info.get('destructionPercentage'),
                            "opponentAttacks": clan2_info.get('attacks'),
                            "teamSize": war.get('teamSize'),
                            "members": handle_rounds_clan_player(clan1_info.get('members', []))
                        }
                        clan2 = {
                            "tag": clan2_tag,
                            "stars": clan2_info.get('stars'),
                            "desPercent": clan2_info.get('destructionPercentage'),
                            "attacks": clan2_info.get('attacks'),
                            "isWinning": clan2_info.get('isWinning'),
                            "opponentTag": clan1_tag,
                            "opponentStars": clan1_info.get('stars'),
                            "opponentDesPercent": clan1_info.get('destructionPercentage'),
                            "opponentAttacks": clan1_info.get('attacks'),
                            "teamSize": war.get('teamSize'),
                            "members": handle_rounds_clan_player(clan2_info.get('members', []))
                        }
                        clans_in_round[clan1_tag] = clan1
                        clans_in_round[clan2_tag] = clan2
                    else:
                        app.logger.warning(f"Warning: War data missing clan or opponent tag in round: {round_data}")
                except (KeyError, TypeError) as e:
                    app.logger.error(f"Error processing war data: {e} in war: {war}")
                    continue
                except Exception as e:
                    app.logger.error(f"An unexpected error occurred while processing war data: {e} in war: {war}")
                    continue
            allrounds.append(clans_in_round)
    except (KeyError, TypeError) as e:
        app.logger.error(f"Error processing round data in get_rounds: {e}")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in get_rounds: {e}")

    return allrounds

def process_wl_data(season, data, drive_service):
    """
    Xử lý dữ liệu Clan War League và tải lên Google Drive.
    """
    # Tên các tệp sẽ được tải lên Drive
    overall_file_name = season + '.json'
    rounds_file_name = season +'_round.json'
    players_file_name = season +'_player.json'
    
    # 1. Trích xuất và xử lý dữ liệu từ API
    listPlayer = get_players(data)
    listClan = get_clans(data)
    allClanRounds = get_all_clan_rounds(data)
    
    # Khởi tạo các cấu trúc dữ liệu để lưu trữ kết quả
    mk_rounds = []
    mk_players_stats = defaultdict(lambda: {
        "atkStars": 0,
        "atkDesPercent": 0,
        "attacks": 0,
        "defStars": 0,
        "defDesPercent": 0,
        "defense": 0,
        "rounds": 0,
    })
    overall_result = defaultdict(lambda: {
        "totalStars": 0,
        "atkStars": 0,
        "atkDesPercent": 0,
        "attacks": 0,
        "defStars": 0,
        "defDesPercent": 0,
        "defense": 0,
    })
    join_war_player = set()
    overall_rounds = []

    # 2. Tổng hợp dữ liệu vòng đấu và người chơi
    for index, item in enumerate(allClanRounds):
        if not isinstance(item, dict) or CLAN_TAG not in item:
            app.logger.warning(f"Cảnh báo: Phần tử tại chỉ mục {index} không phải là dictionary hợp lệ hoặc thiếu clan tag. Bỏ qua.")
            continue
        
        # Thêm dữ liệu vòng đấu của clan #2QCV8UJ8Q vào danh sách
        mk_rounds.append(item[CLAN_TAG])
        
        # Tổng hợp số liệu người chơi
        for player in item[CLAN_TAG]["members"]:
            player_tag = player.get("tag")
            if player_tag:
                join_war_player.add(player_tag)
                # Cập nhật số liệu tấn công
                if 'atkTag' in player:
                    join_war_player.add(player.get("atkTag"))
                    mk_players_stats[player_tag]["atkStars"] += player.get("atkStars", 0)
                    mk_players_stats[player_tag]["atkDesPercent"] += player.get("atkDesPercent", 0)
                    mk_players_stats[player_tag]["attacks"] += 1
                # Cập nhật số liệu phòng thủ
                if 'defTag' in player:
                    join_war_player.add(player.get("defTag"))
                    mk_players_stats[player_tag]["defStars"] += player.get("defStars", 0)
                    mk_players_stats[player_tag]["defDesPercent"] += player.get("defDesPercent", 0)
                    mk_players_stats[player_tag]["defense"] += 1
                mk_players_stats[player_tag]["rounds"] += 1
        
        # Tổng hợp kết quả tổng thể cho tất cả các clan trong vòng đấu
        roundx = {}
        for tag, value in item.items():
            overall_result[tag]["atkStars"] += value.get("stars", 0)
            overall_result[tag]["atkDesPercent"] += value.get("desPercent", 0)
            overall_result[tag]["attacks"] += value.get("attacks", 0)
            overall_result[tag]["defStars"] += value.get("opponentStars", 0)
            overall_result[tag]["defDesPercent"] += value.get("opponentDesPercent", 0)
            overall_result[tag]["defense"] += value.get("opponentAttacks", 0)
            overall_result[tag]["totalStars"] += value.get("stars", 0)
            if value.get("isWinning"):
                overall_result[tag]["totalStars"] += 10
            roundx[tag] = {
                "stars": value.get('stars'),
                "desPercent": value.get('desPercent'),
                "attacks": value.get('attacks'),
                "isWinning": value.get('isWinning'),
                "opponentStars": value.get('opponentStars'),
                "opponentDesPercent": value.get('opponentDesPercent'),
                "opponentAttacks": value.get('opponentAttacks'),
            }
        overall_rounds.append(roundx)
        
    # 3. Chuyển đổi dữ liệu và chuẩn bị tải lên Drive
    mk_players_rank = []
    for tag in join_war_player:
        stats = mk_players_stats[tag]
        mk_players_rank.append({
            "tag": tag,
            "atkStars": stats["atkStars"],
            "atkDesPercent": stats["atkDesPercent"],
            "attacks": stats["attacks"],
            "defStars": stats["defStars"],
            "defDesPercent": stats["defDesPercent"],
            "defense": stats["defense"],
            "rounds": stats["rounds"]
        })
    players = {key: value for key, value in listPlayer.items() if key in join_war_player}

    # 4. Tải lên Drive
    rounds_string = json.dumps(mk_rounds, indent=4)
    rounds_res = drive_service.upload_string_to_drive(rounds_string, rounds_file_name, app.config['WL_RP_DRIVE_FOLDER_ID'], num_backups_to_keep=0)
    if "error" in rounds_res:
        app.logger.error(f"Lỗi khi tải tệp rounds: {rounds_res.get('error')}")
        return {"error": f"Lỗi khi tải tệp rounds: {rounds_res.get('error')}"}

    players_string = json.dumps(mk_players_rank, indent=4)
    players_res = drive_service.upload_string_to_drive(players_string, players_file_name, app.config['WL_RP_DRIVE_FOLDER_ID'], num_backups_to_keep=0)
    if "error" in players_res:
        app.logger.error(f"Lỗi khi tải tệp players: {players_res.get('error')}")
        return {"error": f"Lỗi khi tải tệp players: {players_res.get('error')}"}

    # 5. Tạo và tải lên tệp tổng thể
    mk_overall = {
        "state": data.get('state'),
        "season": data.get('season'),
        "leagueId": data.get('leagueId'),
        "clans": listClan,
        "players": players,
        "rounds": overall_rounds,
        "result": overall_result[CLAN_TAG],
        "urls": {"round": rounds_res.get("id"), "player": players_res.get("id")}
    }
    overall_string = json.dumps(mk_overall, indent=4)
    overall_res = drive_service.upload_string_to_drive(overall_string, overall_file_name, app.config['WL_DRIVE_FOLDER_ID'], num_backups_to_keep=0)

    if "error" in overall_res:
        app.logger.error(f"Lỗi khi tải tệp overall: {overall_res.get('error')}")
        return {"error": f"Lỗi khi tải tệp overall: {overall_res.get('error')}"}

    return {"overall": overall_res, "round": rounds_res, "player": players_res}
    
def process_wldata_and_upload(drive_service):
    current_time = datetime.datetime.now()
    season = current_time.strftime('%Y-%m')
    api_url = "https://api.clashofstats.com/clans/2QCV8UJ8Q/cwl/seasons/" + season
    data = fetch_data(api_url)
    if "error" in data:
        return data
    else:
        return process_wl_data(season, data.get("data"), drive_service)