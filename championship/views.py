from urllib import request
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.urls import reverse
from championship.services.services import *
from .models import *
from .permissions import admin_only
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
import uuid
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

# INDEX PAGE
def index(request):
    championships = Championship.objects.filter(
        status__in=['STARTED','FINISHED']
    ).order_by('-created_at')

    users = User.objects.filter(role='USER')

    if request.user.is_authenticated and request.user.role == 'ADMIN':
        championships = Championship.objects.all().order_by('-created_at')
    else:
        championships = Championship.objects.filter(
            status__in=['STARTED','FINISHED',]
        ).order_by('-created_at')

    ratings = []
    for user in users:
        home_matches = Match.objects.filter(home_user=user, is_finished=True)
        away_matches = Match.objects.filter(away_user=user, is_finished=True)
        total_pld = home_matches.count() + away_matches.count()
        total_pts = 0

        for m in home_matches:
            if m.home_score > m.away_score:
                total_pts += 3
            elif m.home_score == m.away_score:
                total_pts += 1

        for m in away_matches:
            if m.away_score > m.home_score:
                total_pts += 3
            elif m.home_score == m.away_score:
                total_pts += 1

        ratings.append({
            'user': user,
            'pld': total_pld,
            'pts': total_pts
        })

    ratings = sorted(ratings, key=lambda x: x['pts'], reverse=True)

    # 🔹 Turnir tanlash
    selected_id = request.GET.get("champ")

    if selected_id:
        latest_champ = get_object_or_404(championships, pk=selected_id)
    else:
        latest_champ = championships.first()

    table_data = []
    participants = []
    available_users = []

    matches = []

    if latest_champ:
        table_data = get_standings(latest_champ.id)
        matches = Match.objects.filter(championship=latest_champ).order_by('id')

        # Hozirgi turnir ishtirokchilari
        participants = ChampionshipParticipant.objects.filter(
            championship=latest_champ
        ).select_related('user')

        participant_ids = participants.values_list('user_id', flat=True)

        # Hali qo'shilmagan o'yinchilar
        available_users = User.objects.filter(
            role='USER'
        ).exclude(id__in=participant_ids)

    context = {
        'championships': championships,
        'ratings': ratings,
        'table': table_data,
        'latest_champ': latest_champ,
        'participants': participants,
        'available_users': available_users,
        'matches': matches,
    }

    return render(request, 'index.html', context)

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Xush kelibsiz, {username}!")
                return redirect('index')
        else:
            messages.error(request, "Username yoki parol xato.")
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('index')

# CHAMPIONSHIP LIST
def championship_list(request):
    championships = Championship.objects.all()
    return render(request, 'championship_list.html', {
        "championships": championships
    })

@admin_only
def add_participant(request, pk):
    championship = get_object_or_404(Championship, pk=pk)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')

        # limit tekshirish
        current_count = ChampionshipParticipant.objects.filter(
            championship=championship
        ).count()

        if current_count >= championship.teams_count:
            messages.error(request, "Limit to‘lib bo‘lgan!")
            return redirect('admin_championship_detail', pk=pk)
        
        if ChampionshipParticipant.objects.filter(
            championship=championship,
            user_id=user_id
        ).exists():
            messages.error(request, "Bu user allaqachon qo‘shilgan!")
            return redirect('admin_championship_detail', pk=pk)

        ChampionshipParticipant.objects.create(
            championship=championship,
            user_id=user_id
        )

        messages.success(request, "Ishtirokchi qo‘shildi!")

    return redirect('admin_championship_detail', pk=pk)

def championship_matches(request, pk):
    matches = Match.objects.filter(
        championship_id=pk
    ).select_related(
        'home_user', 
        'away_user',
        'championship'
    ).prefetch_related(
        'home_user__avatar',  # Agar avatar field bo'lsa
        'away_user__avatar'
    ).order_by('round_name', 'group_label')
    
    # Agar playoff bo'lsa, next_match ni ham olib kelish
    championship = get_object_or_404(Championship, pk=pk)
    if championship.type == 'PLAYOFF':
        matches = matches.select_related('next_match')
    
    return render(request, 'matches_list.html', {
        "matches": matches,
        "championship": championship
    })

def championship_table(request, pk):
    matches = Match.objects.filter(championship_id=pk, is_finished=True)

    table = {}
    for m in matches:
        for user in [m.home_user, m.away_user]:
            if user.id not in table:
                table[user.id] = {"username": user.username, "pts": 0, "gd": 0, "pld": 0}

        table[m.home_user.id]["pld"] += 1
        table[m.away_user.id]["pld"] += 1

        table[m.home_user.id]["gd"] += m.home_score - m.away_score
        table[m.away_user.id]["gd"] += m.away_score - m.home_score

        if m.home_score > m.away_score:
            table[m.home_user.id]["pts"] += 3
        elif m.away_score > m.home_score:
            table[m.away_user.id]["pts"] += 3
        else:
            table[m.home_user.id]["pts"] += 1
            table[m.away_user.id]["pts"] += 1

    return render(request, 'championship_table.html', {
        "table": table.values(),
        "championship": get_object_or_404(Championship, pk=pk)
    })

def update_profile(request):
    user = request.user
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        user.username = username or user.username
        user.email = email or user.email
        user.save()
        status = "Profile updated"
    else:
        status = None

    return render(request, 'profile.html', {
        "user": user,
        "status": status
    })

