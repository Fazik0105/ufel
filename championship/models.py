from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import pre_save, post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    
    ROLE_CHOICES = (('ADMIN', 'Admin'), ('USER', 'User'))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # NATION CHOICES
    NATION_CHOICES = [
        ('UZ', '🇺🇿 O`zbekiston'),
        ('KG', '🇰🇬 Qirg`iziston'),
        ('KZ', '🇰🇿 Qozog`iston'),
        ('TJ', '🇹🇯 Tojikiston'),
        ('AM', '🇦🇲 Armenia'),
        ('AZ', '🇦🇿 Ozarbayjon'),
        ('BY', '🇧🇾 Belarusiya'),
        ('RU', '🇷🇺 Rossiya'),
        ('OTHER', '🌍 Boshqa'),
    ]
    
    nation = models.CharField(
        max_length=10, 
        choices=NATION_CHOICES, 
        default='UZ',
        null=True,
        blank=True,
        verbose_name="Davlat"
    )

    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser

    def get_nation_flag(self):
        """Nation flagini qaytarish"""
        flags = {
            'UZ': '🇺🇿',
            'KG': '🇰🇬',
            'KZ': '🇰🇿',
            'TJ': '🇹🇯',
            'AM': '🇦🇲',
            'AZ': '🇦🇿',
            'BY': '🇧🇾',
            'RU': '🇷🇺',
            'OTHER': '🌍',
        }
        return flags.get(self.nation, '🇺🇿')

    def __str__(self):
        display_name = f"{self.first_name} {self.last_name}".strip()
        if not display_name:
            display_name = self.username or f"User-{self.id}"
        return display_name
    
class Championship(models.Model):
    CHAMPIONSHIP_TYPE = (
        ('LEAGUE', 'League'),
        ('PLAYOFF', 'Play Off'),
        ('GROUP', 'Group'),
    )

    STATUS = (
        ('DRAFT', 'Draft'),
        ('STARTED', 'Started'),
        ('FINISHED', 'Finished'),
    )
    
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=CHAMPIONSHIP_TYPE)
    status = models.CharField(max_length=20, choices=STATUS, default='DRAFT')
    advance_count = models.IntegerField(default=4)
    created_at = models.DateTimeField(auto_now_add=True)

    teams_count = models.IntegerField(default=8) # Jamoalar soni
    matches_per_team = models.IntegerField(default=2) # Har bir jamoaga o'yinlar soni
    win_points = models.IntegerField(default=3) # G'alaba uchun ochko
    draw_points = models.IntegerField(default=1) # Durang uchun ochko
    loss_points = models.IntegerField(default=0) # Mag'lubiyat uchun ochko
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    group_count = models.IntegerField(default=4, verbose_name="Guruhlar soni")
    group_advance_count = models.IntegerField(default=1, verbose_name="Har bir guruhdan chiqadigan jamoalar soni")
    
    def __str__(self):
        return self.name
    
class ChampionshipParticipant(models.Model):
    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('championship', 'user')

class Match(models.Model):
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE, related_name='matches')
    home_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='home_matches', null=True, blank=True)
    away_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='away_matches', null=True, blank=True)
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    round_name = models.CharField(max_length=50, null=True, blank=True)
    round_order = models.IntegerField(default=0)  # Raund tartibi (1-birinchi raund, 2-ikkinchi raund, ...)
    group_label = models.CharField(max_length=10, null=True, blank=True)
    is_finished = models.BooleanField(default=False)
    bracket_position = models.IntegerField(null=True, blank=True)  # Joriy raunddagi o'rni

    class Meta:
        indexes = [
            models.Index(fields=['championship', 'is_finished']),
            models.Index(fields=['championship', 'round_order']),
            models.Index(fields=['home_user']),
            models.Index(fields=['away_user']),
        ]
    
    # MUHIM: Keyingi matchga ForeignKey bilan bog'lash
    next_match = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='previous_matches'
    )
    next_match_position = models.IntegerField(null=True, blank=True, default=0)  # Keyingi matchdagi pozitsiya (0-home, 1-away)

    def winner(self):
            if self.is_finished:
                # BYE (Raqibsiz) holati uchun tekshiruv
                if self.home_user and not self.away_user:
                    return self.home_user
                if self.away_user and not self.home_user:
                    return self.away_user
                    
                # Oddiy o'yin holati
                if self.home_score > self.away_score:
                    return self.home_user
                elif self.away_score > self.home_score:
                    return self.away_user
            return None
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        if self.is_finished and self.championship.type == 'PLAYOFF':
            from .services import update_playoff_bracket
            update_playoff_bracket(self)

