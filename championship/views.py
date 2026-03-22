from django.utils.translation import activate
from django.conf import settings
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
from django.http import HttpResponseRedirect, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
import json
from django.utils import timezone
from datetime import datetime
from django.utils.translation import gettext as _
from django.utils import translation

# INDEX PAGE
def index(request):
    championships = Championship.objects.filter(
        status__in=['STARTED','FINISHED']
    ).order_by('-created_at')

    if request.user.is_authenticated and request.user.role == 'ADMIN':
        championships = Championship.objects.all().order_by('-created_at')
    else:
        championships = Championship.objects.filter(
            status__in=['STARTED','FINISHED',]
        ).order_by('-created_at')

    # RATING USERLAR - faqat ratingda ko'rinadigan userlar
    rating_users = User.objects.filter(
        role='USER',
        type_settings__in_rating=True
    )
    
    ratings = []
    for user in rating_users:
        rating, created = UserRating.objects.get_or_create(
            user=user,
            defaults={
                'games_played': 0,
                'points': 0
            }
        )
        ratings.append(rating)
    
    ratings = sorted(ratings, key=lambda x: (-x.points, -x.games_played))

    # Turnir tanlash
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

        # TURNIR ISHTIROKCHILARI - faqat tournament userlari
        participants = ChampionshipParticipant.objects.filter(
            championship=latest_champ
        ).select_related('user')

        participant_ids = participants.values_list('user_id', flat=True)

        # TURNIRGA QO'SHISH UCHUN USERLAR - faqat tournament userlari
        available_users = User.objects.filter(
            role='USER',
            type_settings__in_tournament=True
        ).exclude(id__in=participant_ids)

    champion_halls = ChampionHall.objects.select_related('user').order_by('-tournament_date')
    
    # User bo'yicha guruhlash
    user_champions = {}
    for champ in champion_halls:
        user_id = champ.user.id
        if user_id not in user_champions:
            user_champions[user_id] = {
                'user': champ.user,
                'champions': []
            }
        user_champions[user_id]['champions'].append(champ)
    
    # Sort qilish
    for user_data in user_champions.values():
        user_data['champions'].sort(key=lambda x: (-x.year, x.position))
    

    context = {
        'championships': championships,
        'ratings': ratings,
        'table': table_data,
        'latest_champ': latest_champ,
        'participants': participants,
        'available_users': available_users,
        'matches': matches,
        'user_champions': user_champions.values(),
        'total_champions': champion_halls.count(),
        'is_admin': request.user.is_authenticated and request.user.role == 'ADMIN',
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
        'home_user__avatar',
        'away_user__avatar'
    ).order_by('round_name', 'group_label')
    
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
        team_name = request.POST.get('team_name')
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
        source_tab = request.POST.get('source_tab', 'users')  # users tab
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        nation = request.POST.get('nation', 'UZ')
        avatar = request.FILES.get('avatar')
        user_type = request.POST.get('user_type', 'ALL')
        
        # UserType settings
        in_tournament = request.POST.get('in_tournament') == 'on'
        in_rating = request.POST.get('in_rating') == 'on'
        in_champions = request.POST.get('in_champions') == 'on'

        # Validatsiya: username, first_name, last_name dan kamida bittasi kiritilishi kerak
        if not username and not first_name and not last_name:
            messages.error(request, "Xato: Username, Ism yoki Familiyadan kamida bittasini kiriting!")
            response = redirect('admin_dashboard')
            response['Location'] += f'#{source_tab}-tab'
            return response

        # Username takrorlanishini tekshirish (agar username kiritilgan bo'lsa)
        if username and User.objects.filter(username=username).exists():
            messages.error(request, f"Xato: '{username}' nomli username band. Boshqa tanlang.")
            response = redirect('admin_dashboard')
            response['Location'] += f'#{source_tab}-tab'
            return response

        try:
            # Agar username kiritilmagan bo'lsa, avtomatik username yaratish
            if not username:
                base_username = (first_name or last_name or 'user').lower().replace(' ', '')
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

            user = User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role='USER',
                nation=nation,
                avatar=avatar,
                user_type=user_type,
                password=make_password(str(uuid.uuid4()))
            )
            
            # UserType yaratish va sozlash
            type_settings, created = UserType.objects.get_or_create(user=user)
            type_settings.in_tournament = in_tournament
            type_settings.in_rating = in_rating
            type_settings.in_champions = in_champions
            type_settings.save()
            
            # UserRating faqat in_rating=True bo'lsa yaratiladi
            if in_rating:
                UserRating.objects.get_or_create(user=user, defaults={'games_played': 0, 'points': 0})
            else:
                # Agar mavjud bo'lsa o'chirish
                UserRating.objects.filter(user=user).delete()
            
            name = first_name or last_name or "Noma'lum"
            messages.success(request, f"O'yinchi {name} muvaffaqiyatli qo'shildi!")   
            
        except Exception as e:
            messages.error(request, f"Kutilmagan xato: {e}")
        
        # Qaysi tabga qaytish kerak
        response = redirect('admin_dashboard')
        response['Location'] += f'#{source_tab}-tab'
        return response

    users = User.objects.filter(role='USER').select_related('type_settings').order_by('-id')
    return render(request, 'admin_users.html', {"users": users})

