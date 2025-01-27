from django.urls import path
from spotifyapp import views

urlpatterns =[
    path('', views.connexion, name='connexion'),
    path('index',views.index, name='index'),
    path('deconnexion',views.logout_and_redirect,name='deconnexion'),
    path('login', views.login, name='login'),
    path('callback', views.callback, name='callback'),
    path('refresh_token', views.refresh_token, name='refresh_token'),
    path('topartists', views.get_top_artists,name='topartists'),
    path('topsons',views.get_recent_tracks,name='topsons'),
    path('analyse_sons',views.analyse_sons,name='analyse_sons'),
    path('a_propos',views.about, name='about'),
]