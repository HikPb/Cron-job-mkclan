import json
import pprint
import os
from api_service import *
from app import app
from collections import defaultdict

LIST_SEASONS = []

def handle_rounds_clan_player(memberList):
    listMember = []
    if not isinstance(memberList, list):
        print("Warning: memberList is not a list.")
        return listMember

    for member in memberList:
        try:
            newMember = {}
            newMember['tag'] = member.get('tag')
            newMember['mapPosition'] = member.get('mapPosition')

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
            print(f"Error processing member data: {e} in member: {member}")
            continue # Skip this member and continue with the next one
        except Exception as e:
            print(f"An unexpected error occurred while processing member data: {e} in member: {member}")
            continue
    return listMember

def get_players(data):
    allplayer = {}
    if not isinstance(data, dict) or 'clans' not in data or not isinstance(data['clans'], list):
        print("Warning: Invalid data structure for getting players.")
        return allplayer

    try:
        for clan in data['clans']:
            if 'members' in clan and isinstance(clan['members'], list):
                for member in clan['members']:
                    if 'tag' in member:
                        allplayer[member['tag']] = {key: value for key, value in member.items() if key in ['name', 'townHallLevel']}
                    else:
                        print(f"Warning: Member without a tag found in clan: {clan.get('tag')}")
            else:
                print(f"Warning: 'members' key missing or not a list in clan: {clan.get('tag')}")
    except (KeyError, TypeError) as e:
        print(f"Error processing clan or member data in get_players: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in get_players: {e}")
    return allplayer

def get_clans(data):
    allclans = {}
    if not isinstance(data, dict) or 'clans' not in data or not isinstance(data['clans'], list):
        print("Warning: Invalid data structure for getting clans.")
        return allclans

    try:
        for clan in data['clans']:
            if 'tag' in clan:
                 allclans[clan['tag']] = {
                    "name": clan.get('name'),
                    "clanLevel": clan.get('clanLevel'),
                    "badgeUrl" : clan.get('badgeUrls').get('small'),
                 }
            else:
                print("Warning: Clan without a tag found.")
    except (KeyError, TypeError) as e:
        print(f"Error processing clan data in get_clans: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in get_clans: {e}")
    return allclans

def get_all_clan_rounds(data):
    allrounds = []
    if not isinstance(data, dict) or 'rounds' not in data or not isinstance(data['rounds'], list):
        print("Warning: Invalid data structure for getting rounds.")
        return allrounds

    try:
        for round in data['rounds']:
            clans = {}
            if isinstance(round.get('wars'), list):
                for war in round['wars']:
                    try:
                        if isinstance(war.get('clan'), dict) and isinstance(war.get('opponent'), dict):
                            clan1_tag = war['clan'].get('tag')
                            clan2_tag = war['opponent'].get('tag')

                            if clan1_tag and clan2_tag:
                                clan1 = {
                                    "tag": clan1_tag,
                                    "stars": war['clan'].get('stars'),
                                    "desPercent": war['clan'].get('destructionPercentage'),
                                    "attacks": war['clan'].get('attacks'),
                                    "isWinning": war['clan'].get('isWinning'),
                                    "opponentTag": clan2_tag,
                                    "opponentStars": war['opponent'].get('stars'),
                                    "opponentDesPercent": war['opponent'].get('destructionPercentage'),
                                    "opponentAttacks": war['opponent'].get('attacks'),
                                    "teamSize": war.get('teamSize'),
                                    "members": handle_rounds_clan_player(war['clan'].get('members', []))
                                }
                                clan2 = {
                                    "tag": clan2_tag,
                                    "stars": war['opponent'].get('stars'),
                                    "desPercent": war['opponent'].get('destructionPercentage'),
                                    "attacks": war['opponent'].get('attacks'),
                                    "isWinning": war['opponent'].get('isWinning'),
                                    "opponentTag": clan1_tag,
                                    "opponentStars": war['clan'].get('stars'),
                                    "opponentDesPercent": war['clan'].get('destructionPercentage'),
                                    "opponentAttacks": war['clan'].get('attacks'),
                                    "teamSize": war.get('teamSize'),
                                    "members": handle_rounds_clan_player(war['opponent'].get('members', []))
                                }
                                clans[clan1_tag] = clan1
                                clans[clan2_tag] = clan2
                            else:
                                print(f"Warning: War data missing clan or opponent tag in round: {round}")
                        else:
                             print(f"Warning: 'clan' or 'opponent' key missing or not a dict in war: {war}")
                    except (KeyError, TypeError) as e:
                        print(f"Error processing war data: {e} in war: {war}")
                        continue # Skip this war and continue with the next one
                    except Exception as e:
                        print(f"An unexpected error occurred while processing war data: {e} in war: {war}")
                        continue
            else:
                print(f"Warning: 'wars' key missing or not a list in round: {round}")

            allrounds.append(clans)
    except (KeyError, TypeError) as e:
        print(f"Error processing round data in get_rounds: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in get_rounds: {e}")

    return allrounds

