import math
import random
from collections import defaultdict
from django.db.models import Q
from ..models import Match, Championship, User
from django.core.cache import cache
from django.db import models

def get_standings(championship_id):
    championship = Championship.objects.get(id=championship_id)
    
    # Faqat tugagan o'yinlarni olamiz
    matches = Match.objects.filter(
        championship=championship, 
        is_finished=True
    )
    
    # Turnir ishtirokchilari
    participants = User.objects.filter(
        championshipparticipant__championship=championship
    )
    
    standings = []
    for user in participants:
        stats = {
            'user': user, 
            'pld': 0,  # O'yinlar soni
            'w': 0,    # G'alabalar
            'd': 0,    # Duranglar
            'l': 0,    # Mag'lubiyatlar
            'gf': 0,   # Urilgan gollar
            'ga': 0,   # O'tkazilgan gollar
            'gd': 0,   # Farq
            'pts': 0   # Ochkolar
        }
        
        # Userning barcha o'yinlari
        user_matches = matches.filter(
            models.Q(home_user=user) | models.Q(away_user=user)
        )
        
        for m in user_matches:
            stats['pld'] += 1
            
            if m.home_user == user:
                # Home o'yinchi
                stats['gf'] += m.home_score
                stats['ga'] += m.away_score
                
                if m.home_score > m.away_score:
                    stats['w'] += 1
                    stats['pts'] += 3
                elif m.home_score == m.away_score:
                    stats['d'] += 1
                    stats['pts'] += 1
                else:
                    stats['l'] += 1
                    stats['pts'] += 0
            else:
                # Away o'yinchi
                stats['gf'] += m.away_score
                stats['ga'] += m.home_score
                
                if m.away_score > m.home_score:
                    stats['w'] += 1
                    stats['pts'] += 3
                elif m.away_score == m.home_score:
                    stats['d'] += 1
                    stats['pts'] += 1
                else:
                    stats['l'] += 1
                    stats['pts'] += 0
        
        stats['gd'] = stats['gf'] - stats['ga']
        standings.append(stats)
    
    # Ochkolar bo'yicha saralash (agar teng bo'lsa, gol farqi)
    return sorted(standings, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))

