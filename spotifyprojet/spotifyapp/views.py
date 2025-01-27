import os
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from django.http import HttpResponse
import numpy as np
import pandas as pd
from spotipy.oauth2 import SpotifyOAuth
import spotipy
from dotenv import load_dotenv
load_dotenv()
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import urllib, base64,io
import matplotlib.pyplot as plt



client_id=os.getenv('SPOTIPY_CLIENT_ID')
client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')
redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI')
scope="user-library-read streaming user-read-recently-played user-top-read"


# Configure Spotify OAuth
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope
)

def index(request):
    sp = check_token(request)
    if isinstance(sp, HttpResponse):
        return sp  # Return the error response if check_token failed
    if sp:
        try:
            nom_user=sp.current_user()['display_name']
            request.session["name_user"]=nom_user
            return render(request, 'base.html',{"name_user":nom_user})
        except spotipy.exceptions.SpotifyException as e:
            return HttpResponse("Erreur : " + str(e))
    return redirect('/login')

def check_token(request):
    # Check if user is logged in
    if "spotify_token" in request.session:
        token = get_token(request)
        
        try:
            # Utiliser le token d'accès pour accéder à l'API Spotify
            sp = spotipy.Spotify(auth=token)
            sp.me()  # Test the token by making a simple request
            return sp
            
        except spotipy.exceptions.SpotifyException as e:
            # Si le token d'accès est expiré, appeler la fonction refresh_token
            if e.http_status == 401:
                refresh_token(request)
                token = get_token(request)
                sp = spotipy.Spotify(auth=token)
                return sp
            else:
                return HttpResponse("Erreur : " + str(e))

    # If not logged in, redirect to Spotify login
    return redirect('/login')

def refresh_token(request):
    refresh_token = get_refresh_token(request)
    token_info = sp_oauth.refresh_access_token(refresh_token)
    request.session["spotify_token"] = token_info["access_token"]
    request.session["spotify_refresh_token"] = token_info["refresh_token"]

def get_token(request):
    if "spotify_token" in request.session:
        return request.session["spotify_token"]
    else:
        return None
    
def get_refresh_token(request):
    if "spotify_refresh_token" in request.session:
        return request.session["spotify_refresh_token"]
    else:
        return None

def get_top_artists(request):
    sp = check_token(request)
    if isinstance(sp, HttpResponse):
        return sp  # Return the error response if check_token failed
    if sp:
        try:
            top_artists = sp.current_user_top_artists(limit=15, offset=0, time_range="short_term")
            data = structure_donnee(top_artists['items'])
            data = process_data(data)
            return render(request, 'topartists.html', {'data': data,"name_user":request.session["name_user"]})
        except spotipy.exceptions.SpotifyException as e:
            return HttpResponse("Erreur : " + str(e))
    return redirect('/login')

def get_recent_tracks(request):
    sp = check_token(request)
    if isinstance(sp, HttpResponse):
        return sp  # Return the error response if check_token failed
    if sp:
        try:
            tracks = sp.current_user_top_tracks(limit=25, time_range="short_term")["items"]
            data_son = []
            for s in tracks:
                data_son.append(extraire_info_son(s))
            return render(request, 'topsons.html', {"data": data_son,"name_user":request.session["name_user"]})
        except spotipy.exceptions.SpotifyException as e:
            return HttpResponse("Erreur : " + str(e))
    return redirect('/login')

def extraire_info_son(track):
    duree_ms = track["duration_ms"]
    return {
        "nom": track["name"],
        "album": track["album"]["name"],
        "artiste": track["artists"][0]["name"],
        "duree": track["duration_ms"],
        "image": track["album"]["images"][0]["url"],
        "min": int(duree_ms / 60000),
        "sec": int((duree_ms % 60000) / 1000),
        "url": track["external_urls"]["spotify"]
    }

def extraire_info(artist):
    return {
        "nom": artist["name"],
        "image": artist["images"][0]["url"],
        "followers": artist["followers"]["total"],
        "genre": artist["genres"],
        "popularité": artist["popularity"],
        "nb_ecoutes": artist["playcount"] if "playcount" in artist else "N/A",
        "url":artist["external_urls"]["spotify"],
    }

def structure_donnee(artists):
    data = []
    for a in artists:
        info = extraire_info(a)
        data.append(info)
    return data

