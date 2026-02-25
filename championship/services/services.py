import math
import random
from collections import defaultdict
from django.db.models import Q
from ..models import Match, Championship, User
from django.core.cache import cache

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
    
    # Raundlar haqida ma'lumot
    rounds_info = get_playoff_rounds_info(total_teams)
    
    # Barcha matchlarni yaratish
    all_matches = create_playoff_structure(championship, users, rounds_info)
    
    return all_matches

def get_playoff_rounds_info(total_teams):
    """
    Playoff raundlari haqida ma'lumot qaytaradi
    Masalan: 6 teams -> 1/4 final (2 match), 1/2 final (2 match), Final (1 match)
    """
    if total_teams < 2:
        return []
    
    rounds = []
    remaining_teams = total_teams
    round_order = 1
        
    while remaining_teams > 1:
        matches_count = remaining_teams // 2
        
        # Round nomini aniqlash
        if remaining_teams == 2:
            round_name = "Final"
        elif remaining_teams == 4:
            round_name = "1/2-final"
        elif remaining_teams == 8:
            round_name = "1/4 final"
        elif remaining_teams == 16:
            round_name = "1/8 final"
        elif remaining_teams == 32:
            round_name = "1/16 final"
        elif remaining_teams == 64:
            round_name = "1/32 final"
        else:
            round_name = f"1/{remaining_teams} final"
                
        rounds.append({
            'name': round_name,
            'order': round_order,
            'matches_count': matches_count,
            'teams_count': remaining_teams
        })
        
        remaining_teams = matches_count
        round_order += 1
    
    return rounds

def create_playoff_structure(championship, users, rounds_info):
    """
    Playoff strukturasini yaratish va matchlarni bog'lash
    """
    if not rounds_info:
        return []
    
    total_teams = len(users)
    all_matches = []
    
    # 1. Eng keyingi raunddan boshlab matchlarni yaratish (Final dan boshlab)
    round_matches = {}
    
    for round_info in reversed(rounds_info):
        matches = []
        for i in range(round_info['matches_count']):
            match = Match.objects.create(
                championship=championship,
                home_user=None,
                away_user=None,
                round_name=round_info['name'],
                round_order=round_info['order'],
                bracket_position=i,
                home_score=0,
                away_score=0,
                is_finished=False
            )
            matches.append(match)
            all_matches.append(match)
        
        round_matches[round_info['order']] = matches
    
    # 2. Matchlarni o'zaro bog'lash (oldingi raund -> keyingi raund)
    for i in range(len(rounds_info) - 1):
        current_round = rounds_info[i]
        next_round = rounds_info[i + 1]
        
        current_matches = round_matches[current_round['order']]
        next_matches = round_matches[next_round['order']]
        
        
        for j, match in enumerate(current_matches):
            next_match_index = j // 2
            if next_match_index < len(next_matches):
                next_match = next_matches[next_match_index]
                match.next_match = next_match
                match.next_match_position = j % 2  # 0-home, 1-away
                match.save()
    
    # 3. Birinchi raundga jamoalarni joylashtirish
    first_round = rounds_info[0]
    first_round_matches = round_matches[first_round['order']]
    
    # Jamoalarni matchlarga taqsimlash
    teams_per_match = 2
    total_slots = len(first_round_matches) * teams_per_match
    
    if total_teams > total_slots:
        return all_matches
    
    # Jamoalarni matchlarga joylashtirish
    team_index = 0
    for i, match in enumerate(first_round_matches):
        # Har bir matchga 2 tadan jamoa joylashtirish
        if team_index < total_teams:
            match.home_user = users[team_index]
            team_index += 1
        else:
            match.home_user = None
            
        if team_index < total_teams:
            match.away_user = users[team_index]
            team_index += 1
        else:
            match.away_user = None
        
        match.save()
    
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
    
    if not match.next_match:
        # Final match tugagan bo'lsa, turnirni yakunlash
        if match.round_name == "Final" and match.is_finished:
            match.championship.status = "FINISHED"
            match.championship.save()
        return
    
    try:
        next_match = match.next_match
        
        # G'olibni keyingi matchga qo'yish
        if match.next_match_position == 0:  # Home pozitsiyasiga
            next_match.home_user = winner
        else:  # Away pozitsiyasiga
            next_match.away_user = winner
        
        next_match.save()
        
        # Agar keyingi matchda ikkala jamoa ham bo'lsa
        if next_match.home_user and next_match.away_user:
            print(f"Match {next_match.id} now has both teams ready!")
            
    except Exception as e:
        print(f"Error updating bracket: {e}")

def get_bracket_data(championship_id):
    """
    Bracket uchun ma'lumotlarni tayyorlash
    """
    
    matches = Match.objects.filter(
        championship_id=championship_id
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
            'bracket_position': match.bracket_position or 0,
            'round_order': round_order,
            'next_match_id': match.next_match.id if match.next_match else None,
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