@receiver(pre_save, sender=User)
def delete_old_user_avatar(sender, instance, **kwargs):
    if not instance.pk:
        return
    
    try:
        old_avatar = User.objects.get(pk=instance.pk).avatar
    except User.DoesNotExist:
        return

    new_avatar = instance.avatar
    if old_avatar and old_avatar != new_avatar:
        old_avatar.delete(save=False)


@receiver(pre_save, sender=Championship)
def delete_old_championship_avatar(sender, instance, **kwargs):
    if not instance.pk:
        return
    
    try:
        old_avatar = Championship.objects.get(pk=instance.pk).avatar
    except Championship.DoesNotExist:
        return

    new_avatar = instance.avatar
    if old_avatar and old_avatar != new_avatar:
        old_avatar.delete(save=False)

@receiver(post_delete, sender=User)
def delete_user_avatar_on_delete(sender, instance, **kwargs):
    if instance.avatar:
        instance.avatar.delete(save=False)


@receiver(post_delete, sender=Championship)
def delete_championship_avatar_on_delete(sender, instance, **kwargs):
    if instance.avatar:
        instance.avatar.delete(save=False)

class BookmarkedMatch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarked_matches')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'match')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.username} - Match {self.match.id}"
    

class UserRating(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rating')
    games_played = models.IntegerField(default=0, verbose_name="O'yinlar soni")
    points = models.IntegerField(default=0, verbose_name="Ochkolar")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-points', '-games_played']
        
    def __str__(self):
        return f"{self.user.username}: {self.points} pts"

    @receiver(post_save, sender=User)
    def create_user_rating(sender, instance, created, **kwargs):
        if created and instance.role == 'USER':
            UserRating.objects.get_or_create(user=instance, defaults={'games_played': 0, 'points': 0})

class Champion(models.Model):
    """
    UFEL Champions - Turnir g'oliblari va qo'lda kiritilgan chempionlar
    """
    class Meta:
        verbose_name = "Chempion"
        verbose_name_plural = "Chempionlar"
        ordering = ['-year', '-created_at']
    
    # Qaysi turnirdan kelgan (agar turnir orqali qo'shilgan bo'lsa)
    championship = models.ForeignKey(
        Championship, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='champions'
    )
    
    # Chempion bo'lgan user
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='championships_won'
    )
    
    # O'rni (1,2,3)
    POSITION_CHOICES = (
        (1, '🥇 1-o\'rin'),
        (2, '🥈 2-o\'rin'),
        (3, '🥉 3-o\'rin'),
    )
    position = models.IntegerField(choices=POSITION_CHOICES)
    
    # Yil
    year = models.IntegerField()
    
    # Turnir nomi (agar qo'lda kiritilsa yoki championship null bo'lsa)
    tournament_name = models.CharField(max_length=200, blank=True, null=True)
    
    # Turnir rasmi (agar qo'lda kiritilsa)
    tournament_image = models.ImageField(
        upload_to='champions/tournaments/', 
        null=True, 
        blank=True
    )
    
    # Qo'lda kiritilganmi?
    is_manual = models.BooleanField(default=False)
    
    # Qo'shimcha ma'lumotlar
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        position_display = dict(self.POSITION_CHOICES).get(self.position, f"{self.position}-o'rin")
        tournament = self.tournament_name or (self.championship.name if self.championship else "Noma'lum turnir")
        return f"{self.user} - {position_display} ({tournament}, {self.year})"
    
    def get_tournament_display_name(self):
        """Turnir nomini qaytarish (championship dan yoki manual dan)"""
        if self.championship:
            return self.championship.name
        return self.tournament_name or "Noma'lum turnir"
    
    def get_tournament_image(self):
        """Turnir rasmini qaytarish"""
        if self.championship and self.championship.avatar:
            return self.championship.avatar
        return self.tournament_image
    
    def get_position_display_with_emoji(self):
        """O'rin nomini emoji bilan qaytarish"""
        emojis = {1: '🥇', 2: '🥈', 3: '🥉'}
        return f"{emojis.get(self.position, '🏆')} {self.get_position_display()}"
    
