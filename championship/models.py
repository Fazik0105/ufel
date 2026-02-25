from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    
    ROLE_CHOICES = (('ADMIN', 'Admin'), ('USER', 'User'))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser

    def __str__(self):
        display_name = f"{self.first_name} {self.last_name}".strip()
        if not display_name:
            display_name = self.username or f"User-{self.id}"
        return display_name
    
class Championship(models.Model):
    CHAMPIONSHIP_TYPE = (
        ('LEAGUE', 'League'),
        ('PLAYOFF', 'Play Off'),
        ('LEAGUE_PLAYOFF', 'League + Play Off'),
        ('GROUP_PLAYOFF', 'Group + Play Off'),
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