def generate_league_matches(championship, users):
    Match.objects.filter(championship=championship).delete()
    
    teams = list(users)
    n = len(teams)
    
    if n % 2 != 0:
        teams.append(None)
        n += 1

    davralar_soni = championship.matches_per_team  # 1 yoki 2
    rounds_per_davra = n - 1
    
    created_count = 0

    for davra in range(1, davralar_soni + 1):
        # Har bir davra boshida jamoalar ro'yxatini asliga qaytaramiz
        # lekin 2-davrada uy/mehmon almashishi uchun rotatsiyani davom ettiramiz
        current_teams = list(teams)
        
        for round_num in range(1, rounds_per_davra + 1):
            for i in range(n // 2):
                home = current_teams[i]
                away = current_teams[n - 1 - i]

                # Agar jamoalardan biri None bo'lmasa (toq bo'lganda None bo'lishi mumkin)
                if home and away:
                    # 2-davrada uy va mehmon jamoa o'rnini almashtiramiz
                    if davra % 2 == 0:
                        home, away = away, home
                    
                    Match.objects.create(
                        championship=championship,
                        home_user=home,
                        away_user=away,
                        round_name=f"{davra}-davra, {round_num}-tur",
                        round_order=((davra - 1) * rounds_per_davra) + round_num,
                        home_score=0,
                        away_score=0,
                        is_finished=False
                    )
                    created_count += 1
            
            # Circle Method rotatsiyasi: birinchi jamoa qoladi, qolganlar soat tili bo'ylab aylanadi
            current_teams = [current_teams[0]] + [current_teams[-1]] + current_teams[1:-1]

    return created_count

def generate_league_matches_simple(championship, users):
    """Liga tizimi uchun o'yinlar yaratish - soddalashtirilgan versiya"""
    Match.objects.filter(championship=championship).delete()
    
    matches_per_pair = championship.matches_per_team
    total_teams = len(users)
    
    matches_created = 0
    
    for i in range(total_teams):
        for j in range(i + 1, total_teams):
            # Birinchi o'yin: i uy, j mehmon
            Match.objects.create(
                championship=championship,
                home_user=users[i],
                away_user=users[j],
                round_name=f"{users[i].first_name or users[i].username} - {users[j].first_name or users[j].username}",
                home_score=0,
                away_score=0,
                is_finished=False
            )
            matches_created += 1
            
            # Agar matches_per_pair = 2 bo'lsa, javob o'yinini ham yaratish
            if matches_per_pair == 2:
                Match.objects.create(
                    championship=championship,
                    home_user=users[j],  # Endi j uy maydonida
                    away_user=users[i],  # i mehmon
                    round_name=f"{users[j].first_name or users[j].username} - {users[i].first_name or users[i].username}",
                    home_score=0,
                    away_score=0,
                    is_finished=False
                )
                matches_created += 1
    
    expected_matches = (total_teams * (total_teams - 1) // 2) * matches_per_pair
    return matches_created

def generate_league_matches_double(championship, users):
    """
    Har bir jamoa ikki marta (uy va mehmonda) o'ynaydigan liga
    n ta jamoa uchun: n * (n-1) ta o'yin
    """
    Match.objects.filter(championship=championship).delete()
    
    n = len(users)
    matches_created = 0
    
    # Birinchi davra (bir marta o'ynash)
    for i in range(n):
        for j in range(i + 1, n):
            # Birinchi o'yin: i uy, j mehmon
            Match.objects.create(
                championship=championship,
                home_user=users[i],
                away_user=users[j],
                round_name="1-davra",
                home_score=0,
                away_score=0,
                is_finished=False
            )
            matches_created += 1
    
    # Ikkinchi davra (javob o'yinlari) - uy/mehmon almashgan holda
    for i in range(n):
        for j in range(i + 1, n):
            # Javob o'yini: j uy, i mehmon
            Match.objects.create(
                championship=championship,
                home_user=users[j],
                away_user=users[i],
                round_name="2-davra",
                home_score=0,
                away_score=0,
                is_finished=False
            )
            matches_created += 1
    
    return matches_created

def generate_group_playoff(championship, users, group_size=4):
    """Guruh bosqichi + playoff"""
    Match.objects.filter(championship=championship).delete()
    
    # Guruhlarga ajratish
    random.shuffle(users)
    groups = [users[i:i+group_size] for i in range(0, len(users), group_size)]
    
    # Guruh o'yinlarini yaratish
    for idx, group in enumerate(groups, start=1):
        group_label = chr(64 + idx)  # A, B, C, ...
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                Match.objects.create(
                    championship=championship,
                    home_user=group[i],
                    away_user=group[j],
                    group_label=group_label,
                    round_name="Groups",
                    round_order=1
                )

def generate_playoff_matches(championship, users):
    """
    Playoff bracket yaratish - istalgan juft sonli jamoalar uchun (2, 4, 6, 8, 10, ...)
    """
    Match.objects.filter(championship=championship).delete()
    
    # Jamoalarni random tartiblash
    random.shuffle(users)
    
    total_teams = len(users)
    print(f"Total teams: {total_teams}")
    
    # Raundlar haqida ma'lumot
    rounds_info = get_playoff_rounds_info(total_teams)
    print(f"Rounds info: {rounds_info}")
    
    # Barcha matchlarni yaratish
    all_matches = create_playoff_structure(championship, users, rounds_info)
    
    print(f"Created {len(all_matches)} matches")
    for match in all_matches:
        print(f"Match {match.id}: {match.round_name}, order={match.round_order}, pos={match.bracket_position}")
    
    return all_matches


def get_playoff_rounds_info(total_teams):
    """
    Har qanday juft sonli jamoalar uchun raundlar strukturasini hisoblaydi.
    """
    if total_teams < 2: 
        return []
    
    print(f"Calculating rounds for {total_teams} teams")
    
    # Eng yaqin kichik 2 ning darajasini topamiz
    next_power_of_2 = 2 ** int(math.log2(total_teams))
    print(f"Next power of 2: {next_power_of_2}")
    
    # 1-raunddagi o'yinlar soni (Play-in)
    first_round_matches = total_teams - next_power_of_2
    print(f"First round matches: {first_round_matches}")
    
    rounds = []
    
    # 1. PLAY-IN ROUND
    if first_round_matches > 0:
        rounds.append({
            'name': "Round 1 (Play-in)",
            'order': 1,
            'matches_count': first_round_matches,
            'is_preliminary': True
        })
        current_round_teams = next_power_of_2
        start_order = 2
        print(f"Added Play-in round with {first_round_matches} matches")
    else:
        current_round_teams = total_teams
        start_order = 1
        print("No Play-in round needed")

    # 2. ASOSIY TO'R
    temp_teams = current_round_teams
    order = start_order
    
    # Round nomlarini to'g'ri belgilash
    round_number = 1
    while temp_teams > 1:
        m_count = temp_teams // 2
        
        if temp_teams == 2:
            name = "Final"
        elif temp_teams == 4:
            name = "1/2 Final"
        elif temp_teams == 8:
            name = "1/4 Final"
        elif temp_teams == 16:
            name = "1/8 Final"
        elif temp_teams == 32:
            name = "1/16 Final"
        elif temp_teams == 64:
            name = "1/32 Final"
        else:
            name = f"Round {order}"
        
        rounds.append({
            'name': name,
            'order': order,
            'matches_count': m_count,
            'is_preliminary': False
        })
        print(f"Added round {order}: {name} with {m_count} matches")
        
        temp_teams //= 2
        order += 1
        round_number += 1
    
    print(f"Total rounds: {len(rounds)}")
    return rounds

def create_playoff_structure(championship, users, rounds_info):
    """
    Playoff bracket yaratish - istalgan juft sonli jamoalar uchun
    """
    random.shuffle(users)
    total_teams = len(users)
    round_matches = {}
    all_matches = []

    # 1. Barcha bo'sh matchlarni yaratib olamiz
    for r_info in rounds_info:
        matches = []
        for i in range(r_info['matches_count']):
            match = Match.objects.create(
                championship=championship,
                round_name=r_info['name'],
                round_order=r_info['order'],
                bracket_position=i
            )
            matches.append(match)
            all_matches.append(match)
        round_matches[r_info['order']] = matches

    # 2. Matchlarni zanjirdek bog'laymiz
    for i in range(len(rounds_info) - 1):
        curr_r = rounds_info[i]
        next_r = rounds_info[i+1]
        
        curr_matches = round_matches[curr_r['order']]
        next_matches = round_matches[next_r['order']]
        
        for j, match in enumerate(curr_matches):
            # Play-in rounddan keyingi roundga ulanish
            if curr_r.get('is_preliminary', False):
                # Play-in rounddagi har bir match keyingi rounddagi mos matchga ulanadi
                # Play-in g'oliblari keyingi roundda AWAY pozitsiyasiga tushadi
                target_match = next_matches[j]
                match.next_match = target_match
                match.next_match_position = 1  # Away pozitsiyasiga
                print(f"Linking Play-in match {match.id} (pos {j}) to next match {target_match.id} as AWAY")
            else:
                # Standart 2->1 ulanish
                target_index = j // 2
                target_match = next_matches[target_index]
                match.next_match = target_match
                match.next_match_position = j % 2  # 0-home, 1-away
                print(f"Linking match {match.id} (pos {j}) to next match {target_match.id} as {'HOME' if j%2==0 else 'AWAY'}")
            match.save()

    # 3. Jamoalarni taqsimlash - TO'G'RILANGAN QISM
    user_idx = 0
    
    # Play-in round mavjudligini tekshirish
    has_play_in = rounds_info[0].get('is_preliminary', False)
    
    if has_play_in:
        # PLAY-IN ROUND - 1-round
        first_round = rounds_info[0]
        first_round_matches = round_matches[first_round['order']]
        
        # Play-in matchlarini to'ldirish
        play_in_matches_count = len(first_round_matches)
        play_in_players_count = play_in_matches_count * 2
        print(f"Play-in players count: {play_in_players_count}")
        
        for m in first_round_matches:
            if user_idx < total_teams:
                m.home_user = users[user_idx]
                user_idx += 1
            if user_idx < total_teams:
                m.away_user = users[user_idx]
                user_idx += 1
            m.save()
            print(f"Play-in match {m.id}: {m.home_user} vs {m.away_user}")
        
        seed_teams_count = total_teams - play_in_players_count
        print(f"Seed teams count: {seed_teams_count}")
        
        if seed_teams_count > 0 and len(rounds_info) > 1:
            second_round = rounds_info[1]  # 1/4 Final
            second_round_matches = round_matches[second_round['order']]
            
            for i in range(seed_teams_count):
                if i < len(second_round_matches):
                    m = second_round_matches[i % len(second_round_matches)]
                    
                    # Birinchi seed jamoalar HOME ga, keyingilari AWAY ga
                    if i < len(second_round_matches):
                        # Birinchi 4 ta seed HOME ga
                        m.home_user = users[user_idx]
                        print(f"Seed match {m.id}: home_user = {users[user_idx]} (seed {i+1})")
                    else:
                        # Qolgan seed jamoalar AWAY ga
                        m.away_user = users[user_idx]
                        print(f"Seed match {m.id}: away_user = {users[user_idx]} (seed {i+1})")
                    
                    user_idx += 1
                    m.save()
            
            # Play-in g'oliblari keyingi roundda AWAY ga tushadi (allaqachon next_match_position=1)
            
    else:
        # STANDART PLAYOFF (2,4,8,16...)
        first_round = rounds_info[0]
        first_round_matches = round_matches[first_round['order']]
        
        for m in first_round_matches:
            if user_idx < total_teams:
                m.home_user = users[user_idx]
                user_idx += 1
            if user_idx < total_teams:
                m.away_user = users[user_idx]
                user_idx += 1
            m.save()
            print(f"First round match {m.id}: {m.home_user} vs {m.away_user}")

    return all_matches

def get_rounds_info(total_teams):
    """
    Raundlar haqida ma'lumot qaytaradi
    """
    # Eng yaqin 2 ning darajasini topamiz (next power of 2)
    next_power = 2 ** math.ceil(math.log2(total_teams))
    rounds = []
    
    round_names = {
        64: "1/64 final",
        32: "1/32 final", 
        16: "1/16 final",
        8: "1/8 final",
        4: "1/4 final",
        2: "1/2 final",
        1: "Final"
    }
    
    matches_count = next_power // 2
    round_order = 1  # 1 - birinchi raund
        
    while matches_count >= 1:
        teams_in_round = matches_count * 2
        
        if teams_in_round in round_names:
            round_name = round_names[teams_in_round]
        else:
            round_name = f"1/{teams_in_round} final"
                
        rounds.append({
            'name': round_name,
            'order': round_order,
            'matches_count': matches_count,
            'teams_count': teams_in_round
        })
        
        matches_count //= 2
        round_order += 1
    
    return rounds

def create_first_round_matches(championship, users, round_info):
    """
    1-raund o'yinlarini yaratish
    """
    total_teams = len(users)
    next_power = 2 ** math.ceil(math.log2(total_teams))
    byes = next_power - total_teams
        
    created_matches = []
    
    if byes > 0:
        # Bye (saralash) jamoalari - to'g'ridan-to'g'ri keyingi bosqichga o'tadi
        bye_teams = users[:byes]
        playing_teams = users[byes:]
                
        # Bye jamoalar uchun matchlar (avtomatik g'alaba)
        for i, team in enumerate(bye_teams):
            match = Match.objects.create(
                championship=championship,
                home_user=team,
                away_user=None,
                round_name=round_info['name'],
                round_order=round_info['order'],
                home_score=0,
                away_score=0,
                is_finished=False,  # Bye match tugamagan, lekin g'olib aniq
                bracket_position=i
            )
            created_matches.append(match)
        
        # Qolgan jamoalar o'rtasidagi o'yinlar
        for i in range(0, len(playing_teams), 2):
            if i + 1 < len(playing_teams):
                match = Match.objects.create(
                    championship=championship,
                    home_user=playing_teams[i],
                    away_user=playing_teams[i+1],
                    round_name=round_info['name'],
                    round_order=round_info['order'],
                    home_score=0,
                    away_score=0,
                    is_finished=False,
                    bracket_position=byes + (i // 2)
                )
                created_matches.append(match)
    else:
        # Oddiy holat - barcha jamoalar o'ynaydi
        for i in range(0, total_teams, 2):
            match = Match.objects.create(
                championship=championship,
                home_user=users[i],
                away_user=users[i+1],
                round_name=round_info['name'],
                round_order=round_info['order'],
                home_score=0,
                away_score=0,
                is_finished=False,
                bracket_position=i // 2
            )
            created_matches.append(match)    
    return created_matches

def link_all_matches(championship, rounds_info):
    """
    Barcha matchlarni o'zaro bog'lash
    """
    
    for i in range(len(rounds_info) - 1):
        current_round = rounds_info[i]
        next_round = rounds_info[i + 1]
        
        current_matches = Match.objects.filter(
            championship=championship,
            round_order=current_round['order']
        ).order_by('bracket_position')
        
        next_matches = Match.objects.filter(
            championship=championship,
            round_order=next_round['order']
        ).order_by('bracket_position')
        
        current_list = list(current_matches)
        next_list = list(next_matches)
                
        for j, match in enumerate(current_list):
            next_match_index = j // 2
            if next_match_index < len(next_list):
                next_match = next_list[next_match_index]
                match.next_match = next_match
                match.next_match_position = j % 2  # 0-home, 1-away
                match.save()
    
def update_playoff_bracket(match):
    """
    O'yin tugagach, g'olibni keyingi bosqichga o'tkazish
    """
    
    if not match.is_finished:
        return
    
    winner = match.winner()
    if not winner:
        return
    
    print(f"Match {match.id} finished. Winner: {winner.username if winner else 'None'}")
    
    if not match.next_match:
        # Final match tugagan bo'lsa, turnirni yakunlash
        if match.round_name == "Final" and match.is_finished:
            match.championship.status = "FINISHED"
            match.championship.save()
            print(f"Tournament finished!")
        return
    
    try:
        next_match = match.next_match
        print(f"Next match {next_match.id} before update: home={next_match.home_user}, away={next_match.away_user}")
        
        # G'olibni keyingi matchga qo'yish
        if match.next_match_position == 0:  # Home pozitsiyasiga
            next_match.home_user = winner
            print(f"Setting winner to HOME position in match {next_match.id}")
        else:  # Away pozitsiyasiga
            next_match.away_user = winner
            print(f"Setting winner to AWAY position in match {next_match.id}")
        
        next_match.save()
        
        # Agar keyingi matchda ikkala jamoa ham bo'lsa
        if next_match.home_user and next_match.away_user:
            print(f"Match {next_match.id} now has both teams ready!")
            
    except Exception as e:
        print(f"Error updating bracket: {e}")
        import traceback
        traceback.print_exc()

def get_bracket_data(championship_id):
    """
    Bracket uchun ma'lumotlarni tayyorlash
    """
    matches = Match.objects.filter(
        championship_id=championship_id
    ).select_related(
        'home_user', 'away_user'
    ).order_by('round_order', 'bracket_position')
    
    # Raundlar bo'yicha guruhlash
    bracket_dict = {}
    
    for match in matches:
        round_name = match.round_name or "Unknown"
        round_order = match.round_order or 0
        
        if round_name not in bracket_dict:
            bracket_dict[round_name] = {
                'name': round_name,
                'order': round_order,
                'matches': []
            }
        
        # G'olibni aniqlash
        winner = None
        if match.is_finished:
            if match.home_score > match.away_score:
                winner = match.home_user
            elif match.away_score > match.home_score:
                winner = match.away_user
        
        match_data = {
            'id': match.id,
            'home_user': match.home_user,
            'away_user': match.away_user,
            'home_score': match.home_score,
            'away_score': match.away_score,
            'is_finished': match.is_finished,
            'winner': winner,
            'winner_id': winner.id if winner else None,
            'bracket_position': match.bracket_position or 0,
            'round_order': round_order,
        }
        
        bracket_dict[round_name]['matches'].append(match_data)
    
    # Raundlarni order bo'yicha tartiblash
    sorted_bracket = sorted(bracket_dict.values(), key=lambda x: x['order'])
    
    # Har bir raunddagi matchlarni bracket_position bo'yicha tartiblash
    for round_data in sorted_bracket:
        round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    return sorted_bracket

def get_bracket_data_cached(championship_id):
    """
    Bracket ma'lumotlarini cache bilan qaytarish
    """
    cache_key = f'bracket_data_{championship_id}'
    data = cache.get(cache_key)
    
    if data is None:
        # Agar cache bo'lmasa, yangidan hisobla
        data = get_bracket_data(championship_id)
        # 5 daqiqaga cache ga saqla (300 sekund)
        cache.set(cache_key, data, 300)
    
    return data

def check_playoff_completion(championship):
    """
    Playoff tugaganligini tekshirish
    """
    final_matches = Match.objects.filter(
        championship=championship,
        round_name="Final"
    )
    
    if final_matches.exists() and final_matches.first().is_finished:
        championship.status = "FINISHED"
        championship.save()
        
def check_playoff_completion(championship):
    """
    Playoff tugaganligini tekshirish
    """
    final_matches = Match.objects.filter(
        championship=championship,
        round_name="Final"
    )
    
    if final_matches.exists() and final_matches.first().is_finished:
        championship.status = "FINISHED"
        championship.save()

def get_group_standings(championship_id):
    """
    Guruhlar bo'yicha jadvalni qaytaradi
    """
    try:
        championship = Championship.objects.get(id=championship_id)
    except Championship.DoesNotExist:
        return []
    
    # Guruh o'yinlarini olish (tugagan va tugamagan)
    matches = Match.objects.filter(
        championship=championship
    ).exclude(group_label__isnull=True).exclude(group_label='')
    
    # Guruhlar bo'yicha guruhlash
    groups = {}
    
    # Guruhdagi barcha jamoalarni olish
    for match in matches:
        if match.group_label not in groups:
            groups[match.group_label] = {}
        
        # Home user
        if match.home_user and match.home_user.id not in groups[match.group_label]:
            groups[match.group_label][match.home_user.id] = {
                'user': match.home_user,
                'pld': 0, 'w': 0, 'd': 0, 'l': 0,
                'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0
            }
        
        # Away user
        if match.away_user and match.away_user.id not in groups[match.group_label]:
            groups[match.group_label][match.away_user.id] = {
                'user': match.away_user,
                'pld': 0, 'w': 0, 'd': 0, 'l': 0,
                'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0
            }
    
    # Faqat tugagan o'yinlar uchun statistikani hisoblash
    finished_matches = matches.filter(is_finished=True)
    
    for match in finished_matches:
        group_label = match.group_label
        
        if group_label not in groups:
            continue
        
        # Home user statistikasi
        if match.home_user:
            home_id = match.home_user.id
            if home_id in groups[group_label]:
                stats = groups[group_label][home_id]
                stats['pld'] += 1
                stats['gf'] += match.home_score
                stats['ga'] += match.away_score
                
                if match.home_score > match.away_score:
                    stats['w'] += 1
                    stats['pts'] += 3
                elif match.home_score == match.away_score:
                    stats['d'] += 1
                    stats['pts'] += 1
                else:
                    stats['l'] += 1
        
        # Away user statistikasi
        if match.away_user:
            away_id = match.away_user.id
            if away_id in groups[group_label]:
                stats = groups[group_label][away_id]
                stats['pld'] += 1
                stats['gf'] += match.away_score
                stats['ga'] += match.home_score
                
                if match.away_score > match.home_score:
                    stats['w'] += 1
                    stats['pts'] += 3
                elif match.away_score == match.home_score:
                    stats['d'] += 1
                    stats['pts'] += 1
                else:
                    stats['l'] += 1
    
    # GD hisoblash
    for group_label, users_dict in groups.items():
        for user_id, stats in users_dict.items():
            stats['gd'] = stats['gf'] - stats['ga']
    
    # Guruhlarni tartiblash va chiqish
    result = []
    for group_label in sorted(groups.keys()):
        standings = list(groups[group_label].values())
        # Ochkolar, gol farqi, urilgan gollar bo'yicha tartiblash
        standings.sort(key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
        result.append({
            'label': group_label,
            'standings': standings
        })
    
    return result

def generate_group_matches(championship, users):
    """
    GROUP tizimi uchun o'yinlar yaratish - guruhlarga random taqsimlash
    Guruhlar A, B, C, D... ko'rinishida nomlanadi
    """
    Match.objects.filter(championship=championship).delete()
    
    total_users = len(users)
    group_count = championship.group_count  # Nechta guruh
    
    # Guruhlar sonini tekshirish
    if group_count <= 0:
        group_count = 4  # Default
    
    print(f"Generating groups: {group_count} groups, {total_users} users")
    print(f"Users before shuffling: {[u.username for u in users]}")
    
    # Jamoalarni random tartiblash - BU MUHIM!
    random.shuffle(users)
    print(f"Users after shuffling: {[u.username for u in users]}")
    
    # Guruhlarga ajratish (teng taqsimlash)
    groups = []
    base_size = total_users // group_count
    remainder = total_users % group_count
    
    # Har bir guruhdagi jamoalar sonini aniqlash
    group_sizes = []
    for i in range(group_count):
        if i < remainder:
            group_sizes.append(base_size + 1)
        else:
            group_sizes.append(base_size)
    
    print(f"Group sizes: {group_sizes}")
    
    # Jamoalarni guruhlarga random taqsimlash
    # Buning uchun users ro'yxatini random tartiblab, keyin ketma-ket guruhlarga joylaymiz
    start_idx = 0
    for i in range(group_count):
        group_size = group_sizes[i]
        end_idx = start_idx + group_size
        
        # Guruh uchun jamoalarni olish
        group_users = users[start_idx:end_idx]
        
        # Guruh labeli: A, B, C, D... (65 = 'A' ASCII)
        group_label = chr(65 + i)
        
        # Guruh ichida ham jamoalarni random tartiblash (ixtiyoriy)
        random.shuffle(group_users)
        
        groups.append({
            'label': group_label,
            'users': group_users,
            'size': group_size
        })
        
        print(f"Group {group_label}: {[u.username for u in group_users]}")
        
        start_idx = end_idx
    
    # Qolgan jamoalarni tekshirish
    if start_idx < total_users:
        print(f"Warning: {total_users - start_idx} users left unassigned!")
        # Qolgan jamoalarni random guruhlarga qo'shish
        remaining_users = users[start_idx:]
        for i, user in enumerate(remaining_users):
            group_idx = i % group_count
            groups[group_idx]['users'].append(user)
            groups[group_idx]['size'] += 1
            print(f"Added {user.username} to group {groups[group_idx]['label']}")
    
    # Har bir guruh uchun o'yinlar yaratish
    total_matches = 0
    round_order = 1  # Barcha guruh o'yinlari 1-raund deb hisoblanadi
    
    for group in groups:
        group_users = group['users']
        group_label = group['label']
        n = len(group_users)
        
        print(f"Creating matches for Group {group_label} with {n} teams: {[u.username for u in group_users]}")
        
        # Guruhdagi jamoalar soni kamida 2 bo'lishi kerak
        if n < 2:
            print(f"Group {group_label} has less than 2 teams, skipping")
            continue
        
        # Guruh ichida random o'yinlar tartibini yaratish
        # Har bir jamoa bir-biri bilan o'ynaydi (League usulida)
        
        # O'yinlar ro'yxatini yaratish
        matches_list = []
        for i in range(n):
            for j in range(i + 1, n):
                # Birinchi o'yin (home i, away j)
                matches_list.append({
                    'home': group_users[i],
                    'away': group_users[j],
                    'is_first': True
                })
                
                # Agar matches_per_team = 2 bo'lsa, javob o'yini
                if championship.matches_per_team == 2:
                    matches_list.append({
                        'home': group_users[j],
                        'away': group_users[i],
                        'is_first': False
                    })
        
        # O'yinlar tartibini randomlashtirish
        random.shuffle(matches_list)
        print(f"Group {group_label}: Created {len(matches_list)} matches in random order")
        
        # O'yinlarni yaratish
        for match_data in matches_list:
            Match.objects.create(
                championship=championship,
                home_user=match_data['home'],
                away_user=match_data['away'],
                round_name=f"Guruh {group_label}",
                round_order=round_order,
                group_label=group_label,
                home_score=0,
                away_score=0,
                is_finished=False
            )
            total_matches += 1
    
    print(f"Total matches created: {total_matches}")
    return total_matches