def process_data(data):
    data.sort(key=lambda x: x["nb_ecoutes"], reverse=True)
    return data

def login(request):
    # Clear existing tokens to force reauthentication
    request.session.pop("spotify_token", None)
    request.session.pop("spotify_refresh_token", None)
    request.session.save()

    # Delete the .cache file
    cache_file_path = os.path.join(os.path.dirname(__file__), '..', '.cache')
    if os.path.exists(cache_file_path):
        os.remove(cache_file_path)

    # Redirect user to Spotify authorization URL
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

def callback(request):
    # Handle callback from Spotify authorization
    code = request.GET.get("code")
    token_info = sp_oauth.get_access_token(code)

    # Store access token in session
    request.session["spotify_token"] = token_info["access_token"]
    request.session["spotify_refresh_token"] = token_info["refresh_token"]

    return redirect('/index')

def get_plot_top_artist(sp):
    artists = sp.current_user_top_artists(limit=1, time_range="short_term")["items"]
    artist_ids = [artist["id"] for artist in artists]
    artist_names = [artist["name"] for artist in artists]

    fig, ax = plt.subplots(figsize=(12, 8))

    for artist_id, artist_name in zip(artist_ids, artist_names):
        play_counts = get_monthly_play_counts(sp, artist_id)
        df = pd.DataFrame(play_counts, columns=['month', 'play_count'])
        df['month'] = pd.to_datetime(df['month'])
        df = df.set_index('month')
        df = df.resample('ME').sum()  # Use 'ME' instead of 'M'
        ax.plot(df.index, df['play_count'], label=artist_name)

    ax.set_xlabel('Date')
    ax.set_ylabel('Nombre d\'écoutes')
    ax.set_title('Popularité albums de ton artiste')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save the plot to a PNG image in memory
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    uri2 = 'data:image/png;base64,' + urllib.parse.quote(string)
    return uri2


def get_plot_genre_topsons(sp):
    results=sp.current_user_top_tracks(limit=25, time_range="short_term")["items"]

    # Extract genres from the user's top tracks
    genres = []
    for track in results:
        for artist in track['artists']:
            artist_info = sp.artist(artist['id'])
            genres.extend(artist_info['genres'])

    # Count the occurrences of each genre
    genre_counts = Counter(genres)#instance de counter qui crée un dict et qui compte 
    # Combine singular and plural genre names
    genre_counts_combined = Counter()
    for genre, count in genre_counts.items():
        singular_genre = genre.rstrip('s')
        genre_counts_combined[singular_genre] += count
   
    genre_counts = genre_counts_combined
    genre_keys = list(genre_counts.keys())


    # Create a bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(genre_counts.keys(), genre_counts.values())
    ax.set_xlabel('Genres')
    ax.set_ylabel('Nombre d\'écoute ')
    ax.set_title('Top Genres de ton top 25 sons')
    plt.xticks(rotation=90)
    plt.tight_layout()

    # Save the plot to a PNG image in memory
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    uri = 'data:image/png;base64,' + urllib.parse.quote(string)
    return uri,genre_keys


def analyse_sons(request):
    sp = check_token(request)


    uri_plot_genres,genre_keys = get_plot_genre_topsons(sp)
    uri_plot_artist =get_plot_top_artist(sp)


    # Pass the image URI to the template
    return render(request, 'analyse_sons.html', {'image_uri_genres': uri_plot_genres , 
    'image_uri_artist':uri_plot_artist,"genre_keys":genre_keys,"name_user":request.session["name_user"]})


def about(request):
    return render(request,'about.html',{"name_user":request.session["name_user"]})

def connexion(request):
    return render(request,'connexion.html')



def logout_and_redirect(request):
    # Clear the session to log out the user
    
    # Delete the .cache file
    cache_file_path = os.path.join(os.path.dirname(__file__), '..', '.cache')
    if os.path.exists(cache_file_path):
        os.remove(cache_file_path)

    logout(request)
    
    return redirect("https://accounts.spotify.com/logout")

def get_monthly_play_counts(sp, artist_id):
    results = sp.artist_top_tracks(artist_id)
    play_counts = []
    for track in results['tracks']:
        play_counts.append({
            'month': track['album']['release_date'][:7],  # Extract the year and month
            # Use the actual play count if available, otherwise use popularity as a proxy
            'play_count': track['popularity']
        })
    return play_counts