def create_participant(request, pk):
    championship = get_object_or_404(Championship, pk=pk)

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        team_name = request.POST.get('team_name')  # agar kerak bo'lsa
        ChampionshipParticipant.objects.create(
            championship=championship,
            user_id=user_id,
            team_name=team_name
        )
        status = "Participant added"
    else:
        status = None

    return render(request, 'championship_detail.html', {
        "championship": championship,
        "status": status
    })

@admin_only
def admin_users(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        avatar = request.FILES.get('avatar')

        # 1. Username bazada bor-yo'qligini tekshirish
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Xato: '{username}' nomli username band. Boshqa tanlang.")
            return redirect('admin_users')

        if username:
            try:
                # 2. Foydalanuvchini yaratish
                user = User.objects.create(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    role='USER',
                    avatar=avatar, # Agar avatar bo'lsa saqlaydi, bo'lmasa null ketadi
                    password=make_password(str(uuid.uuid4())) 
                )
                messages.success(request, f"O'yinchi {first_name} muvaffaqiyatli qo'shildi!")
                return redirect('admin_users')
            except Exception as e:
                messages.error(request, f"Kutilmagan xato: {e}")
                return redirect('admin_users')

    users = User.objects.filter(role='USER').order_by('-id')
    return render(request, 'admin_users.html', {"users": users})

@admin_only
def admin_user_detail(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        new_username = request.POST.get('username')
        
        # Username boshqa bironta foydalanuvchiga tegishli emasligini tekshirish
        if User.objects.filter(username=new_username).exclude(pk=pk).exists():
            messages.error(request, f"Xato: '{new_username}' nomli username allaqachon band.")
            return redirect('admin_user_detail', pk=pk)

        target_user.username = new_username
        target_user.first_name = request.POST.get('first_name', target_user.first_name)
        target_user.last_name = request.POST.get('last_name', target_user.last_name)
        
        # Rasmni tekshirish
        if 'avatar' in request.FILES:
            target_user.avatar = request.FILES['avatar']
            
        target_user.save()
        messages.success(request, f"{target_user.first_name} ma'lumotlari yangilandi!")
        return redirect('admin_dashboard')
    
    return render(request, 'admin_user_detail.html', {'target_user': target_user})

@admin_only
def admin_championship_detail(request, pk):
    championship = get_object_or_404(Championship, pk=pk)
    
    if request.method == 'POST':
        # Turnir ma'lumotlarini yangilash
        championship.name = request.POST.get('name', championship.name)
        championship.type = request.POST.get('type', championship.type)
        championship.status = request.POST.get('status', championship.status)
        championship.teams_count = int(request.POST.get('teams_count', championship.teams_count))
        
        # GROUP settings
        if championship.type == 'GROUP':
            championship.group_count = int(request.POST.get('group_count', championship.group_count or 4))
            championship.group_advance_count = int(request.POST.get('group_advance_count', championship.group_advance_count or 1))
        
        # Rasm yuklash
        if 'avatar' in request.FILES:
            championship.avatar = request.FILES['avatar']
        
        championship.save()
        messages.success(request, "Turnir ma'lumotlari muvaffaqiyatli yangilandi!")
        return redirect('admin_championship_detail', pk=pk)

    # FILTERLARNI OLISH
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    # Participants ni bir martada olish
    participants = ChampionshipParticipant.objects.filter(
        championship=championship
    ).select_related('user').only(
        'user__id', 
        'user__username', 
        'user__first_name', 
        'user__last_name',
        'user__avatar'
    )
    
    participant_user_ids = participants.values_list('user_id', flat=True)
    
    # Available users
    available_users = User.objects.filter(
        role='USER'
    ).exclude(
        id__in=participant_user_ids
    ).only('id', 'username', 'first_name', 'last_name')
    
    # Barcha matchlarni olish (filterlarsiz) - BRACKET UCHUN
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user'
    ).order_by('round_order', 'bracket_position')
    
    # Matches list uchun (filterlangan)
    filtered_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user', 'next_match'
    ).order_by('round_order', 'bracket_position', 'id')
    
    # Filterlarni qo'llash (faqat matches list uchun)
    if search_query:
        filtered_matches = filtered_matches.filter(
            Q(home_user__username__icontains=search_query) |
            Q(home_user__first_name__icontains=search_query) |
            Q(away_user__username__icontains=search_query) |
            Q(away_user__first_name__icontains=search_query)
        )
    
    if status_filter == 'finished':
        filtered_matches = filtered_matches.filter(is_finished=True)
    elif status_filter == 'pending':
        filtered_matches = filtered_matches.filter(is_finished=False)
    
    # Bracket data ni to'g'ridan-to'g'ri all_matches dan tayyorlash (SERIALIZABLE VERSION)
    bracket_data = []
    if championship.type == 'PLAYOFF' and all_matches.exists():
        # Raundlar bo'yicha guruhlash
        rounds_dict = {}
        for match in all_matches:
            round_name = match.round_name
            if round_name not in rounds_dict:
                rounds_dict[round_name] = {
                    'name': round_name,
                    'order': match.round_order,
                    'matches': []
                }
            
            # Winner ni aniqlash
            winner = None
            if match.is_finished:
                if match.home_score > match.away_score:
                    winner = match.home_user
                elif match.away_score > match.home_score:
                    winner = match.away_user
            
            # Convert User objects to serializable dictionaries
            home_user_data = None
            if match.home_user:
                home_user_data = {
                    'id': match.home_user.id,
                    'username': match.home_user.username,
                    'first_name': match.home_user.first_name,
                    'last_name': match.home_user.last_name,
                    'avatar_url': match.home_user.avatar.url if match.home_user.avatar else None
                }
            
            away_user_data = None
            if match.away_user:
                away_user_data = {
                    'id': match.away_user.id,
                    'username': match.away_user.username,
                    'first_name': match.away_user.first_name,
                    'last_name': match.away_user.last_name,
                    'avatar_url': match.away_user.avatar.url if match.away_user.avatar else None
                }
            
            winner_data = None
            if winner:
                winner_data = {
                    'id': winner.id,
                    'username': winner.username,
                    'first_name': winner.first_name,
                    'last_name': winner.last_name,
                    'avatar_url': winner.avatar.url if winner.avatar else None
                }
            
            # Match ma'lumotlarini qo'shish
            match_data = {
                'id': match.id,
                'home_user': home_user_data,
                'away_user': away_user_data,
                'home_score': match.home_score,
                'away_score': match.away_score,
                'is_finished': match.is_finished,
                'winner': winner_data,
                'bracket_position': match.bracket_position or 0,
                'round_order': match.round_order,
            }
            rounds_dict[round_name]['matches'].append(match_data)
        
        # Raundlarni order bo'yicha tartiblash
        bracket_data = sorted(rounds_dict.values(), key=lambda x: x['order'])
        
        # Har bir raunddagi matchlarni bracket_position bo'yicha tartiblash
        for round_data in bracket_data:
            round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    table_data = []
    if championship.type == 'LEAGUE' and all_matches.exists():
        table_data = get_standings(championship.id)
    elif championship.type == 'GROUP' and all_matches.exists():
        # GROUP uchun maxsus jadval
        from championship.services import get_group_standings
        table_data = get_group_standings(championship.id)   
    
    matches_list = list(filtered_matches)
    matches_count = len(matches_list)
    matches_exist = all_matches.exists()

    context = {
        'championship': championship,
        'participants': participants,
        'available_users': available_users,
        'matches_exist': matches_exist,
        'matches': matches_list,
        'table': table_data,
        'bracket_data': bracket_data,  # Now this is JSON serializable
        'search_query': search_query,
        'status_filter': status_filter,
        'matches_count': matches_count,
    }
    
    return render(request, 'admin_championship_detail.html', context)

