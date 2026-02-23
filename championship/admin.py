from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Championship, ChampionshipParticipant, Match

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # BaseUserAdmin dan foydalanish parollarni hash qilishda muammo tug'dirmaydi
    list_display = ('username', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Qo\'shimcha ma\'lumotlar', {'fields': ('role', 'avatar')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Qo\'shimcha ma\'lumotlar', {'fields': ('role', 'avatar', 'first_name', 'last_name')}),
    )

@admin.register(Championship)
class ChampionshipAdmin(admin.ModelAdmin):
    # list_display ichida faqat models.py da bor maydonlarni qoldiramiz
    list_display = ('name', 'type', 'status', 'advance_count', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('name',)

@admin.register(ChampionshipParticipant)
class ChampionshipParticipantAdmin(admin.ModelAdmin):
    list_display = ('championship', 'user')
    list_filter = ('championship',)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('championship', 'home_user', 'away_user', 'home_score', 'away_score', 'round_name', 'is_finished')
    list_filter = ('championship', 'round_name', 'is_finished')
    list_editable = ('home_score', 'away_score', 'is_finished') # Admin panelning o'zida hisobni yozish uchun