# ============= CHAMPION SIGNALS =============
@receiver(post_save, sender=Match)
def check_championship_finished_and_add_champions(sender, instance, **kwargs):
    """
    Match tugaganda, agar bu Final match bo'lsa va turnir tugagan bo'lsa,
    1,2,3-o'rinlarni Champion modeliga qo'shish
    """
    # Faqat tugagan matchlar uchun
    if not instance.is_finished:
        return
    
    championship = instance.championship
    
    # Faqat FINISHED holatidagi turnirlar uchun
    if championship.status != 'FINISHED':
        return
    
    # Turnir uchun allaqachon chempionlar qo'shilganmi tekshirish
    if Champion.objects.filter(championship=championship).exists():
        return
    
    # Turnir turiga qarab 1,2,3-o'rinlarni aniqlash
    year = timezone.now().year
    
    if championship.type == 'PLAYOFF':
        add_playoff_champions(championship, year)
    elif championship.type == 'LEAGUE':
        add_league_champions(championship, year)
    elif championship.type == 'GROUP':
        add_group_champions(championship, year)

def add_playoff_champions(championship, year):
    """Playoff turniri uchun 1,2,3-o'rinlarni aniqlash"""
    try:
        # Final matchni topish
        final_match = Match.objects.filter(
            championship=championship,
            round_name="Final",
            is_finished=True
        ).first()
        
        if not final_match:
            return
        
        # 1-o'rin (Final g'olibi)
        champion = final_match.winner()
        if champion:
            Champion.objects.create(
                championship=championship,
                user=champion,
                position=1,
                year=year
            )
        
        # 2-o'rin (Final mag'lubi)
        runner_up = final_match.home_user if final_match.away_user == champion else final_match.away_user
        if runner_up:
            Champion.objects.create(
                championship=championship,
                user=runner_up,
                position=2,
                year=year
            )
        
        # 3-o'rin uchun semifinal mag'lublari o'rtasidagi g'olib
        # (odatda 3-o'rin uchun alohida match bo'lmasa, ikkala semifinalchi ham 3-o'rin)
        semifinals = Match.objects.filter(
            championship=championship,
            round_name__in=["1/2 Final", "Semifinal"],
            is_finished=True
        )
        
        # Semifinal mag'lublarini topish
        semifinal_losers = []
        for sf in semifinals:
            if sf.winner():
                loser = sf.home_user if sf.away_user == sf.winner() else sf.away_user
                if loser:
                    semifinal_losers.append(loser)
        
        # Ikkala semifinal mag'lubini 3-o'rin sifatida qo'shish (yoki faqat bittasini)
        for loser in semifinal_losers[:2]:  # Ko'pi bilan 2 ta
            if loser and loser != champion and loser != runner_up:
                Champion.objects.create(
                    championship=championship,
                    user=loser,
                    position=3,
                    year=year
                )
                
    except Exception as e:
        print(f"Error adding playoff champions: {e}")

def add_league_champions(championship, year):
    """Liga turniri uchun 1,2,3-o'rinlarni aniqlash (jadval bo'yicha)"""
    try:
        from .services import get_standings
        standings = get_standings(championship.id)
        
        # Top 3 ni olish
        for i, standing in enumerate(standings[:3], start=1):
            if i <= 3:  # 1,2,3
                Champion.objects.create(
                    championship=championship,
                    user=standing['user'],
                    position=i,
                    year=year
                )
    except Exception as e:
        print(f"Error adding league champions: {e}")

def add_group_champions(championship, year):
    """Group turniri uchun 1,2,3-o'rinlarni aniqlash"""
    try:
        from .services import get_group_standings
        group_data = get_group_standings(championship.id)
        
        # Barcha guruhlardagi eng yaxshi jamoalarni olish
        all_teams = []
        for group in group_data:
            for standing in group['standings']:
                all_teams.append(standing)
        
        # Ochkolar bo'yicha saralash
        all_teams.sort(key=lambda x: (-x['pts'], -x['gd'], -x['gf']))
        
        # Top 3 ni olish
        for i, team in enumerate(all_teams[:3], start=1):
            if i <= 3:
                Champion.objects.create(
                    championship=championship,
                    user=team['user'],
                    position=i,
                    year=year
                )
    except Exception as e:
        print(f"Error adding group champions: {e}")