@admin_only
def admin_user_detail(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        new_username = request.POST.get('username', '').strip()
        
        if new_username:
            if User.objects.filter(username=new_username).exclude(pk=pk).exists():
                messages.error(request, f"Xato: '{new_username}' nomli username allaqachon band.")
                return redirect('admin_user_detail', pk=pk)
            target_user.username = new_username
        
        first_name = request.POST.get('first_name', '').strip()
        if first_name:
            target_user.first_name = first_name
            
        last_name = request.POST.get('last_name', '').strip()
        if last_name:
            target_user.last_name = last_name
            
        nation = request.POST.get('nation', '').strip()
        if nation:
            target_user.nation = nation
        
        user_type = request.POST.get('user_type', '')
        if user_type:
            target_user.user_type = user_type
        
        # UserType settings (qaysi sectionlarda ko'rinishi)
        type_settings, created = UserType.objects.get_or_create(user=target_user)
        type_settings.in_tournament = request.POST.get('in_tournament') == 'on'
        type_settings.in_rating = request.POST.get('in_rating') == 'on'
        type_settings.in_champions = request.POST.get('in_champions') == 'on'
        type_settings.save()
        
        if 'avatar' in request.FILES:
            target_user.avatar = request.FILES['avatar']
            
        target_user.save()
        messages.success(request, f"{target_user.first_name or target_user.username} ma'lumotlari yangilandi!")
        return redirect('admin_dashboard')
    
    # UserType ni olish yoki yaratish
    type_settings, created = UserType.objects.get_or_create(user=target_user)
    
    return render(request, 'admin_user_detail.html', {
        'target_user': target_user,
        'type_settings': type_settings
    })

@admin_only
def admin_championship_detail(request, pk):
    championship = get_object_or_404(Championship, pk=pk)
    
    if request.method == 'POST':
        championship.name = request.POST.get('name', championship.name)
        championship.type = request.POST.get('type', championship.type)
        championship.status = request.POST.get('status', championship.status)
        championship.teams_count = int(request.POST.get('teams_count', championship.teams_count))
        
        if championship.type == 'GROUP':
            championship.group_count = int(request.POST.get('group_count', championship.group_count or 4))
            championship.group_advance_count = int(request.POST.get('group_advance_count', championship.group_advance_count or 1))
        
        if 'avatar' in request.FILES:
            championship.avatar = request.FILES['avatar']
        
        championship.save()
        messages.success(request, "Turnir ma'lumotlari muvaffaqiyatli yangilandi!")
        return redirect('admin_championship_detail', pk=pk)

    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
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
    
    # TURNIR UCHUN USERLAR - faqat tournament userlari
    available_users = User.objects.filter(
        role='USER',
        type_settings__in_tournament=True
    ).exclude(
        id__in=participant_user_ids
    ).only('id', 'username', 'first_name', 'last_name')
    
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user'
    ).order_by('round_order', 'bracket_position')
    
    filtered_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user', 'next_match'
    ).order_by('round_order', 'bracket_position', 'id')
    
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
        
        bracket_data = sorted(rounds_dict.values(), key=lambda x: x['order'])
        
        for round_data in bracket_data:
            round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    table_data = []
    if championship.type == 'LEAGUE' and all_matches.exists():
        table_data = get_standings(championship.id)
    elif championship.type == 'GROUP' and all_matches.exists():
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
        'bracket_data': bracket_data,
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
                
                if i < len(finished_flags) and finished_flags[i] == 'on':
                    match.is_finished = True
                else:
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
    
    # TURNIR UCHUN USERLAR
    available_users = User.objects.filter(
        role='USER',
        type_settings__in_tournament=True
    ).exclude(id__in=participant_ids)

    table_html = render_to_string('tournament_table_rows.html', {'table': table_data}, request=request)
    
    admin_html = ""
    if request.user.is_authenticated and (request.user.role == 'ADMIN' or request.user.is_superuser):
        admin_html = render_to_string('admin_tournament_box.html', {
            'latest_champ': championship,
            'available_users': available_users,
            'participants': participants,
            'user': request.user
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
        # POST parametrlaridan qaysi tabdan kelganini aniqlash
        source_tab = request.POST.get('source_tab', 'tournaments')
        action = request.POST.get('action', '')
        
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        nation = request.POST.get('nation', 'UZ')
        avatar = request.FILES.get('avatar')
        user_type = request.POST.get('user_type', 'ALL')
        
        # UserType settings
        in_tournament = request.POST.get('in_tournament') == 'on'
        in_rating = request.POST.get('in_rating') == 'on'
        in_champions = request.POST.get('in_champions') == 'on'

        # Validatsiya: username, first_name, last_name dan kamida bittasi kiritilishi kerak
        if not username and not first_name and not last_name:
            messages.error(request, "Xato: Username, Ism yoki Familiyadan kamida bittasini kiriting!")
            # Qaysi tabga qaytish kerakligini aniqlash
            response = redirect('admin_dashboard')
            response['Location'] += f'#{source_tab}-tab'
            return response

        # Username takrorlanishini tekshirish (agar username kiritilgan bo'lsa)
        if username and User.objects.filter(username=username).exists():
            messages.error(request, f"Xato: '{username}' username band.")
            response = redirect('admin_dashboard')
            response['Location'] += f'#{source_tab}-tab'
            return response

        try:
            # Agar username kiritilmagan bo'lsa, avtomatik username yaratish
            if not username:
                base_username = (first_name or last_name or 'user').lower().replace(' ', '')
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

            user = User.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                role='USER',
                nation=nation,
                avatar=avatar,
                user_type=user_type,
                password=make_password(str(uuid.uuid4()))
            )

            # UserType yaratish va sozlash
            type_settings, created = UserType.objects.get_or_create(user=user)
            type_settings.in_tournament = in_tournament
            type_settings.in_rating = in_rating
            type_settings.in_champions = in_champions
            type_settings.save()
            
            # UserRating faqat in_rating=True bo'lsa yaratiladi
            if in_rating:
                UserRating.objects.get_or_create(user=user, defaults={'games_played': 0, 'points': 0})
            else:
                # Agar mavjud bo'lsa o'chirish
                UserRating.objects.filter(user=user).delete()
            name = first_name or last_name or "Noma'lum"
            messages.success(request, f"O'yinchi {name} muvaffaqiyatli qo'shildi!")   
        except Exception as e:
            messages.error(request, f"Kutilmagan xato: {e}")

        # Qaysi tabga qaytish kerakligini aniqlash
        response = redirect('admin_dashboard')
        response['Location'] += f'#{source_tab}-tab'
        return response

    # GET so'rov
    users = User.objects.filter(role='USER').select_related('type_settings').order_by('-id')
    championships = Championship.objects.all().order_by('-created_at')
    
    rating_users = User.objects.filter(
        role='USER',
        type_settings__in_rating=True
    )

    ratings = []
    for user in rating_users:
        rating, created = UserRating.objects.get_or_create(
            user=user,
            defaults={'games_played': 0, 'points': 0}
        )
        ratings.append(rating)
    
    ratings = sorted(ratings, key=lambda x: (-x.points, -x.games_played))
    
    # CHAMPIONS HALL ma'lumotlarini qo'shamiz
    champion_halls = ChampionHall.objects.select_related('user').order_by('-tournament_date')
    
    # User bo'yicha guruhlash
    user_champions = {}
    for champ in champion_halls:
        user_id = champ.user.id
        if user_id not in user_champions:
            user_champions[user_id] = {
                'user': champ.user,
                'champions': []
            }
        user_champions[user_id]['champions'].append(champ)
    
    # Har bir userning championlarini year va position bo'yicha sort qilish
    for user_data in user_champions.values():
        user_data['champions'].sort(key=lambda x: x.tournament_date, reverse=True)

    return render(request, 'admin_dashboard.html', {
        "users": users,
        "championships": championships,
        "ratings": ratings,
        "user_champions": user_champions.values(),
        "total_champions": champion_halls.count(),
    })

@admin_only
def remove_participant(request, pk, user_id):
    championship = get_object_or_404(Championship, pk=pk)
    participant = get_object_or_404(ChampionshipParticipant, championship=championship, user_id=user_id)

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
    
    matches = Match.objects.filter(
        championship=championship, 
        is_finished=True
    )
    
    participants = User.objects.filter(
        championshipparticipant__championship=championship
    )
    
    standings = []
    for user in participants:
        stats = {
            'user': user, 
            'pld': 0,
            'w': 0,
            'd': 0,
            'l': 0,
            'gf': 0,
            'ga': 0,
            'gd': 0,
            'pts': 0
        }
        
        user_matches = matches.filter(
            Q(home_user=user) | Q(away_user=user)
        )
        
        for m in user_matches:
            stats['pld'] += 1
            
            if m.home_user == user:
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
    
    return sorted(standings, key=lambda x: (-x['pts'], -x['gd'], -x['gf']))

@admin_only
def create_championship(request):
    users = User.objects.filter(
        role='USER',
        type_settings__in_tournament=True
    ).order_by('first_name')

    if request.method == 'POST':
        name = request.POST.get('name')
        type_ = request.POST.get('type')
        status = request.POST.get('status', 'DRAFT')

        teams_count = int(request.POST.get('teams_count', 4))
        matches_per_team = int(request.POST.get('matches_per_team', 2))
        win_points = int(request.POST.get('win_points', 3))
        draw_points = int(request.POST.get('draw_points', 1))
        loss_points = int(request.POST.get('loss_points', 0))

        group_count = int(request.POST.get('group_count', 4))
        group_advance_count = int(request.POST.get('group_advance_count', 1))

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
                
                match_id_str = str(match.id)
                
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
                        
                        serializable_bracket = []
                        for round_data in updated_bracket:
                            serializable_round = {
                                'name': round_data['name'],
                                'order': round_data['order'],
                                'matches': []
                            }
                            
                            for match_data in round_data['matches']:
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
                        
                        serializable_bracket.sort(key=lambda x: x['order'])
                        response_data['bracket_data'] = serializable_bracket
                    
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
        if n < 2:
            messages.error(request, "Playoff uchun kamida 2 ta jamoa kerak!")
            return redirect('admin_championship_detail', pk=pk)
        
        if n % 2 != 0:
            messages.error(request, "Playoff uchun jamoalar soni juft bo'lishi kerak!")
            return redirect('admin_championship_detail', pk=pk)
        
        generate_playoff_matches(championship, users)
        messages.success(request, f"Playoff o'yinlari yaratildi! {n} ta jamoa, {n-1} ta o'yin.")
    
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
    try:
        if request.user.is_authenticated:
            bookmarks = BookmarkedMatch.objects.filter(user=request.user).select_related(
                'match', 'match__home_user', 'match__away_user', 'match__championship'
            )[:3]
        else:
            bookmarks = BookmarkedMatch.objects.all().select_related(
                'match', 'match__home_user', 'match__away_user', 'match__championship'
            ).order_by('-created_at')[:3]
            
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
        
        return JsonResponse({
            'success': True,
            'bookmarks': data,
            'is_authenticated': request.user.is_authenticated
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e), 
            'bookmarks': []
        }, status=500)

