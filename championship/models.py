# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from datetime import timezone

class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    
    ROLE_CHOICES = (('ADMIN', 'Admin'), ('USER', 'User'))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # Yangi: User turi (qaysi sectionda ko'rinishi)
    USER_TYPE_CHOICES = (
        ('TOURNAMENT', 'Turnir ishtirokchisi'),
        ('RATING', 'Reyting ishtirokchisi'),
        ('CHAMPION', 'Chempion'),
        ('ALL', 'Hamma sectionlarda'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='ALL')
    
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
        flags = {
            'UZ': '🇺🇿', 'KG': '🇰🇬', 'KZ': '🇰🇿', 'TJ': '🇹🇯',
            'AM': '🇦🇲', 'AZ': '🇦🇿', 'BY': '🇧🇾', 'RU': '🇷🇺', 'OTHER': '🌍',
        }
        return flags.get(self.nation, '🇺🇿')

    def __str__(self):
        display_name = f"{self.first_name} {self.last_name}".strip()
        if not display_name:
            display_name = self.username or f"User-{self.id}"
        return display_name
    
    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"

class UserType(models.Model):
    """
    Userlarni qaysi sectionlarda ko'rinishini boshqarish
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='type_settings')
    in_tournament = models.BooleanField(default=True, verbose_name="Turnirlarda ko'rinadi")
    in_rating = models.BooleanField(default=True, verbose_name="Reytingda ko'rinadi")
    in_champions = models.BooleanField(default=True, verbose_name="Chempionlar ro'yxatida ko'rinadi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User turi"
        verbose_name_plural = "User turlari"
    
    def __str__(self):
        return f"{self.user} - T:{self.in_tournament} R:{self.in_rating} C:{self.in_champions}"

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

    teams_count = models.IntegerField(default=8)
    matches_per_team = models.IntegerField(default=2)
    win_points = models.IntegerField(default=3)
    draw_points = models.IntegerField(default=1)
    loss_points = models.IntegerField(default=0)
    avatar = models.ImageField(upload_to='tournaments/', null=True, blank=True)

    group_count = models.IntegerField(default=4, verbose_name="Guruhlar soni")
    group_advance_count = models.IntegerField(default=1, verbose_name="Har bir guruhdan chiqadigan jamoalar soni")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Turnir"
        verbose_name_plural = "Turnirlar"

class ChampionshipParticipant(models.Model):
    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('championship', 'user')
        verbose_name = "Turnir ishtirokchisi"
        verbose_name_plural = "Turnir ishtirokchilari"

class Match(models.Model):
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE, related_name='matches')
    home_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='home_matches', null=True, blank=True)
    away_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='away_matches', null=True, blank=True)
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    round_name = models.CharField(max_length=50, null=True, blank=True)
    round_order = models.IntegerField(default=0)
    group_label = models.CharField(max_length=10, null=True, blank=True)
    is_finished = models.BooleanField(default=False)
    bracket_position = models.IntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['championship', 'is_finished']),
            models.Index(fields=['championship', 'round_order']),
            models.Index(fields=['home_user']),
            models.Index(fields=['away_user']),
        ]
        verbose_name = "O'yin"
        verbose_name_plural = "O'yinlar"
    
    next_match = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='previous_matches'
    )
    next_match_position = models.IntegerField(null=True, blank=True, default=0)

    def winner(self):
        if self.is_finished:
            if self.home_user and not self.away_user:
                return self.home_user
            if self.away_user and not self.home_user:
                return self.away_user
                
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

class BookmarkedMatch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarked_matches')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'match')
        ordering = ['-created_at']
        verbose_name = "Bookmark"
        verbose_name_plural = "Bookmarklar"
        
    def __str__(self):
        return f"{self.user.username} - Match {self.match.id}"
    
class UserRating(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rating')
    games_played = models.IntegerField(default=0, verbose_name="O'yinlar soni")
    points = models.IntegerField(default=0, verbose_name="Ochkolar")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-points', '-games_played']
        verbose_name = "User reytingi"
        verbose_name_plural = "User reytinglari"
        
    def __str__(self):
        return f"{self.user.username}: {self.points} pts"

class ChampionHall(models.Model):
    POSITION_CHOICES = (
        (1, '1-o`rin'),
        (2, '2-o`rin'),
        (3, '3-o`rin'),
    )
   
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='champion_halls',
        verbose_name="Chempion"
    )
    position = models.IntegerField(choices=POSITION_CHOICES, verbose_name="O'rin")
    tournament_name = models.CharField(max_length=200, verbose_name="Turnir nomi")
    tournament_image = models.ImageField(
        upload_to='champion_halls/',
        null=True,
        blank=True,
        verbose_name="Turnir rasmi"
    )
    # To'liq sana (yil, oy, kun)
    tournament_date = models.DateField(
        verbose_name="Turnir sanasi"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
   
    @property
    def added_at(self):
        """added_at property - created_at bilan bir xil"""
        return self.created_at
    
    @property
    def year(self):
        """Yilni tournament_date dan olish"""
        return self.tournament_date.year if self.tournament_date else None
    
    def get_position_display_with_emoji(self):
        """Emoji bilan birga o'rinni qaytarish"""
        emojis = {1: '🥇', 2: '🥈', 3: '🥉'}
        return f"{emojis.get(self.position, '')} {self.get_position_display()}"
    
    def get_formatted_date(self):
        """Sanani formatlab qaytarish: December 15, 2023"""
        if self.tournament_date:
            return self.tournament_date.strftime("%B %d, %Y")
        return None
   
    class Meta:
        verbose_name = "Champion Hall"
        verbose_name_plural = "Champion Hall"
        ordering = ['-tournament_date', '-created_at']

# ============= SIGNALS =============
@receiver(post_save, sender=User)
def create_user_related(sender, instance, created, **kwargs):
    """Yangi user yaratilganda UserType va UserRating yaratish"""
    if created:
        # UserType yaratish - user_type ga qarab sozlanadi
        user_type_settings = UserType.objects.create(user=instance)
        
        # UserType ni user_type ga qarab sozlash
        if instance.user_type == 'TOURNAMENT':
            user_type_settings.in_tournament = True
            user_type_settings.in_rating = False
            user_type_settings.in_champions = False
        elif instance.user_type == 'RATING':
            user_type_settings.in_tournament = False
            user_type_settings.in_rating = True
            user_type_settings.in_champions = False
        elif instance.user_type == 'CHAMPION':
            user_type_settings.in_tournament = False
            user_type_settings.in_rating = False
            user_type_settings.in_champions = True
        elif instance.user_type == 'ALL':
            user_type_settings.in_tournament = True
            user_type_settings.in_rating = True
            user_type_settings.in_champions = True
        
        user_type_settings.save()
        
        # UserRating faqat rating userlari uchun
        if instance.role == 'USER' and (instance.user_type in ['RATING', 'ALL']):
            UserRating.objects.get_or_create(user=instance, defaults={'games_played': 0, 'points': 0})

@receiver(post_save, sender=User)
def update_user_type(sender, instance, **kwargs):
    """User type o'zgarganda UserType ni yangilash"""
    UserType.objects.get_or_create(user=instance)

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

@receiver(post_save, sender=Match)
def assign_champion_on_finish(sender, instance, **kwargs):
    if instance.is_finished and instance.round_name == "Final" and instance.championship.status == "FINISHED":
        winner = instance.winner()
        if winner:
            # 1-o'rin uchun assign
            ChampionHall.objects.create(
                user=winner,
                position=1,
                year=timezone.now().year,
                tournament_name=instance.championship.name,
                tournament_image=instance.championship.avatar  # Agar rasm bo'lsa
            )