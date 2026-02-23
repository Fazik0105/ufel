from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (('ADMIN', 'Admin'), ('USER', 'User'))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='USER')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def is_admin(self):
        return self.role == 'ADMIN' or self.is_superuser

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

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
    home_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='home_matches', null=True, blank=True)  # null=True qo'shildi
    away_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='away_matches', null=True, blank=True)  # null=True qo'shildi
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    round_name = models.CharField(max_length=50, null=True, blank=True)
    round_order = models.IntegerField(default=0)  # Raund tartibi (1-final, 2-semifinal, ...)
    group_label = models.CharField(max_length=10, null=True, blank=True)
    is_finished = models.BooleanField(default=False)
    bracket_position = models.IntegerField(null=True, blank=True)  # Joriy raunddagi o'rni
    next_match_id = models.IntegerField(null=True, blank=True)  # Keyingi match ID si
    next_match_position = models.IntegerField(null=True, blank=True)  # Keyingi matchdagi pozitsiya (0-home, 1-away)

    def winner(self):
        if self.is_finished:
            if self.home_score > self.away_score:
                return self.home_user
            elif self.away_score > self.home_score:
                return self.away_user
        return None
    
    def save(self, *args, **kwargs):
        # Yangi match yaratilganda
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Match tugatilganda bracketni yangilash
        if not is_new and self.is_finished:
            from .services import update_playoff_bracket
            update_playoff_bracket(self)