@admin_only
def update_match_score(request, pk):
    if request.method == 'POST':
        match_ids = request.POST.getlist('match_ids')
        home_scores = request.POST.getlist('home_scores')
        away_scores = request.POST.getlist('away_scores')
        finished_flags = request.POST.getlist('finished_flags')  # Yangi qator

        # Xavfsizlik uchun turnirni tekshiramiz
        championship = get_object_or_404(Championship, pk=pk)
        
        updated_count = 0
        for i in range(len(match_ids)):
            match = Match.objects.filter(id=match_ids[i], championship=championship).first()
            if match:
                h_score = int(home_scores[i] or 0)
                a_score = int(away_scores[i] or 0)
                
                match.home_score = h_score
                match.away_score = a_score
                
                # Agar finished_flags mavjud bo'lsa va "on" bo'lsa, True qilamiz
                if i < len(finished_flags) and finished_flags[i] == 'on':
                    match.is_finished = True
                else:
                    # Agar checkbox belgilanmagan bo'lsa, is_finished ni False qilamiz
                    match.is_finished = False
                
                match.save()
                updated_count += 1
        
        messages.success(request, f"{updated_count} ta o'yin natijalari muvaffaqiyatli yangilandi!")
        
    return redirect('admin_championship_detail', pk=pk)

@admin_only
def bulk_add_participants(request, pk):
    championship = get_object_or_404(Championship, pk=pk)

    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')

        current_count = ChampionshipParticipant.objects.filter(
            championship=championship
        ).count()

        available_slots = championship.teams_count - current_count

        if available_slots <= 0:
            messages.error(request, "Turnir to‘lib bo‘lgan!")
            return redirect(f"/?champ={pk}")

        user_ids = user_ids[:available_slots]

        participants = [
            ChampionshipParticipant(championship=championship, user_id=uid)
            for uid in user_ids
        ]

        ChampionshipParticipant.objects.bulk_create(
            participants,
            ignore_conflicts=True
        )

        messages.success(request, "O'yinchilar qo'shildi.")

    return redirect(f"/?champ={pk}")

@admin_only
def generate_matches(request, pk):
    """
    Turnir uchun matchlarni yaratish
    """
    championship = get_object_or_404(Championship, pk=pk)
    
    participants = ChampionshipParticipant.objects.filter(championship=championship)
    
    if participants.count() != championship.teams_count:
        messages.error(request, f"Ishtirokchilar soni {championship.teams_count} ta bo'lishi shart!")
        return redirect('admin_championship_detail', pk=pk)

    users = [p.user for p in participants]
    n = len(users)

    if championship.type == 'LEAGUE':
        total_created = generate_league_matches(championship, users)
        matches_per_team = (n - 1) * championship.matches_per_team
        messages.success(
            request, 
            f"Liga o'yinlari yaratildi! Har bir jamoa {matches_per_team} ta o'yin o'ynaydi. Jami {total_created} ta o'yin."
        )
            
    elif championship.type == 'PLAYOFF':
        # Playoff uchun tekshirish
        if n < 2:
            messages.error(request, "Playoff uchun kamida 2 ta jamoa kerak!")
            return redirect('admin_championship_detail', pk=pk)
        
        if n % 2 != 0:
            messages.error(request, "Playoff uchun jamoalar soni juft bo'lishi kerak!")
            return redirect('admin_championship_detail', pk=pk)
        
        generate_playoff_matches(championship, users)
        messages.success(request, f"Playoff o'yinlari yaratildi! {n} ta jamoa, {n-1} ta o'yin.")

    championship.status = 'STARTED'
    championship.save()

    return redirect('admin_championship_detail', pk=pk)