def process_wl_data(season, data, drive_service):
    os.makedirs("WarLeague", exist_ok=True)
    overall_name = season + '.json'
    round_name = season +'_round.json'
    player_name = season +'_player.json'
    overall_filepath = os.path.join("WarLeague", overall_name)
    round_filepath = os.path.join("WarLeague", round_name)
    player_filepath = os.path.join("WarLeague", player_name)

    print(f"Đang xử lý: {season}")

    listPlayer = get_players(data)
    listClan = get_clans(data)
    allClanRounds = get_all_clan_rounds(data)

    mk_rounds = []
    mk_players = defaultdict(lambda: {
            "atkStars": 0,
            "atkDesPercent": 0,
            "attacks": 0,
            "defStars": 0,
            "defDesPercent": 0,
            "defense": 0,
            "rounds": 0,
        })

    overall_result =  defaultdict(lambda: {
            "totalStars": 0,
            "atkStars": 0,
            "atkDesPercent": 0,
            "attacks": 0,
            "defStars": 0,
            "defDesPercent": 0,
            "defense": 0,
        })
    join_war_player = set()
    for index, item in enumerate(allClanRounds):
        if isinstance(item, dict) and "#2QCV8UJ8Q" in item:
            mk_rounds.append(item["#2QCV8UJ8Q"])
            for player in item["#2QCV8UJ8Q"]["members"]:
                if 'tag' in player and player["tag"] not in join_war_player:
                    join_war_player.add(player["tag"])
                if 'atkTag' in player and player['atkTag'] not in join_war_player:
                    join_war_player.add(player['atkTag'])
                if 'defTag' in player and player['defTag'] not in join_war_player:
                    join_war_player.add(player['defTag'])

                if 'tag' in player:
                    tag = player.get("tag")
                    atk_stars = player.get("atkStars", 0)
                    atk_des_percent = player.get("atkDesPercent", 0)
                    def_stars = player.get("defStars", 0)
                    def_des_percent = player.get("defDesPercent", 0)

                    mk_players[tag]["rounds"] += 1
                    mk_players[tag]["atkStars"] += atk_stars
                    mk_players[tag]["atkDesPercent"] += atk_des_percent
                    if 'atkTag' in player:
                        mk_players[tag]["attacks"] += 1
                    mk_players[tag]["defStars"] += def_stars
                    mk_players[tag]["defDesPercent"] += def_des_percent
                    if 'defTag' in player:
                        mk_players[tag]["defense"] += 1
        else:
            print(f"Cảnh báo: Phần tử tại chỉ mục {index} không phải là dictionary hợp lệ hoặc thiếu khóa 'a'. Bỏ qua.")

    players = {key:value for key, value in listPlayer.items() if key in join_war_player}

    mk_players_rank = []
    for tag, stats in mk_players.items():
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

    overall_rounds = []
    for index, round in enumerate(allClanRounds):
        roundx = {}
        if isinstance(round, dict):
            for key, value in round.items():
                overall_result[key]["atkStars"] += value.get("stars")
                overall_result[key]["atkDesPercent"] += value.get("desPercent")
                overall_result[key]["attacks"] += value.get("attacks")
                overall_result[key]["defStars"] += value.get("opponentStars")
                overall_result[key]["defDesPercent"] += value.get("opponentDesPercent")
                overall_result[key]["defense"] += value.get("opponentAttacks")
                overall_result[key]["totalStars"] += value.get("stars")
                if value.get("isWinning"):
                    overall_result[key]["totalStars"] += 10

                roundx[key] = {
                    "stars": value.get('stars'),
                    "desPercent": value.get('desPercent'),
                    "attacks": value.get('attacks'),
                    "isWinning": value.get('isWinning'),
                    "opponentStars": value.get('opponentStars'),
                    "opponentDesPercent": value.get('opponentDesPercent'),
                    "opponentAttacks": value.get('opponentAttacks'),
                }
            overall_rounds.append(roundx)
        else:
            print(f"Cảnh báo: Phần tử tại chỉ mục {index} không phải là dictionary hợp lệ. Bỏ qua.")

    with open(round_filepath, 'w', encoding='utf-8') as f:
        json.dump(mk_rounds, f, indent=4)
    round_id = drive_service.upload_json_to_drive(round_filepath, app.config['WL_RP_DRIVE_FOLDER_ID'], num_backups_to_keep=0)

    with open(player_filepath, 'w', encoding='utf-8') as f:
        json.dump(mk_players_rank, f, indent=4)
    player_id = drive_service.upload_json_to_drive(player_filepath, app.config['WL_RP_DRIVE_FOLDER_ID'], num_backups_to_keep=0)

    mk_overall = {
        "state" : data.get('state'),
        "season": data.get('season'),
        "leagueId": data.get('leagueId'),
        "clans" : listClan,
        "players" : players,
        "rounds" : overall_rounds,
        "result": overall_result["#2QCV8UJ8Q"],
        "urls": {"round" : round_id, "player" : player_id}
    }

    with open(overall_filepath, 'w', encoding='utf-8') as f:
        json.dump(mk_overall, f, indent=4)
    drive_service.upload_json_to_drive(overall_filepath, app.config['WL_DRIVE_FOLDER_ID'], num_backups_to_keep=0)
    print(f"\nXử lý {season} hoàn tất.")

def handle_wldata_and_upload():
    base_url = "https://api.clashofstats.com/clans/2QCV8UJ8Q/cwl/seasons/"
    for season in LIST_SEASONS:
        api_url = base_url + season
        data = fetch_data(api_url)
        if data != None:
            process_wl_data(season, data)