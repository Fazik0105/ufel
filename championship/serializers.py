from rest_framework import serializers
from .models import *


class ChampionshipSerializer(serializers.ModelSerializer):
    participants_count = serializers.IntegerField(
        source='participants.count',
        read_only=True
    )

    class Meta:
        model = Championship
        fields = (
            'id',
            'name',
            'type',
            'status',
            'participants_count',
            'created_at',
        )
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'avatar')

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'avatar',
            'role',
            'password',
        )
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class ParticipantSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='USER')
    )
    team_name = serializers.CharField(max_length=100)

class MatchSerializer(serializers.ModelSerializer):
    home = serializers.CharField(source='home.username')
    away = serializers.CharField(source='away.username')

    class Meta:
        model = Match
        fields = (
            'id',
            'home',
            'away',
            'home_score',
            'away_score',
            'round',
            'group',
            'is_finished',
        )