import math
import random
from collections import defaultdict
from django.db.models import Q
from ..models import Match, Championship, User

def generate_league_matches(championship, users):
    """Liga tizimi uchun o'yinlar yaratish"""
    Match.objects.filter(championship=championship).delete()
    random.shuffle(users)
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            Match.objects.create(
                championship=championship,
                home_user=users[i],
                away_user=users[j],
                round_name="League"
            )

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
    Playoff bracket yaratish - istalgan sonli jamoalar uchun
    """
    print(f"Generating playoff matches for {len(users)} users")
    Match.objects.filter(championship=championship).delete()
    
    # Jamoalarni random tartiblash
    random.shuffle(users)
    
    total_teams = len(users)
    print(f"Total teams: {total_teams}")
    
    # Eng yaqin 2 ning darajasini topish
    next_power = 2 ** math.ceil(math.log2(total_teams))
    print(f"Next power of 2: {next_power}")
    
    # Raund nomlari va tartiblarini aniqlash
    rounds_info = get_rounds_info(total_teams)
    print(f"Rounds info: {rounds_info}")
    
    # 1-raund o'yinlarini yaratish
    create_first_round_matches(championship, users, rounds_info[0])
    
    # Keyingi raundlarni yaratish (agar kerak bo'lsa)
    if len(rounds_info) > 1:
        create_subsequent_rounds(championship, rounds_info[1:])
    
    # Matchlarni o'zaro bog'lash
    link_all_matches(championship, rounds_info)
    
    # Yaratilgan matchlarni tekshirish
    match_count = Match.objects.filter(championship=championship).count()
    print(f"Created {match_count} matches")

def get_rounds_info(total_teams):
    """
    Raundlar haqida ma'lumot qaytaradi
    """
    next_power = 2 ** math.ceil(math.log2(total_teams))
    rounds = []
    
    round_names = {
        64: "1/64 final",
        32: "1/32 final", 
        16: "1/16 final",
        8: "1/8 final",
        4: "1/4 final",
        2: "Semi-final",
        1: "Final"
    }
    
    matches_count = next_power // 2
    round_order = 1  # 1 dan boshlaymiz
    
    print(f"Generating rounds for {total_teams} teams, next_power={next_power}")
    
    while matches_count >= 1:
        teams_in_round = matches_count * 2
        
        if teams_in_round in round_names:
            round_name = round_names[teams_in_round]
        else:
            round_name = f"1/{teams_in_round} final"
        
        print(f"Round {round_order}: {round_name}, matches={matches_count}, teams={teams_in_round}")
        
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
    
    print(f"Creating first round: {round_info['name']}, byes={byes}")
    
    if byes > 0:
        # Bye (saralash) jamoalari
        bye_teams = users[:byes]
        playing_teams = users[byes:]
        
        print(f"Bye teams: {len(bye_teams)}, Playing teams: {len(playing_teams)}")
        
        # Bye jamoalar uchun matchlar
        for i, team in enumerate(bye_teams):
            match = Match.objects.create(
                championship=championship,
                home_user=team,
                away_user=None,
                round_name=round_info['name'],
                round_order=round_info['order'],
                home_score=0,
                away_score=0,
                is_finished=False,
                bracket_position=i
            )
            print(f"Created bye match {match.id}: {team} - BYE, pos={i}")
        
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
                print(f"Created playing match {match.id}: {playing_teams[i]} vs {playing_teams[i+1]}, pos={byes + (i // 2)}")
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
            print(f"Created match {match.id}: {users[i]} vs {users[i+1]}, pos={i // 2}")

def create_subsequent_rounds(championship, rounds_info_list):
    """
    Keyingi raundlarni yaratish
    """
    for round_info in rounds_info_list:
        matches_count = round_info['matches_count']
        print(f"Creating subsequent round: {round_info['name']} with {matches_count} matches")
        
        for j in range(matches_count):
            match = Match.objects.create(
                championship=championship,
                home_user=None,
                away_user=None,
                round_name=round_info['name'],
                round_order=round_info['order'],
                home_score=0,
                away_score=0,
                is_finished=False,
                bracket_position=j
            )
            print(f"Created empty match {match.id} for round {round_info['name']}, pos={j}")
            
def link_all_matches(championship, rounds_info):
    """
    Barcha matchlarni o'zaro bog'lash
    """
    print(f"Linking matches for championship {championship.id}")
    
    for i in range(len(rounds_info) - 1):
        current_round = rounds_info[i]
        next_round = rounds_info[i + 1]
        
        print(f"Linking round {current_round['name']} (order={current_round['order']}) -> {next_round['name']} (order={next_round['order']})")
        
        current_matches = Match.objects.filter(
            championship=championship,
            round_order=current_round['order']
        ).order_by('bracket_position')
        
        next_matches = Match.objects.filter(
            championship=championship,
            round_order=next_round['order']
        ).order_by('bracket_position')
        
        print(f"Current round matches: {current_matches.count()}")
        print(f"Next round matches: {next_matches.count()}")
        
        current_list = list(current_matches)
        next_list = list(next_matches)
        
        for j, match in enumerate(current_list):
            next_match_index = j // 2
            if next_match_index < len(next_list):
                next_match = next_list[next_match_index]
                match.next_match_id = next_match.id
                match.next_match_position = j % 2  # 0-home, 1-away
                match.save()
                print(f"Linked match {match.id} (pos {j}) to next match {next_match.id} (pos {next_match_index})")
def update_playoff_bracket(match):
    """
    O'yin tugagach, g'olibni keyingi bosqichga o'tkazish
    """
    if not match.is_finished or not match.next_match_id:
        return
    
    winner = match.winner()
    if not winner:
        return
    
    try:
        next_match = Match.objects.get(id=match.next_match_id)
        
        # G'olibni keyingi matchga qo'yish
        if match.next_match_position == 0:  # Home pozitsiyasiga
            next_match.home_user = winner
        else:  # Away pozitsiyasiga
            next_match.away_user = winner
        
        next_match.save()
        
        # Agar keyingi matchda ikkala jamoa ham bo'lsa
        if next_match.home_user and next_match.away_user:
            # Match boshlanishi mumkin
            pass
            
    except Match.DoesNotExist:
        pass

def get_bracket_data(championship_id):
    """
    Bracket uchun ma'lumotlarni tayyorlash
    """
    print(f"\n=== Getting bracket data for championship {championship_id} ===")
    
    matches = Match.objects.filter(
        championship_id=championship_id
    ).order_by('round_order', 'bracket_position')
    
    print(f"Found {matches.count()} matches")
    
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
        
        match_data = {
            'id': match.id,
            'home_user': match.home_user,
            'away_user': match.away_user,
            'home_score': match.home_score,
            'away_score': match.away_score,
            'is_finished': match.is_finished,
            'winner': match.winner() if match.is_finished else None,
            'bracket_position': match.bracket_position or 0,
            'round_order': round_order,
        }
        
        bracket_dict[round_name]['matches'].append(match_data)
        print(f"Match {match.id}: {round_name} (order={round_order}), pos={match.bracket_position}")
    
    # Raundlarni order bo'yicha tartiblash
    sorted_bracket = sorted(bracket_dict.values(), key=lambda x: x['order'])
    
    # Har bir raunddagi matchlarni bracket_position bo'yicha tartiblash
    for round_data in sorted_bracket:
        round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    print(f"\nReturning {len(sorted_bracket)} rounds:")
    for round_data in sorted_bracket:
        print(f"  {round_data['name']} (order={round_data['order']}): {len(round_data['matches'])} matches")
    
    return sorted_bracket

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