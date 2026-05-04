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
        
        stats['gd'] = stats['gf'] - stats['ga']
        standings.append(stats)
  
    return sorted(standings, key=lambda x: (-x['pts'], -x['gf'], x['ga']))

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
    Playoff bracket yaratish - istalgan sondagi jamoalar uchun mukammal (Byes) mantiqi bilan.
    """
    Match.objects.filter(championship=championship).delete()
    
    users_list = list(users)
    random.shuffle(users_list)
    total_teams = len(users_list)
    
    if total_teams < 2:
        return []
        
    # 1. Eng yaqin 2 ning darajasini topamiz (Masalan, 10 jamoa bo'lsa -> 16 bo'ladi)
    next_power = 2 ** math.ceil(math.log2(total_teams))
    
    # 2. Raundlar ma'lumotini olish
    rounds_info = get_playoff_rounds_info(next_power)
    
    # 3. Zanjirdek bog'langan bo'sh bracket yaratish
    round_matches, all_matches = create_playoff_structure(championship, rounds_info)
    
    # 4. Jamoalarni 1-raundga joylashtirish
    r1_matches = round_matches[1]
    byes_count = next_power - total_teams
    
    # Jamoalarni 2 ga bo'lamiz: Bye oladiganlar va Raund 1 da o'ynaydiganlar
    bye_teams = users_list[:byes_count]
    playing_teams = users_list[byes_count:]
    
    # Byelar (bo'sh o'rinlar) bracketning bir joyiga to'planib qolmasligi uchun
    # ularni simmetrik ravishda (tepa va pastga) taqsimlaymiz
    bye_match_indices = set()
    if byes_count > 0:
        step = len(r1_matches) / byes_count
        for i in range(byes_count):
            bye_match_indices.add(int(i * step))
            
    bye_idx = 0
    play_idx = 0
    
    for i, match in enumerate(r1_matches):
        if i in bye_match_indices and bye_idx < len(bye_teams):
            # Bu o'yinga Bye tushdi (1 ta jamoa bor, raqib yo'q)
            match.home_user = bye_teams[bye_idx]
            match.away_user = None
            match.is_finished = True # Avtomatik g'alaba hisoblanadi
            bye_idx += 1
        else:
            # Standart 2 ta jamoa o'ynaydigan o'yin
            if play_idx < len(playing_teams):
                match.home_user = playing_teams[play_idx]
                match.away_user = playing_teams[play_idx + 1]
                play_idx += 2
        match.save()
        
        # Bye olgan jamoalarni darhol keyingi raundga yuborish
        if match.is_finished:
            from .services import update_playoff_bracket # Yo'lini o'zingizga moslang
            update_playoff_bracket(match)
            
    return all_matches

def get_playoff_rounds_info(next_power):
    """
    Mukammal 2 ning darajasi asosida raundlar tarmog'ini tuzadi
    """
    rounds = []
    matches_count = next_power // 2
    order = 1
    
    while matches_count >= 1:
        if matches_count == 1:
            name = "Final"
        elif matches_count == 2:
            name = "1/2 Final"
        elif matches_count == 4:
            name = "1/4 Final"
        elif matches_count == 8:
            name = "1/8 Final"
        elif matches_count == 16:
            name = "1/16 Final"
        elif matches_count == 32:
            name = "1/32 Final"
        else:
            name = f"Round {order}"
            
        rounds.append({
            'name': name,
            'order': order,
            'matches_count': matches_count
        })
        matches_count //= 2
        order += 1
        
    return rounds

def create_playoff_structure(championship, rounds_info):
    """
    Faqat mukammal zanjir (2->1) bog'laydi. Qandaydir maxsus shartlarsiz.
    """
    round_matches = {}
    all_matches = []
    
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
        
    # Zanjirni ulash qismi (Home: 0, Away: 1)
    for i in range(len(rounds_info) - 1):
        curr_matches = round_matches[rounds_info[i]['order']]
        next_matches = round_matches[rounds_info[i+1]['order']]
        
        for j, match in enumerate(curr_matches):
            match.next_match = next_matches[j // 2]
            match.next_match_position = j % 2 
            match.save()
            
    return round_matches, all_matches
    

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

    except Exception as e:
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
        
    # Guruh o'yinlarini olish
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
        if match.home_user:
            if match.home_user.id not in groups[match.group_label]:
                groups[match.group_label][match.home_user.id] = {
                    'user': match.home_user,
                    'pld': 0, 'w': 0, 'd': 0, 'l': 0,
                    'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0
                }
        
        # Away user
        if match.away_user:
            if match.away_user.id not in groups[match.group_label]:
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
        # TO'G'RI SARALASH:
        # 1. Ochkolar (pts)
        # 2. Urilgan gollar (gf) - kim ko'p gol urgan bo'lsa
        # 3. O'tkazilgan gollar (ga) - kim kam gol o'tkazgan bo'lsa
        standings.sort(key=lambda x: (-x['pts'], -x['gf'], x['ga']))
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
    
    
    # Jamoalarni random tartiblash - BU MUHIM!
    random.shuffle(users)
    
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
                
        start_idx = end_idx
    
    # Qolgan jamoalarni tekshirish
    if start_idx < total_users:
        # Qolgan jamoalarni random guruhlarga qo'shish
        remaining_users = users[start_idx:]
        for i, user in enumerate(remaining_users):
            group_idx = i % group_count
            groups[group_idx]['users'].append(user)
            groups[group_idx]['size'] += 1    
    # Har bir guruh uchun o'yinlar yaratish
    total_matches = 0
    round_order = 1  # Barcha guruh o'yinlari 1-raund deb hisoblanadi
    
    for group in groups:
        group_users = group['users']
        group_label = group['label']
        n = len(group_users)
                
        # Guruhdagi jamoalar soni kamida 2 bo'lishi kerak
        if n < 2:
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
    
    return total_matches