def generate_league_matches_single(championship, users):
    """Har bir jamoa bir marta o'ynaydigan liga"""
    Match.objects.filter(championship=championship).delete()
    
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            Match.objects.create(
                championship=championship,
                home_user=users[i],
                away_user=users[j],
                round_name="Liga",
                home_score=0,
                away_score=0,
                is_finished=False
            )

def get_championship_data(request, pk):
    championship = get_object_or_404(Championship, pk=pk)
    table_data = get_standings(pk)
    
    participants = ChampionshipParticipant.objects.filter(championship=championship).select_related('user')
    participant_ids = participants.values_list('user_id', flat=True)
    available_users = User.objects.filter(role='USER').exclude(id__in=participant_ids)

    table_html = render_to_string('tournament_table_rows.html', {'table': table_data}, request=request)
    
    admin_html = ""
    if request.user.is_authenticated and (request.user.role == 'ADMIN' or request.user.is_superuser):
        admin_html = render_to_string('admin_tournament_box.html', {
            'latest_champ': championship,
            'available_users': available_users,
            'participants': participants,
            'user': request.user # Userni ham uzating
        }, request=request)

    return JsonResponse({
        'success': True,
        'champ_name': championship.name,
        'table_html': table_html,
        'admin_html': admin_html
    })

@admin_only
def admin_dashboard(request):
    if request.method == "POST":
        username = request.POST.get('username') 
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        avatar = request.FILES.get('avatar')

        if not username or username.strip() == "":
            username = None

        if username is None and not first_name:
            messages.error(request, "Xato: Username yoki Ism kiritilishi shart!")
            return redirect('admin_dashboard')

        if username and User.objects.filter(username=username).exists():
            messages.error(request, f"Xato: '{username}' username band.")
            return redirect('admin_dashboard')

        try:
            User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role='USER',
                avatar=avatar,
                password=make_password(str(uuid.uuid4()))
            )
            messages.success(request, f"{first_name or username} muvaffaqiyatli qo'shildi!")
        except Exception as e:
            messages.error(request, f"Kutilmagan xato: {e}")

        return redirect('admin_dashboard')

    users = User.objects.filter(role='USER').order_by('-id')
    championships = Championship.objects.all().order_by('-created_at')

    return render(request, 'admin_dashboard.html', {
        "users": users,
        "championships": championships
    })

@admin_only
def remove_participant(request, pk, user_id):
    championship = get_object_or_404(Championship, pk=pk)
    participant = get_object_or_404(ChampionshipParticipant, championship=championship, user_id=user_id)

    # GET va POST so'rovlarini qabul qilish
    participant.delete()
    messages.success(request, f"{participant.user.get_full_name() or participant.user.username} turnirdan olib tashlandi!")
    
    return redirect('admin_championship_detail', pk=pk)

@admin_only
def delete_championship(request, pk):
    champ = get_object_or_404(Championship, pk=pk)
    champ.delete()
    messages.success(request, f"{champ.name} muvaffaqiyatli o'chirildi!")
    return redirect('admin_dashboard')

def get_standings(championship_id):
    championship = get_object_or_404(Championship, id=championship_id)
    
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

@admin_only
def create_championship(request):
    users = User.objects.filter(role='USER').order_by('first_name')

    if request.method == 'POST':
        name = request.POST.get('name')
        type_ = request.POST.get('type')
        status = request.POST.get('status', 'DRAFT')

        teams_count = int(request.POST.get('teams_count', 4))
        matches_per_team = int(request.POST.get('matches_per_team', 2))
        win_points = int(request.POST.get('win_points', 3))
        draw_points = int(request.POST.get('draw_points', 1))
        loss_points = int(request.POST.get('loss_points', 0))

        # 🆕 GROUP uchun fieldlar
        group_count = int(request.POST.get('group_count', 4))
        group_advance_count = int(request.POST.get('group_advance_count', 1))

        # 🆕 Avatar faylini olish
        avatar = request.FILES.get('avatar')

        selected_users = request.POST.getlist('users')

        if len(selected_users) != teams_count:
            messages.error(
                request,
                f"Xatolik: Jamoalar soni ({teams_count}) tanlangan o'yinchilar soniga ({len(selected_users)}) teng emas!"            
            )
            return redirect('admin_dashboard')

        championship = Championship.objects.create(
            name=name,
            type=type_,
            teams_count=teams_count,
            matches_per_team=matches_per_team,
            win_points=win_points,
            draw_points=draw_points,
            loss_points=loss_points,
            status=status,
            avatar=avatar,
            # YANGI: GROUP fieldlari
            group_count=group_count,
            group_advance_count=group_advance_count
        )

        participants = [
            ChampionshipParticipant(
                championship=championship,
                user_id=user_id
            )
            for user_id in selected_users
        ]

        ChampionshipParticipant.objects.bulk_create(participants)

        messages.success(
            request,
            f"Turnir '{name}' muvaffaqiyatli yaratildi va {len(participants)} o'yinchi qo'shildi!"
        )

        return redirect('admin_championship_detail', pk=championship.pk)

    return redirect('admin_dashboard')

