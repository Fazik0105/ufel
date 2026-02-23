from django.urls import path
from . import views

urlpatterns = [
    # index / home
    path('', views.index, name='index'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    # championships
    path('championships/', views.championship_list, name='championship_list'),
    path('championships/create/', views.create_championship, name='create_championship'),
    path('championships/<int:pk>/generate/', views.generate_matches, name='generate_matches'),
    path('championships/<int:pk>/add-user/', views.add_participant, name='add_participant'),
    path('championships/<int:pk>/participants/', views.create_participant, name='create_participant'),
    path('championships/<int:pk>/matches/', views.championship_matches, name='championship_matches'),
    path('championships/<int:pk>/table/', views.championship_table, name='championship_table'),
    path('championship/<int:pk>/update-all-scores/', views.update_all_scores, name='update_all_scores'),
    # profile
    path('profile/', views.update_profile, name='update_profile'),

    # admin users
    path('users/', views.admin_users, name='admin_users'),
    path('users/<int:pk>/', views.admin_user_detail, name='admin_user_detail'),

    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/championship/<int:pk>/settings/', views.admin_championship_detail, name='admin_championship_detail'),
    # path('match/<int:match_id>/update/', views.update_match_score, name='update_match_score'),
    path('admin/championship/<int:pk>/bulk-add/', views.bulk_add_participants, name='bulk_add_participants'),
    path('admin/championship/<int:pk>/generate/', views.generate_matches, name='generate_matches'),
    path('get-championship-data/<int:pk>/', views.get_championship_data, name='get_championship_data'),
    path('admin/championship/<int:pk>/delete/', views.delete_championship, name='delete_championship'),
    path('admin/championship/<int:pk>/remove-participant/<int:user_id>/', views.remove_participant, name='remove_participant'),
    path('admin/users/delete/<int:pk>/', views.admin_delete_user, name='admin_delete_user'),
]