def tournament_public_view(request, pk):
    championship = get_object_or_404(Championship, pk=pk)
    
    if championship.status == 'DRAFT' and not (request.user.is_authenticated and request.user.role == 'ADMIN'):
        messages.error(request, "Bu turnir hali boshlanmagan.")
        return redirect('index')
    
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related(
        'home_user', 'away_user'
    ).order_by('round_order', 'bracket_position', 'id')
    
    table_data = []
    if championship.type == 'LEAGUE' and all_matches.exists():
        try:
            from championship.services import get_standings
            table_data = get_standings(championship.id)
        except Exception as e:
            print(f"Error in get_standings: {e}")
            table_data = []
    
    group_data = []
    if championship.type == 'GROUP':
        group_matches = all_matches.exclude(group_label__isnull=True).exclude(group_label='')
        
        if group_matches.exists():
            groups_dict = {}
            
            for match in group_matches:
                if match.group_label not in groups_dict:
                    groups_dict[match.group_label] = {}
                
                if match.home_user and match.home_user.id not in groups_dict[match.group_label]:
                    groups_dict[match.group_label][match.home_user.id] = {
                        'user': match.home_user,
                        'pld': 0, 'w': 0, 'd': 0, 'l': 0,
                        'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0
                    }
                
                if match.away_user and match.away_user.id not in groups_dict[match.group_label]:
                    groups_dict[match.group_label][match.away_user.id] = {
                        'user': match.away_user,
                        'pld': 0, 'w': 0, 'd': 0, 'l': 0,
                        'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0
                    }
            
            finished_matches = group_matches.filter(is_finished=True)
            
            for match in finished_matches:
                group_label = match.group_label
                
                if group_label not in groups_dict:
                    continue
                
                if match.home_user:
                    home_id = match.home_user.id
                    if home_id in groups_dict[group_label]:
                        stats = groups_dict[group_label][home_id]
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
                
                if match.away_user:
                    away_id = match.away_user.id
                    if away_id in groups_dict[group_label]:
                        stats = groups_dict[group_label][away_id]
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
            
            for group_label, users_dict in groups_dict.items():
                for user_id, stats in users_dict.items():
                    stats['gd'] = stats['gf'] - stats['ga']
            
            for group_label in sorted(groups_dict.keys()):
                standings = list(groups_dict[group_label].values())
                standings.sort(key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
                
                group_data.append({
                    'label': group_label,
                    'standings': standings
                })
    
    bracket_data = []
    if championship.type == 'PLAYOFF' and all_matches.exists():
        rounds_dict = {}
        
        for match in all_matches.order_by('round_order', 'bracket_position'):
            round_name = match.round_name or f"Round {match.round_order}"
            
            if round_name not in rounds_dict:
                rounds_dict[round_name] = {
                    'name': round_name,
                    'order': match.round_order or 0,
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
                'round_order': match.round_order or 0,
            }
            rounds_dict[round_name]['matches'].append(match_data)
        
        # Raundlarni order bo'yicha tartiblash
        bracket_data = sorted(rounds_dict.values(), key=lambda x: x['order'])
        
        # Har bir raunddagi matchlarni bracket_position bo'yicha tartiblash
        for round_data in bracket_data:
            round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    player_filter = request.GET.get('player', '')
    status_filter = request.GET.get('status', 'all')
    
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related('home_user', 'away_user').order_by('round_order', 'bracket_position', 'id')
    
    filtered_matches = all_matches
    if player_filter:
        filtered_matches = filtered_matches.filter(
            Q(home_user_id=player_filter) | Q(away_user_id=player_filter)
        )
    
    if status_filter == 'finished':
        filtered_matches = filtered_matches.filter(is_finished=True)
    elif status_filter == 'pending':
        filtered_matches = filtered_matches.filter(is_finished=False)
    
    # Turnir ishtirokchilarini olish
    participants = ChampionshipParticipant.objects.filter(
        championship=championship
    ).select_related('user')
    
    group_stats = {
        'total_groups': len(group_data) if championship.type == 'GROUP' else 0,
        'advance_count': championship.group_advance_count if championship.type == 'GROUP' else 0,
        'total_teams': sum(len(g['standings']) for g in group_data) if championship.type == 'GROUP' else 0
    }
    
    context = {
        'championship': championship,
        'matches': filtered_matches,
        'matches_count': filtered_matches.count(),
        'total_matches': all_matches.count(),
        'matches_exist': all_matches.exists(),
        'table': table_data,
        'group_data': group_data,
        'group_stats': group_stats,
        'bracket_data': bracket_data,
        'participants': participants,
        'participants_count': participants.count(),
        'participants': participants,
        'status_filter': status_filter,
        'is_public_view': True,
        'finished_matches_count': all_matches.filter(is_finished=True).count(),
        'pending_matches_count': all_matches.filter(is_finished=False).count(),
        'is_admin': request.user.is_authenticated and request.user.role == 'ADMIN',
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({
            'success': True,
            'group_data': group_data,
            'matches_count': filtered_matches.count(),
        })
    
    return render(request, 'tournament_public_view.html', context)

def tournament_detail_partial(request, pk):
    championship = get_object_or_404(Championship, pk=pk)
    
    player_filter = request.GET.get('player', '')
    status_filter = request.GET.get('status', 'all')
    
    all_matches = Match.objects.filter(
        championship=championship
    ).select_related('home_user', 'away_user').order_by('round_order', 'bracket_position', 'id')
    
    filtered_matches = all_matches
    if player_filter:
        try:
            player_id = int(player_filter)
            filtered_matches = filtered_matches.filter(
                Q(home_user_id=player_id) | Q(away_user_id=player_id)
            )
        except ValueError:
            # Agar player_filter butun son bo‘lmasa, filtrni qo‘llamaymiz
            pass
    
    if status_filter == 'finished':
        filtered_matches = filtered_matches.filter(is_finished=True)
    elif status_filter == 'pending':
        filtered_matches = filtered_matches.filter(is_finished=False)
    
    # Turnir ishtirokchilarini olish
    participants = ChampionshipParticipant.objects.filter(
        championship=championship
    ).select_related('user')
    
    table_data = []
    if championship.type == 'LEAGUE' and all_matches.exists():
        table_data = get_standings(championship.id)
    
    group_data = []
    if championship.type == 'GROUP' and all_matches.exists():
        from championship.services import get_group_standings
        group_data = get_group_standings(championship.id)
    
    # BRACKET DATA
    bracket_data = []
    if championship.type == 'PLAYOFF' and all_matches.exists():
        rounds_dict = {}
        for match in all_matches:
            round_name = match.round_name or f"Round {match.round_order}"
            if round_name not in rounds_dict:
                rounds_dict[round_name] = {
                    'name': round_name,
                    'order': match.round_order or 0,
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
                'round_order': match.round_order or 0,
            }
            rounds_dict[round_name]['matches'].append(match_data)
        
        bracket_data = sorted(rounds_dict.values(), key=lambda x: x['order'])
        
        for round_data in bracket_data:
            round_data['matches'].sort(key=lambda x: x['bracket_position'])
    
    html = render_to_string('tournament_content_partial.html', {
        'championship': championship,
        'table': table_data,
        'group_data': group_data,
        'bracket_data': bracket_data,
        'matches': filtered_matches,
        'matches_count': filtered_matches.count(),
        'participants': participants,
        'status_filter': status_filter,
        'player': player_filter,
        'is_public_view': True,
    }, request=request)
    
    return JsonResponse({
        'success': True,
        'html': html,
        'championship_name': championship.name,
    })

@admin_only
@require_POST
def update_ratings(request):
    try:
        user_ids = request.POST.getlist('user_ids') or request.POST.getlist('user_ids[]')
        games_played = request.POST.getlist('games_played') or request.POST.getlist('games_played[]')
        points = request.POST.getlist('points') or request.POST.getlist('points[]')
        
        print(f"Received - user_ids: {user_ids}, games: {games_played}, points: {points}")
        
        updated_count = 0
        for i in range(len(user_ids)):
            if user_ids[i]:
                games_value = games_played[i] if i < len(games_played) else None
                points_value = points[i] if i < len(points) else None
                
                if (games_value is None or games_value == '') and (points_value is None or points_value == ''):
                    print(f"Skipping user {user_ids[i]} - both values are empty")
                    continue
                
                try:
                    rating = UserRating.objects.get(user_id=user_ids[i])
                    current_games = rating.games_played
                    current_points = rating.points
                except UserRating.DoesNotExist:
                    current_games = 0
                    current_points = 0
                
                update_data = {}
                
                if games_value is not None and games_value != '':
                    try:
                        games_int = int(games_value)
                        update_data['games_played'] = games_int
                    except (ValueError, TypeError):
                        pass
                
                if points_value is not None and points_value != '':
                    try:
                        points_int = int(points_value)
                        update_data['points'] = points_int
                    except (ValueError, TypeError):
                        pass
                
                if not update_data:
                    print(f"No valid data to update for user {user_ids[i]}")
                    continue
                
                rating, created = UserRating.objects.update_or_create(
                    user_id=user_ids[i],
                    defaults=update_data
                )
                updated_count += 1
                print(f"Updated user {user_ids[i]}: {update_data}")
        
        return JsonResponse({
            'success': True,
            'message': f"{updated_count} ta reyting yangilandi",
            'updated_count': updated_count
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
       
@admin_only
def finish_championship(request, pk):
    championship = get_object_or_404(Championship, pk=pk)
    
    if request.method == 'POST':
        championship.status = 'FINISHED'
        championship.save()
        
        messages.success(request, f"Turnir '{championship.name}' yakunlandi!")
        
    return redirect('admin_championship_detail', pk=pk)

def champions_page_data(request):
    champion_halls = ChampionHall.objects.select_related('user').order_by('-year', 'position')
   
    years_data = {}
    for champ in champion_halls:
        if champ.year not in years_data:
            years_data[champ.year] = []
       
        user_data = {
            'id': champ.user.id,
            'name': str(champ.user),
            'first_name': champ.user.first_name or '',
            'last_name': champ.user.last_name or '',
            'username': champ.user.username or '',
            'avatar': champ.user.avatar.url if champ.user.avatar else None,
        }
       
        years_data[champ.year].append({
            'id': champ.id,
            'user': user_data,
            'position': champ.position,
            'position_display': dict(ChampionHall.POSITION_CHOICES).get(champ.position, 'Noma\'lum'),
            'tournament_name': champ.tournament_name,
            'tournament_image': champ.tournament_image.url if champ.tournament_image else None,
        })
   
    sorted_years = sorted(years_data.items(), key=lambda x: x[0], reverse=True)
   
    return JsonResponse({
        'success': True,
        'years': [{'year': year, 'champions': champs} for year, champs in sorted_years],
    })

def champions_page(request):
    return render(request, 'champions_page.html')

@admin_only
def add_champion_hall(request):
    """Champion Hall ga yangi yozuv qo'shish"""
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            position = request.POST.get('position')
            tournament_name = request.POST.get('tournament_name')
            tournament_image = request.FILES.get('tournament_image')
            tournament_date = request.POST.get('tournament_date')  # Yangi maydon
            source_tab = request.POST.get('source_tab', 'champions')
            
            if not all([user_id, position, tournament_name, tournament_date]):
                messages.error(request, "Barcha maydonlarni to'ldiring!")
                response = redirect('admin_dashboard')
                response['Location'] += '#champions-tab'
                return response
            
            user = get_object_or_404(User, id=user_id)
            
            # Sanani parse qilish
            try:
                parsed_date = datetime.strptime(tournament_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                messages.error(request, "Sana formati noto'g'ri!")
                response = redirect('admin_dashboard')
                response['Location'] += '#champions-tab'
                return response
            
            champion_hall = ChampionHall.objects.create(
                user=user,
                position=position,
                tournament_name=tournament_name,
                tournament_image=tournament_image,
                tournament_date=parsed_date
            )
            
            messages.success(request, f"{user} muvaffaqiyatli championlar ro'yxatiga qo'shildi!")
            
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
        
        response = redirect('admin_dashboard')
        response['Location'] += '#champions-tab'
        return response
    
    response = redirect('admin_dashboard')
    response['Location'] += '#champions-tab'
    return response

@admin_only
def edit_champion_hall(request, pk):
    """Champion Hall yozuvini tahrirlash va user uchun yangi champion qo'shish"""
    champion_hall = get_object_or_404(ChampionHall, pk=pk)
    target_user = champion_hall.user
    
    if request.method == 'POST':
        action = request.POST.get('action', 'edit')
        
        if action == 'add':
            # Yangi champion qo'shish
            try:
                position = request.POST.get('new_position')
                tournament_name = request.POST.get('new_tournament_name')
                tournament_image = request.FILES.get('new_tournament_image')
                tournament_date = request.POST.get('new_tournament_date')
                
                if not all([position, tournament_name, tournament_date]):
                    messages.error(request, "Barcha maydonlarni to'ldiring!")
                else:
                    # Sanani parse qilish
                    try:
                        parsed_date = datetime.strptime(tournament_date, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        messages.error(request, "Sana formati noto'g'ri!")
                        return redirect('champion_hall_edit', pk=pk)
                    
                    new_champion = ChampionHall.objects.create(
                        user=target_user,
                        position=position,
                        tournament_name=tournament_name,
                        tournament_image=tournament_image,
                        tournament_date=parsed_date
                    )
                    messages.success(request, f"{target_user} uchun yangi champion qo'shildi!")
                
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")
        
        else:
            # Mavjud championni tahrirlash
            try:
                user_id = request.POST.get('user_id')
                position = request.POST.get('position')
                tournament_name = request.POST.get('tournament_name')
                tournament_image = request.FILES.get('tournament_image')
                tournament_date = request.POST.get('tournament_date')
               
                if not all([user_id, position, tournament_name, tournament_date]):
                    messages.error(request, "Barcha maydonlarni to'ldiring!")
                    return redirect('champion_hall_edit', pk=pk)
               
                champion_hall.user_id = user_id
                champion_hall.position = position
                champion_hall.tournament_name = tournament_name
               
                # Sanani yangilash
                try:
                    champion_hall.tournament_date = datetime.strptime(tournament_date, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    messages.error(request, "Sana formati noto'g'ri!")
                    return redirect('champion_hall_edit', pk=pk)
               
                if tournament_image:
                    if champion_hall.tournament_image:
                        champion_hall.tournament_image.delete(save=False)
                    champion_hall.tournament_image = tournament_image
               
                champion_hall.save()
                messages.success(request, f"Champion ma'lumotlari yangilandi!")
               
            except Exception as e:
                messages.error(request, f"Xatolik: {str(e)}")
                return redirect('champion_hall_edit', pk=pk)
        
        response = redirect('admin_dashboard')
        response['Location'] += '#champions-tab'
        return response
   
    users = User.objects.filter(
        role='USER',
        type_settings__in_champions=True
    ).order_by('first_name', 'last_name')
   
    current_year = timezone.now().year
    years = range(current_year - 10, current_year + 2)
    
    other_champions = ChampionHall.objects.filter(
        user=target_user
    ).exclude(pk=pk).order_by('-tournament_date')
   
    return render(request, 'admin/edit_champion_hall.html', {
        'champion': champion_hall,
        'target_user': target_user,
        'other_champions': other_champions,
        'users': users,
        'years': years,
        'positions': ChampionHall.POSITION_CHOICES,
    })

@admin_only
def champion_hall_delete(request, pk):
    """Champion yozuvini o'chirish"""
    champion = get_object_or_404(ChampionHall, pk=pk)
   
    if request.method == 'POST':
        try:
            user_name = str(champion.user)
            tournament = champion.tournament_name
            
            # Rasmni o'chirish
            if champion.tournament_image:
                champion.tournament_image.delete(save=False)
                
            champion.delete()
            messages.success(request, f"{user_name} - {tournament} championlar ro'yxatidan o'chirildi!")
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
       
        # Champions tabiga qaytish
        response = redirect('admin_dashboard')
        response['Location'] += '#champions-tab'
        return response
   
    # GET so'rov - o'chirishni tasdiqlash sahifasi
    return render(request, 'admin/champion_hall_confirm_delete.html', {
        'champion': champion
    })

@admin_only
def add_champion_to_user(request, user_id):
    """Berilgan user uchun yangi champion qo'shish"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        try:
            position = request.POST.get('position')
            year = request.POST.get('year')
            tournament_name = request.POST.get('tournament_name')
            tournament_image = request.FILES.get('tournament_image')
            
            if not all([position, year, tournament_name]):
                messages.error(request, "Barcha maydonlarni to'ldiring!")
            else:
                champion = ChampionHall.objects.create(
                    user=user,
                    position=position,
                    year=year,
                    tournament_name=tournament_name,
                    tournament_image=tournament_image
                )
                messages.success(request, f"{user} uchun yangi champion qo'shildi!")
            
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
        
        return redirect('user_champions', user_id=user_id)
    
    current_year = timezone.now().year
    years = range(current_year - 10, current_year + 2)
    
    return render(request, 'admin/add_champion_to_user.html', {
        'target_user': user,
        'years': years,
        'positions': ChampionHall.POSITION_CHOICES,
    })

@admin_only
def user_champions(request, user_id):
    """Berilgan userning barcha championlarini ko'rish"""
    user = get_object_or_404(User, id=user_id)
    champions = ChampionHall.objects.filter(user=user).order_by('-year', 'position')
    
    return render(request, 'admin/user_champions.html', {
        'target_user': user,
        'champions': champions,
    })

def champion_detail_data(request, pk):
    """Champion haqida batafsil ma'lumot (JSON)"""
    try:
        champion = get_object_or_404(ChampionHall, pk=pk)
        data = {
            'success': True,
            'champion': {
                'id': champion.id,
                'position': champion.position,
                'position_display': champion.get_position_display(),
                'tournament_name': champion.tournament_name,
                'tournament_image': champion.tournament_image.url if champion.tournament_image else None,
                'formatted_date': champion.get_formatted_date(),
                'user': {
                    'id': champion.user.id,
                    'full_name': str(champion.user),
                    'first_name': champion.user.first_name,
                    'last_name': champion.user.last_name,
                    'username': champion.user.username,
                    'avatar': champion.user.avatar.url if champion.user.avatar else None,
                }
            }
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
@admin_only
def delete_rating(request, user_id):
    """Reytingdan userni o'chirish (faqat rating ma'lumotlarini o'chiradi)"""
    if request.method == 'POST':
        try:
            user = get_object_or_404(User, id=user_id)
            
            # UserRating ni o'chirish
            rating = UserRating.objects.filter(user=user).first()
            if rating:
                rating.delete()
                
                # UserType ni yangilash (in_rating = False qilish)
                type_settings, created = UserType.objects.get_or_create(user=user)
                type_settings.in_rating = False
                type_settings.save()
                
                messages.success(request, f"{user} reytingdan muvaffaqiyatli o'chirildi!")
            else:
                messages.warning(request, f"{user} uchun reyting ma'lumoti topilmadi!")
                
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
    
    # Rating tabiga qaytish
    response = redirect('admin_dashboard')
    response['Location'] += '#ratings-tab'
    return response

@admin_only
def delete_rating_ajax(request, user_id):
    """AJAX orqali reytingdan o'chirish"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            user = get_object_or_404(User, id=user_id)
            rating = UserRating.objects.filter(user=user).first()
            
            if rating:
                rating.delete()
                
                # UserType ni yangilash
                type_settings, created = UserType.objects.get_or_create(user=user)
                type_settings.in_rating = False
                type_settings.save()
                
                return JsonResponse({
                    'success': True,
                    'message': f'{user} reytingdan o\'chirildi!',
                    'user_id': user_id
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Reyting ma\'lumoti topilmadi'
                }, status=404)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def user_champions_api(request, user_id):
    """Userning barcha championlarini yil bo'yicha guruhlab qaytarish"""
    try:
        user = get_object_or_404(User, id=user_id)
        champions = ChampionHall.objects.filter(user=user).order_by('-tournament_date')
        
        # Yil bo'yicha guruhlash
        champions_by_year = {}
        for champ in champions:
            year = champ.tournament_date.year
            if year not in champions_by_year:
                champions_by_year[year] = []
            
            champions_by_year[year].append({
                'id': champ.id,
                'tournament_name': champ.tournament_name,
                'tournament_image': champ.tournament_image.url if champ.tournament_image else None,
                'position': champ.position,
                'position_display': champ.get_position_display(),
                'formatted_date': champ.get_formatted_date(),
            })
        
        # Yillarni kamayish tartibida sort qilish
        sorted_years = dict(sorted(champions_by_year.items(), reverse=True))
        
        data = {
            'success': True,
            'user': {
                'id': user.id,
                'full_name': str(user),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'avatar': user.avatar.url if user.avatar else None,
            },
            'champions_by_year': sorted_years,
            'total_champions': champions.count(),
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

def champion_detail_data(request, pk):
    """Champion haqida batafsil ma'lumot (JSON)"""
    try:
        champion = get_object_or_404(ChampionHall, pk=pk)
        data = {
            'success': True,
            'champion': {
                'id': champion.id,
                'position': champion.position,
                'position_display': champion.get_position_display(),
                'tournament_name': champion.tournament_name,
                'tournament_image': champion.tournament_image.url if champion.tournament_image else None,
                'formatted_date': champion.get_formatted_date(),
                'user': {
                    'id': champion.user.id,
                    'full_name': str(champion.user),
                    'first_name': champion.user.first_name,
                    'last_name': champion.user.last_name,
                    'username': champion.user.username,
                    'avatar': champion.user.avatar.url if champion.user.avatar else None,
                }
            }
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@admin_only
@require_POST
def undo_match(request, match_id):
    """O'yin natijasini qaytarish - matchni 0:0 va tugamagan holatga qaytarish"""
    try:
        match = get_object_or_404(Match, id=match_id)
        
        # Eski natijalarni saqlash (log uchun)
        old_home_score = match.home_score
        old_away_score = match.away_score
        old_is_finished = match.is_finished
        
        # O'yinni tugamagan qilish va hisobni 0:0 qaytarish
        match.home_score = 0
        match.away_score = 0
        match.is_finished = False
        match.save()
        
        # Agar Playoff bo'lsa, keyingi matchlarni tozalash
        if match.championship.type == 'PLAYOFF' and match.next_match:
            next_match = match.next_match
            if match.next_match_position == 0:
                next_match.home_user = None
            else:
                next_match.away_user = None
            next_match.is_finished = False
            next_match.save()
        
        # Agar bu Final bo'lsa va championship FINISHED bo'lsa, uni STARTED ga qaytarish
        if match.round_name == "Final" and match.championship.status == 'FINISHED':
            match.championship.status = 'STARTED'
            match.championship.save()
        
        response_data = {
            'status': 'success',
            'message': f'O\'yin natijasi qaytarildi: {old_home_score}:{old_away_score} -> 0:0',
            'match_id': match.id,
            'home_score': match.home_score,
            'away_score': match.away_score,
            'is_finished': match.is_finished,
        }
        
        # Turnir jadvalini yangilash (agar LEAGUE bo'lsa)
        if match.championship.type == 'LEAGUE':
            from championship.services import get_standings
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
        
        # Guruh jadvalini yangilash (GROUP bo'lsa)
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
        
        # Bracketni yangilash (PLAYOFF bo'lsa)
        elif match.championship.type == 'PLAYOFF':
            from championship.services import get_bracket_data
            updated_bracket = get_bracket_data(match.championship.id)
            
            serializable_bracket = []
            for round_data in updated_bracket:
                serializable_round = {
                    'name': round_data['name'],
                    'order': round_data['order'],
                    'matches': []
                }
                
                for match_data in round_data['matches']:
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
                    
                    serializable_match = {
                        'id': match_data['id'],
                        'home_score': match_data['home_score'],
                        'away_score': match_data['away_score'],
                        'is_finished': match_data['is_finished'],
                        'bracket_position': match_data['bracket_position'],
                        'round_order': match_data['round_order'],
                        'home_user': home_user_data,
                        'away_user': away_user_data,
                        'winner_id': match_data['winner'].id if match_data['winner'] else None,
                    }
                    serializable_round['matches'].append(serializable_match)
                
                serializable_bracket.append(serializable_round)
            
            serializable_bracket.sort(key=lambda x: x['order'])
            response_data['bracket_data'] = serializable_bracket
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'Xatolik: {str(e)}'
        }, status=500)
    

def reglament_view(request):
    """Reglament page view"""
    return render(request, 'reglament.html')
    
def get_reglament_content(request):
    """API endpoint to get reglament content in requested language"""
    lang = request.GET.get('lang', 'uz')
    
    if lang == 'ru':
        # Russian hardcoded content
        content = {
            'reglament': {
                'title': 'Uzbekistan Football e-League — РЕГЛАМЕНТ',
                'sections': [
                    {
                        'title': '1. ОБЩАЯ ИНФОРМАЦИЯ',
                        'points': [
                            '1.1. UFEL (Uzbekistan Football e-League) — лига, организующая турниры по игре eFootball.',
                            '1.2. Турниры проводятся на основе игры eFootball и в соответствии с данным регламентом.',
                            '1.3. Настоящий регламент является обязательным для всех участников.',
                            '1.4. Цель лиги — развитие eFootball в Узбекистане на новом уровне и создание сильной конкурентной среды.'
                        ]
                    },
                    {
                        'title': '2. УЧАСТНИКИ',
                        'points': [
                            '2.1. В лиге могут участвовать все зарегистрированные участники.',
                            '2.2. Администраторы имеют право запрашивать у участников необходимую информацию для участия в турнире.',
                            '2.3. Один участник может участвовать в турнирах только с одного аккаунта.'
                        ]
                    },
                    {
                        'title': '3. ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ',
                        'points': [
                            '3.1. Платформы: PlayStation 4/5, компьютер (PC), Xbox.',
                            '3.2. Для стабильной игры рекомендуется использовать проводное интернет-соединение (LAN).',
                            '3.3. В случае низкой скорости интернета или несоответствия техническим требованиям участник может быть отстранён от турнира.',
                            '3.4. Настройки матча (Match Settings) определяются в зависимости от формата турнира и указываются отдельно в регламенте или объявлении.',
                            '3.5. В случае разрыва соединения или технических проблем во время матча судьи принимают решение о переигровке или сохранении текущего счёта.'
                        ]
                    },
                    {
                        'title': '4. ПОРЯДОК НАЧАЛА МАТЧА',
                        'points': [
                            '4.1. Для проведения матча участники договариваются между собой о удобном времени и связываются друг с другом.',
                            '4.2. Если соперник не отвечает на сообщения или не выходит на связь в назначенное время, необходимо обратиться к администраторам UFEL.',
                            '4.3. Администраторы рассматривают ситуацию и принимают окончательное решение (техническая победа или другое решение).',
                            '4.4. Договорные матчи строго запрещены.'
                        ]
                    },
                    {
                        'title': '5. ПОРЯДОК РАСЧЁТА ТУРНИРНОЙ ТАБЛИЦЫ',
                        'points': [
                            '5.1. В лиге места участников в турнирной таблице определяются по количеству набранных очков.',
                            '5.2. Если количество очков одинаковое, преимущество получает участник, забивший больше голов.',
                            '5.3. Если равны и очки, и количество забитых голов, преимущество получает участник, пропустивший меньше голов.',
                            '5.4. Если все вышеуказанные показатели равны, учитывается результат личной встречи между участниками.',
                            '5.5. В турнирах со специальным форматом (например, ЧМ, ЛЧ и другие) порядок расчёта таблицы может быть установлен отдельным регламентом данного турнира.'
                        ]
                    },
                    {
                        'title': '6. ДИСЦИПЛИНА',
                        'points': [
                            '6.1. Во время турнира все участники должны соблюдать взаимное уважение и спортивный дух.',
                            '6.2. Оскорбления, угрозы или другое неподобающее поведение в группе могут привести к предупреждению или бану.'
                        ]
                    },
                    {
                        'title': '7. ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ',
                        'points': [
                            '7.1. Участник, принимая участие в турнире, автоматически соглашается с данным регламентом.',
                            '7.2. Администраторы UFEL принимают окончательное решение в спорных ситуациях.',
                            '7.3. Администраторы имеют право вносить изменения и дополнения в данный регламент.'
                        ]
                    }
                ]
            },
            'rating': {
                'title': 'РЕЙТИНГОВАЯ СИСТЕМА',
                'description': 'Рейтинговые очки накапливаются в течение одного сезона. Рейтинг рассчитывается по следующим правилам.',
                'sections': [
                    {
                        'title': 'РЕЙТИНГ ЗА МАТЧ',
                        'points': [
                            'Победа (в основное время, 90 минут) +40 рейтинга',
                            'Ничья +20 рейтинга',
                            'Поражение 0 рейтинга',
                            'Победа в дополнительное время или по пенальти +20 рейтинга'
                        ]
                    },
                    {
                        'title': 'ТЕХНИЧЕСКОЕ ПОРАЖЕНИЕ',
                        'points': [
                            'Поражение через TP –20 рейтинга',
                            'Победа через TP +40 рейтинга'
                        ]
                    },
                    {
                        'title': 'ЧЕМПИОНСКИЕ БОНУСЫ',
                        'points': [
                            'Чемпион турнира +100 рейтинга',
                            '2-е место +50 рейтинга',
                            '3-е место +50 рейтинга',
                            'Лучший бомбардир турнира +50 рейтинга'
                        ]
                    },
                    {
                        'title': 'РЕЙТИНГ ЗА ГОЛЫ',
                        'points': [
                            'Рейтинг за голы действует во всех форматах турниров (лига, кубок и др.).',
                            'Видео гола является обязательным.',
                            '',
                            'Самый красивый гол турнира (топ-3 по количеству реакций)',
                            '1-е место +100 рейтинга',
                            '2-е место +50 рейтинга',
                            '3-е место +50 рейтинга',
                            '',
                            'Каждый тип гола может быть засчитан только 1 раз за один турнир',
                            '',
                            'Гол ударом через себя (ножницами) +150 рейтинга',
                            'Scorpion гол +150 рейтинга',
                            'Rabona (гол или ассист) +100 рейтинга',
                            'Гол прямым ударом с углового +100 рейтинга',
                            'Гол с дальней дистанции (20+ метров) +100 рейтинга',
                            'Гол или ассист от вратаря (пенальти и штрафные не учитываются) +100 рейтинга',
                            'Гол со штрафного удара +50 рейтинга',
                            'Гол Blitz Curler +30 рейтинга',
                            'Poker (1 игрок забивает 4 или более голов) +50 рейтинга',
                            'Решающий гол после 85-й минуты +50 рейтинга',
                            'Comeback победа (отставание минимум в 2 гола) +50 рейтинга'
                        ]
                    }
                ],
                'note': 'Видео голов также публикуются на Instagram странице ufel_uz. Один участник в течение одного турнира может набрать общий рейтинг за разные типы голов. Если будет обнаружена попытка искусственного увеличения рейтинга, результат будет аннулирован.'
            }
        }
    else:
        # Uzbek – use Django's gettext (will return original Uzbek strings for now)
        translation.activate(lang)
        content = {
            'reglament': {
                'title': _('Uzbekistan Football e-League — REGLAMENT'),
                'sections': [
                    {
                        'title': _('1. UMUMIY MA’LUMOT'),
                        'points': [
                            _('1.1. UFEL (Uzbekistan Football e-League) — eFootball o\'yinida turnirlar tashkil qiluvchi liga hisoblanadi.'),
                            _('1.2. Turnirlar eFootball oʻyini asosida va ushbu reglamentga muvofiq tashkil etiladi.'),
                            _('1.3. Ushbu reglament barcha ishtirokchilar uchun majburiy hisoblanadi.'),
                            _('1.4. Liga maqsadi — eFootballni O\'zbekistonda yangi darajada rivojlantirish va kuchli raqobat muhitini taʼminlash.')
                        ]
                    },
                    {
                        'title': _('2. ISHTIROKCHILAR'),
                        'points': [
                            _('2.1. Ligada roʻyxatdan oʻtgan barcha ishtirokchilar qatnashishi mumkin.'),
                            _('2.2. Adminlar ishtirokchilardan turnir uchun kerakli bo\'lgan malumotlarni sorashi mumkun.'),
                            _('2.3. Bir ishtirokchi turnirlarda faqat bitta akkaunt orqali qatnashishi mumkin.')
                        ]
                    },
                    {
                        'title': _('3. TEXNIK TALABLAR'),
                        'points': [
                            _('3.1. Platformalar: PlayStation 4/5, Kompyuter (PC), Xbox.'),
                            _('3.2. Barqaror o‘yin uchun internet ulanishi LAN (simli) tarmoq tavsiya etiladi.'),
                            _('3.3. Ishtirokchining internet tezligi pas yoki ulanishi belgilangan texnik talablarga mos kelmagan hollarda, turnirdan chetlatiladi.'),
                            _('3.4. Match Sozlamalari turnir turiga qarab alohida reglament yoki eʼlonda belgilanadi.'),
                            _('3.5. O\'yin davomida internet uzilishi yoki texnik nosozliklar yuzaga kelsa, hakamlar qarori bilan qayta o\'ynash yoki hisobni saqlab qolish masalasi ko\'rib chiqiladi.')
                        ]
                    },
                    {
                        'title': _('4. O‘YINNI BOSHLASH TARTIBI'),
                        'points': [
                            _('4.1. O‘yinni boshlash uchun ishtirokchilar o‘zaro kelishgan holda qulay vaqtni belgilaydi va bir-biri bilan bog‘lanadi.'),
                            _('4.2. Agar raqib xabarlarga javob bermasa yoki kelishilgan vaqtda aloqaga chiqmasa, UFEL adminlariga murojaat qilinadi.'),
                            _('4.3. Adminlar holatni ko‘rib chiqib, texnik g‘alaba, yoki boshqa yakuniy qaror qabul qiladi.'),
                            _('4.4. Kelishilgan o‘yinlar qat’iyan taqiqlanadi.')
                        ]
                    },
                    {
                        'title': _('5. LIGA JADVALINI HISOBLASH TARTIBI'),
                        'points': [
                            _('5.1. Liga bosqichida ishtirokchilarning turnir jadvalidagi o‘rinlari, to‘plangan ochkolar soni asosida aniqlanadi.'),
                            _('5.2. Agar ishtirokchilarning ochkolari teng bo‘lsa, ustunlik ko‘proq gol urgan ishtirokchiga beriladi.'),
                            _('5.3. Agar ochkolar va urilgan gollar soni ham teng bo‘lsa, ustunlik kamroq gol o‘tkazib yuborgan ishtirokchiga beriladi.'),
                            _('5.4. Agar yuqoridagi barcha ko‘rsatkichlar teng bo‘lib qolsa, ishtirokchilarning o‘zaro o‘yin natijasi hisobga olinadi.'),
                            _('5.5. Maxsus formatdagi turnirlarda (JCH, CHL va boshqa) turnirlarda jadvalni hisoblash tartibi ushbu turnir reglamentida alohida belgilanadi.')
                        ]
                    },
                    {
                        'title': _('6. INTIZOM'),
                        'points': [
                            _('6.1. Turnir davomida barcha ishtirokchilar o‘zaro hurmat va sport ruhiga amal qilishlari tavsiya etiladi.'),
                            _('6.2. Guruhda Haqorat, tahdid yoki boshqa nojo‘ya xatti harakatlar ogohlantirish yoki Ban ga sabab bo‘ladi.')
                        ]
                    },
                    {
                        'title': _('7. YAKUNIY QOIDALAR'),
                        'points': [
                            _('7.1. Ishtirokchi turnirda qatnashish orqali ushbu reglamentni to‘liq qabul qilgan hisoblanadi.'),
                            _('7.2. UFEL adminlari bahsli vaziyatlarda yakuniy qaror qabul qiladi.'),
                            _('7.3. Adminlar reglamentga o‘zgartirish va qo‘shimchalar kiritish huquqini o‘zida saqlab qoladi.')
                        ]
                    }
                ]
            },
            'rating': {
                'title': _('REYTING TIZIMI'),
                'description': _('Reyting Natijalari Bir Mavsum So\'ngigacha Yeg\'ilib Boradi. Reyting Quyidagi Qoidalar Asosida Hisoblanadi.'),
                'sections': [
                    {
                        'title': _('O\'YIN UCHUN REYTING'),
                        'points': [
                            _('G\'alaba (90 daqiqa ichida) +40 Reyting'),
                            _('Durrang +20 Reyting'),
                            _('Mag\'lubiyat 0 Reyting'),
                            _('Qo\'shimcha vaqt yoki Penaltilarda G\'alaba +20 Reyting')
                        ]
                    },
                    {
                        'title': _('TEXNIK MAG\'LUBIYAT'),
                        'points': [
                            _('TP – Orqali Mag\'lubiyat –20 Reyting'),
                            _('TP – Orqali G\'alaba +40 Reyting')
                        ]
                    },
                    {
                        'title': _('CHEMPIONLIK UCHUN'),
                        'points': [
                            _('Chempionlik Uchun Qo\'shimcha +100 Reyting'),
                            _('2-O\'rin uchun +50 Reyting'),
                            _('3-O\'rin uchun +50 Reyting'),
                            _('Turnir Top Urari +50 Reyting')
                        ]
                    },
                    {
                        'title': _('GOLLAR VIDEOSI UCHUN REYTING'),
                        'points': [
                            _('Gol Reytingi Barcha Turnir Formatlarida Amal Qiladi (liga, kubok va boshqa).'),
                            _('Gol Videosi Majburiy Hisoblanadi.'),
                            _(''),
                            _('Turnir Eng Chiroyli Goli (eng kop reaksiya top3)'),
                            _('1-O\'rin +100 Reyting'),
                            _('2-O\'rin +50 Reyting'),
                            _('3-O\'rin +50 Reyting'),
                            _(''),
                            _('Har Bir Gol Turidan 1ta Turnirga 1ta Limit'),
                            _(''),
                            _('Qaychi Zarbasida Gol +150 REYTING'),
                            _('Scorpion Gol +150 REYTING'),
                            _('Rabona Gol yoki Asist +100 REYTING'),
                            _('Burchak Zarbasidan Gol (угловой tog\'ridan tog\'ri gol) +100 REYTING'),
                            _('Uzoq Masofadan Gol (20+ metr va undan uzoq) +100 REYTING'),
                            _('Darvozabondan Gol yoki Asist (penalti yoki jarima zarbasi hisobga olinmaydi) +100 REYTING'),
                            _('Jarima Zarbasidan Gol +50 REYTING'),
                            _('Blitz Curler Gol +30 REYTING'),
                            _('Poker (bir o\'yinchi 4ta yoki undan kop gol) +50 REYTING'),
                            _('85+ Hal Qiluvchi Gol (85-daqiqadan so\'ng g\'alaba goli) +50 REYTING'),
                            _('Comeback G\'alaba (kamida 2gol ortda qolib kambek) +50 REYTING')
                        ]
                    }
                ],
                'note': _('Gollar ufel_uz Instagram Sahifasida Ham Joylanadi. Bir Ishtirokchi Bitta Turnir Davomida Turli xil Gollar Orqali Umumiy Reyting To‘plashi Mumkin. Reytingni Soxta Oshirish Urinishlari Aniqlansa, Natija Bekor Qilinadi!')
            }
        }
    
    return JsonResponse(content)


def set_language(request):
    lang = request.GET.get('lang', 'uz')
    next_url = request.GET.get('next')
    
    # Agar next bo'lmasa, referer yoki index ga o'tish
    if not next_url:
        next_url = request.META.get('HTTP_REFERER', reverse('index'))
    
    print(f"Setting language to: {lang}")
    print(f"Next URL: {next_url}")
    print(f"Available languages: {dict(settings.LANGUAGES)}")
    
    # Til mavjudligini tekshirish
    if lang in dict(settings.LANGUAGES).keys():
        # Translation ni faollashtirish
        activate(lang)
        
        # Session ga saqlash
        request.session['django_language'] = lang
        request.session.modified = True  # MUHIM!
        
        # Cookie ga saqlash
        response = HttpResponseRedirect(next_url)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, 
            lang,
            max_age=365*24*60*60,  # 1 yil
            httponly=False,
            samesite='Lax',
            path='/'
        )
        
        print(f"Language set successfully: {lang}")
        print(f"Session: {request.session.get('django_language')}")
        
        return response
    
    print(f"Language {lang} not available")
    return HttpResponseRedirect(next_url)