@admin_only
def admin_delete_user(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    
    username = target_user.username
    target_user.delete()
    messages.success(request, f"O'yinchi @{username} muvaffaqiyatli o'chirildi.")
    
    return redirect('admin_dashboard')

@admin_only
def update_all_scores(request, pk):
    if request.method == 'POST':
        match_ids = request.POST.getlist('match_ids')
        home_scores = request.POST.getlist('home_scores')
        away_scores = request.POST.getlist('away_scores')
        finished_flags = request.POST.getlist('finished_flags')

        championship = get_object_or_404(Championship, pk=pk)
        
        updated_count = 0
        for i in range(len(match_ids)):
            match = Match.objects.filter(id=match_ids[i], championship=championship).first()
            if match:
                h_score = int(home_scores[i] or 0)
                a_score = int(away_scores[i] or 0)
                
                match.home_score = h_score
                match.away_score = a_score
                
                # MUHIM: finished_flags ro'yxatida match_ids[i] bormi?
                # Biz match_ids ni ishlatib, qaysi matchlar tugaganligini aniqlaymiz
                match_id_str = str(match.id)
                
                # finished_flags ro'yxati faqat belgilangan checkboxlar uchun keladi
                # Shuning uchun biz match_ids orqali tekshiramiz
                if match_id_str in request.POST.getlist('finished_match_ids'):
                    match.is_finished = True
                else:
                    match.is_finished = False
                
                match.save()
                updated_count += 1
        
        messages.success(request, f"{updated_count} ta o'yin natijalari muvaffaqiyatli yangilandi!")
        
    return redirect('admin_championship_detail', pk=pk)

@admin_only
def update_single_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    championship_id = match.championship.id
    
    if request.method == 'POST':
        try:
            h_score = int(request.POST.get('home_score', 0))
            a_score = int(request.POST.get('away_score', 0))
            
            if match.home_user and match.away_user:
                if match.championship.type == 'PLAYOFF' and h_score == a_score:
                    error_msg = "Playoffda durang bo'lishi mumkin emas!"
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
                    messages.error(request, error_msg)
                    return redirect(f"{reverse('admin_championship_detail', args=[championship_id])}#match-{match.id}")
                
                match.home_score = h_score
                match.away_score = a_score
                match.is_finished = True
                match.save()
                
                next_match_updated = None
                if match.championship.type == 'PLAYOFF':
                    winner = match.winner()
                    
                    if match.next_match:
                        next_match = match.next_match
                        if match.next_match_position == 0:
                            next_match.home_user = winner
                        else:
                            next_match.away_user = winner
                        next_match.save()
                        next_match_updated = next_match
                    
                    if match.round_name == "Final":
                        match.championship.status = "FINISHED"
                        match.championship.save()
                
                success_msg = f"Natija saqlandi: {h_score}:{a_score}"
                
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    response_data = {
                        'status': 'success',
                        'message': success_msg,
                        'match_id': match.id,
                        'home_score': match.home_score,
                        'away_score': match.away_score,
                        'is_finished': match.is_finished,
                        'winner_id': match.winner().id if match.winner() else None,
                        'next_match_id': match.next_match.id if match.next_match else None,
                    }
                    
                    if match.next_match:
                        response_data['next_match_home_id'] = match.next_match.home_user.id if match.next_match.home_user else None
                        response_data['next_match_away_id'] = match.next_match.away_user.id if match.next_match.away_user else None
                        
                        response_data['next_match_data'] = {
                            'id': next_match_updated.id if next_match_updated else match.next_match.id,
                            'home_user': {
                                'id': match.next_match.home_user.id if match.next_match.home_user else None,
                                'username': match.next_match.home_user.username if match.next_match.home_user else None,
                                'first_name': match.next_match.home_user.first_name if match.next_match.home_user else None,
                                'last_name': match.next_match.home_user.last_name if match.next_match.home_user else None,
                                'avatar_url': match.next_match.home_user.avatar.url if match.next_match.home_user and match.next_match.home_user.avatar else None
                            } if match.next_match.home_user else None,
                            'away_user': {
                                'id': match.next_match.away_user.id if match.next_match.away_user else None,
                                'username': match.next_match.away_user.username if match.next_match.away_user else None,
                                'first_name': match.next_match.away_user.first_name if match.next_match.away_user else None,
                                'last_name': match.next_match.away_user.last_name if match.next_match.away_user else None,
                                'avatar_url': match.next_match.away_user.avatar.url if match.next_match.away_user and match.next_match.away_user.avatar else None
                            } if match.next_match.away_user else None,
                        }
                    
                    if match.championship.type == 'LEAGUE':
                        updated_table = get_standings(match.championship.id)
                        
                        serializable_table = []
                        for entry in updated_table:
                            serializable_entry = {
                                'user': {
                                    'id': entry['user'].id,
                                    'username': entry['user'].username,
                                    'first_name': entry['user'].first_name,
                                    'last_name': entry['user'].last_name,
                                    'avatar_url': entry['user'].avatar.url if entry['user'].avatar else None
                                },
                                'pld': entry['pld'],
                                'w': entry['w'],
                                'd': entry['d'],
                                'l': entry['l'],
                                'gf': entry['gf'],
                                'ga': entry['ga'],
                                'gd': entry['gd'],
                                'pts': entry['pts']
                            }
                            serializable_table.append(serializable_entry)
                        
                        response_data['table_data'] = serializable_table
                    
                    elif match.championship.type == 'PLAYOFF':
                        from .services import get_bracket_data
                        updated_bracket = get_bracket_data(match.championship.id)
                        
                        # Convert to serializable format
                        serializable_bracket = []
                        for round_data in updated_bracket:
                            serializable_round = {
                                'name': round_data['name'],
                                'order': round_data['order'],
                                'matches': []
                            }
                            
                            for match_data in round_data['matches']:
                                # Convert user objects to dictionaries
                                home_user_data = None
                                if match_data['home_user']:
                                    home_user_data = {
                                        'id': match_data['home_user'].id,
                                        'username': match_data['home_user'].username,
                                        'first_name': match_data['home_user'].first_name,
                                        'last_name': match_data['home_user'].last_name,
                                        'avatar_url': match_data['home_user'].avatar.url if match_data['home_user'].avatar else None
                                    }
                                
                                away_user_data = None
                                if match_data['away_user']:
                                    away_user_data = {
                                        'id': match_data['away_user'].id,
                                        'username': match_data['away_user'].username,
                                        'first_name': match_data['away_user'].first_name,
                                        'last_name': match_data['away_user'].last_name,
                                        'avatar_url': match_data['away_user'].avatar.url if match_data['away_user'].avatar else None
                                    }
                                
                                winner_data = None
                                if match_data['winner']:
                                    winner_data = {
                                        'id': match_data['winner'].id,
                                        'username': match_data['winner'].username,
                                        'first_name': match_data['winner'].first_name,
                                        'last_name': match_data['winner'].last_name,
                                        'avatar_url': match_data['winner'].avatar.url if match_data['winner'].avatar else None
                                    }
                                
                                serializable_match = {
                                    'id': match_data['id'],
                                    'home_score': match_data['home_score'],
                                    'away_score': match_data['away_score'],
                                    'is_finished': match_data['is_finished'],
                                    'bracket_position': match_data['bracket_position'],
                                    'round_order': match_data['round_order'],
                                    'home_user': home_user_data,
                                    'away_user': away_user_data,
                                    'winner_id': winner_data['id'] if winner_data else None,
                                    'winner': winner_data
                                }
                                serializable_round['matches'].append(serializable_match)
                            
                            serializable_bracket.append(serializable_round)
                        
                        # Sort rounds by order
                        serializable_bracket.sort(key=lambda x: x['order'])
                        response_data['bracket_data'] = serializable_bracket
                    
                    # GROUP uchun yangilangan jadval
                    elif match.championship.type == 'GROUP':
                        from championship.services import get_group_standings
                        updated_group_table = get_group_standings(match.championship.id)
                        
                        serializable_group_table = []
                        for group in updated_group_table:
                            serializable_group = {
                                'label': group['label'],
                                'standings': []
                            }
                            for entry in group['standings']:
                                serializable_entry = {
                                    'user': {
                                        'id': entry['user'].id,
                                        'username': entry['user'].username,
                                        'first_name': entry['user'].first_name,
                                        'last_name': entry['user'].last_name,
                                        'avatar_url': entry['user'].avatar.url if entry['user'].avatar else None
                                    },
                                    'pld': entry['pld'],
                                    'w': entry['w'],
                                    'd': entry['d'],
                                    'l': entry['l'],
                                    'gf': entry['gf'],
                                    'ga': entry['ga'],
                                    'gd': entry['gd'],
                                    'pts': entry['pts']
                                }
                                serializable_group['standings'].append(serializable_entry)
                            serializable_group_table.append(serializable_group)
                        
                        response_data['group_table_data'] = serializable_group_table
                    
                    return JsonResponse(response_data)
                
                messages.success(request, success_msg)
            else:
                error_msg = "O'yin uchun ikkala jamoa ham mavjud emas!"
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
                messages.error(request, error_msg)
            
        except Exception as e:
            error_msg = f"Xatolik yuz berdi: {str(e)}"
            import traceback
            traceback.print_exc()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': error_msg}, status=500)
            messages.error(request, error_msg)
            
    url = reverse('admin_championship_detail', kwargs={'pk': championship_id})
    return redirect(f"{url}#match-{match.id}")

@admin_only
def generate_matches(request, pk):
    """
    Turnir uchun matchlarni yaratish
    """
    championship = get_object_or_404(Championship, pk=pk)
    
    participants = ChampionshipParticipant.objects.filter(championship=championship)
    
    if participants.count() != championship.teams_count:
        messages.error(request, f"Ishtirokchilar soni {championship.teams_count} ta bo'lishi shart!")
        return redirect('admin_championship_detail', pk=pk)

    users = [p.user for p in participants]
    n = len(users)

    if championship.type == 'LEAGUE':
        total_created = generate_league_matches(championship, users)
        matches_per_team = (n - 1) * championship.matches_per_team
        messages.success(
            request, 
            f"Liga o'yinlari yaratildi! Har bir jamoa {matches_per_team} ta o'yin o'ynaydi. Jami {total_created} ta o'yin."
        )
    
    elif championship.type == 'PLAYOFF':
        # Playoff uchun tekshirish
        if n < 2:
            messages.error(request, "Playoff uchun kamida 2 ta jamoa kerak!")
            return redirect('admin_championship_detail', pk=pk)
        
        if n % 2 != 0:
            messages.error(request, "Playoff uchun jamoalar soni juft bo'lishi kerak!")
            return redirect('admin_championship_detail', pk=pk)
        
        generate_playoff_matches(championship, users)
        messages.success(request, f"Playoff o'yinlari yaratildi! {n} ta jamoa, {n-1} ta o'yin.")
    
    # YANGI: GROUP uchun
    elif championship.type == 'GROUP':
        total_created = generate_group_matches(championship, users)
        messages.success(
            request, 
            f"Guruh bosqichi o'yinlari yaratildi! {championship.group_count} ta guruh, jami {total_created} ta o'yin."
        )

    championship.status = 'STARTED'
    championship.save()

    return redirect('admin_championship_detail', pk=pk)

@admin_only
@require_POST
def toggle_bookmark(request, match_id):
    try:
        match = Match.objects.get(id=match_id)
        user = request.user
        
        user_bookmarks = BookmarkedMatch.objects.filter(user=user)
        
        existing_bookmark = user_bookmarks.filter(match=match).first()
        if existing_bookmark:
            existing_bookmark.delete()
            return JsonResponse({
                'status': 'removed',
                'message': 'Bookmark o\'chirildi',
                'bookmark_count': user_bookmarks.count()
            })
        
        if user_bookmarks.count() >= 3:
            oldest_bookmark = user_bookmarks.last() 
            if oldest_bookmark:
                oldest_bookmark.delete()
        
        bookmark = BookmarkedMatch.objects.create(user=user, match=match)
        
        updated_bookmarks = BookmarkedMatch.objects.filter(user=user).select_related('match')
        bookmarks_data = [{
            'id': bm.id,
            'match_id': bm.match.id,
            'home_user': {
                'id': bm.match.home_user.id if bm.match.home_user else None,
                'name': bm.match.home_user.get_full_name() or bm.match.home_user.username if bm.match.home_user else 'TBD',
                'avatar': bm.match.home_user.avatar.url if bm.match.home_user and bm.match.home_user.avatar else None
            } if bm.match.home_user else None,
            'away_user': {
                'id': bm.match.away_user.id if bm.match.away_user else None,
                'name': bm.match.away_user.get_full_name() or bm.match.away_user.username if bm.match.away_user else 'TBD',
                'avatar': bm.match.away_user.avatar.url if bm.match.away_user and bm.match.away_user.avatar else None
            } if bm.match.away_user else None,
            'score': f"{bm.match.home_score}:{bm.match.away_score}",
            'is_finished': bm.match.is_finished,
            'championship_name': bm.match.championship.name,
            'championship_id': bm.match.championship.id,
            'round_name': bm.match.round_name or 'Guruh bosqichi'
        } for bm in updated_bookmarks]
        
        return JsonResponse({
            'status': 'added',
            'message': 'Bookmark qo\'shildi',
            'bookmark_count': user_bookmarks.count(),
            'bookmarks': bookmarks_data
        })
        
    except Match.DoesNotExist:
        return JsonResponse({'error': 'Match topilmadi'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_user_bookmarks(request):
    """Foydalanuvchining bookmarklarini qaytarish"""
    try:
        bookmarks = BookmarkedMatch.objects.filter(user=request.user).select_related(
            'match', 'match__home_user', 'match__away_user', 'match__championship'
        )[:3]
                
        data = [{
            'id': bm.id,
            'match_id': bm.match.id,
            'home_user': {
                'id': bm.match.home_user.id if bm.match.home_user else None,
                'name': bm.match.home_user.get_full_name() or bm.match.home_user.username if bm.match.home_user else 'TBD',
                'avatar': bm.match.home_user.avatar.url if bm.match.home_user and bm.match.home_user.avatar else None
            } if bm.match.home_user else None,
            'away_user': {
                'id': bm.match.away_user.id if bm.match.away_user else None,
                'name': bm.match.away_user.get_full_name() or bm.match.away_user.username if bm.match.away_user else 'TBD',
                'avatar': bm.match.away_user.avatar.url if bm.match.away_user and bm.match.away_user.avatar else None
            } if bm.match.away_user else None,
            'score': f"{bm.match.home_score}:{bm.match.away_score}",
            'is_finished': bm.match.is_finished,
            'championship_name': bm.match.championship.name,
            'championship_id': bm.match.championship.id,
            'round_name': bm.match.round_name or 'Guruh bosqichi'
        } for bm in bookmarks]
        
        return JsonResponse({'bookmarks': data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

def tournament_public_view(request, pk):
    """
    Turnir ma'lumotlarini faqat o'qish rejimida ko'rsatish (public view)
    - Hech qanday forma, input yoki o'zgartirish imkoniyati yo'q
    - Faqat jadvallar, setkalar va o'yinlar ro'yxati ko'rinadi
    """
    championship = get_object_or_404(Championship, pk=pk)
    
    # Barcha turnirlarni olish (tablar uchun)
    if request.user.is_authenticated and request.user.role == 'ADMIN':
        championships = Championship.objects.all().order_by('-created_at')
    else:
        championships = Championship.objects.filter(
            status__in=['STARTED', 'FINISHED']
        ).order_by('-created_at')
    
    # Faqat STARTED yoki FINISHED turnirlarni ko'rsatish
    if championship.status == 'DRAFT' and not (request.user.is_authenticated and request.user.role == 'ADMIN'):
        messages.error(request, "Bu turnir hali boshlanmagan.")
        return redirect('index')
    
    # Barcha matchlarni olish
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user'
    ).order_by('round_order', 'bracket_position', 'id')
    
    # Turnir jadvali (League uchun)
    table_data = []
    if championship.type == 'LEAGUE' and all_matches.exists():
        table_data = get_standings(championship.id)
    
    # Guruhlar jadvali (Group uchun)
    group_data = []
    if championship.type == 'GROUP' and all_matches.exists():
        from championship.services import get_group_standings
        group_data = get_group_standings(championship.id)
    
    # Playoff setkasi (Playoff uchun)
    bracket_data = []
    if championship.type == 'PLAYOFF' and all_matches.exists():
        # Raundlar bo'yicha guruhlash
        rounds_dict = {}
        for match in all_matches:
            round_name = match.round_name
            if round_name not in rounds_dict:
                rounds_dict[round_name] = {
                    'name': round_name,
                    'order': match.round_order,
                    'matches': []
                }
            
            # Winner ni aniqlash
            winner = None
            if match.is_finished:
                if match.home_score > match.away_score:
                    winner = match.home_user
                elif match.away_score > match.home_score:
                    winner = match.away_user
            
            # Match ma'lumotlarini qo'shish
            match_data = {
                'id': match.id,
                'home_user': match.home_user,
                'away_user': match.away_user,
                'home_score': match.home_score,
                'away_score': match.away_score,
                'is_finished': match.is_finished,
                'winner': winner,
                'bracket_position': match.bracket_position or 0,
                'round_order': match.round_order,
            }
            rounds_dict[round_name]['matches'].append(match_data)
        
        # Raundlarni order bo'yicha tartiblash
        bracket_data = sorted(rounds_dict.values(), key=lambda x: x['order'])
        
        # Har bir raunddagi matchlarni bracket_position bo'yicha tartiblash
        for round_data in bracket_data:
            round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    # Filterlash parametrlari
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    # Filterlangan matchlar (o'yinlar ro'yxati uchun)
    filtered_matches = all_matches
    
    if search_query:
        filtered_matches = filtered_matches.filter(
            Q(home_user__username__icontains=search_query) |
            Q(home_user__first_name__icontains=search_query) |
            Q(away_user__username__icontains=search_query) |
            Q(away_user__first_name__icontains=search_query)
        )
    
    if status_filter == 'finished':
        filtered_matches = filtered_matches.filter(is_finished=True)
    elif status_filter == 'pending':
        filtered_matches = filtered_matches.filter(is_finished=False)
    
    # Ishtirokchilarni olish
    participants = ChampionshipParticipant.objects.filter(
        championship=championship
    ).select_related('user')
    
    # Ratings (HOME PAGE uchun)
    users = User.objects.filter(role='USER')
    ratings = []
    for user in users:
        home_matches = Match.objects.filter(home_user=user, is_finished=True)
        away_matches = Match.objects.filter(away_user=user, is_finished=True)
        total_pld = home_matches.count() + away_matches.count()
        total_pts = 0

        for m in home_matches:
            if m.home_score > m.away_score:
                total_pts += 3
            elif m.home_score == m.away_score:
                total_pts += 1

        for m in away_matches:
            if m.away_score > m.home_score:
                total_pts += 3
            elif m.home_score == m.away_score:
                total_pts += 1

        ratings.append({
            'user': user,
            'pld': total_pld,
            'pts': total_pts
        })

    ratings = sorted(ratings, key=lambda x: x['pts'], reverse=True)
    
    context = {
        'championships': championships,  # MUHIM: tablar uchun
        'championship': championship,
        'matches': filtered_matches,
        'matches_count': filtered_matches.count(),
        'matches_exist': all_matches.exists(),
        'table': table_data,
        'group_data': group_data,
        'bracket_data': bracket_data,
        'participants': participants,
        'search_query': search_query,
        'status_filter': status_filter,
        'ratings': ratings,  # HOME PAGE uchun
        'is_public_view': True,
    }
    
    return render(request, 'index.html', context)

# views.py ga quyidagi funksiyani qo'shing
def tournament_detail_partial(request, pk):
    """
    Turnir ma'lumotlarini qisman yuklash (AJAX uchun)
    """
    championship = get_object_or_404(Championship, pk=pk)
    
    # Barcha matchlarni olish
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user'
    ).order_by('round_order', 'bracket_position', 'id')
    
    # Turnir jadvali (League uchun)
    table_data = []
    if championship.type == 'LEAGUE' and all_matches.exists():
        table_data = get_standings(championship.id)
    
    # Guruhlar jadvali (Group uchun)
    group_data = []
    if championship.type == 'GROUP' and all_matches.exists():
        from championship.services import get_group_standings
        group_data = get_group_standings(championship.id)
    
    # Playoff setkasi (Playoff uchun)
    bracket_data = []
    if championship.type == 'PLAYOFF' and all_matches.exists():
        rounds_dict = {}
        for match in all_matches:
            round_name = match.round_name
            if round_name not in rounds_dict:
                rounds_dict[round_name] = {
                    'name': round_name,
                    'order': match.round_order,
                    'matches': []
                }
            
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
                'round_order': match.round_order,
            }
            rounds_dict[round_name]['matches'].append(match_data)
        
        bracket_data = sorted(rounds_dict.values(), key=lambda x: x['order'])
        for round_data in bracket_data:
            round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    # HTML qismlarini render qilish
    tournament_content_html = render_to_string('tournament_content_partial.html', {
        'championship': championship,
        'table': table_data,
        'group_data': group_data,
        'bracket_data': bracket_data,
        'matches': all_matches,
        'is_public_view': True,
    }, request=request)
    
    return JsonResponse({
        'success': True,
        'html': tournament_content_html,
        'championship_name': championship.name,
    })

