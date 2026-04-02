import hashlib
import html
import json
import re
from difflib import SequenceMatcher
from urllib.parse import quote

import requests
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from utils.cache import TTLCache

music_sources_bp = Blueprint('music_sources', __name__, url_prefix='/api/music')

_cache = TTLCache(default_ttl=3600)

DEEZER_BASE_URL = 'https://api.deezer.com'
LASTFM_BASE_URL = 'https://ws.audioscrobbler.com/2.0/'
TADB_BASE_URL = 'https://www.theaudiodb.com/api/v1/json/123'
LYRICS_BASE_URL = 'https://api.lyrics.ovh'
MUSICBRAINZ_BASE_URL = 'https://musicbrainz.org/ws/2'
COVER_ART_BASE_URL = 'https://coverartarchive.org'


def _error(message: str, code: int):
    return jsonify({'error': message, 'code': code}), code


def _ttl() -> int:
    return int(current_app.config.get('API_CACHE_TTL', 3600))


def _timeout() -> int:
    return int(current_app.config.get('EXTERNAL_API_TIMEOUT', 12))


def _cache_key(namespace: str, url: str, params=None, headers=None) -> str:
    payload = json.dumps(
        {
            'url': url,
            'params': params or {},
            'headers': headers or {},
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    return f'{namespace}:{digest}'


def _cached_json_request(namespace: str, url: str, params=None, headers=None, allow_redirects=True):
    cache_key = _cache_key(namespace, url, params=params, headers=headers)
    cached_value = _cache.get(cache_key)
    if cached_value is not None:
        return cached_value, None

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=_timeout(),
            allow_redirects=allow_redirects,
        )
    except requests.RequestException as exc:
        return None, _error(f'External API request failed: {exc}', 502)

    if response.status_code == 404:
        return None, _error('Resource not found', 404)

    if response.status_code >= 400:
        return None, _error(
            f'External API returned status {response.status_code}',
            response.status_code,
        )

    content_type = (response.headers.get('content-type') or '').lower()
    if 'application/json' not in content_type and not response.text.strip().startswith('{') and not response.text.strip().startswith('['):
        return None, _error('External API returned non-JSON response', 502)

    try:
        payload = response.json()
    except ValueError:
        return None, _error('Failed to parse external API response', 502)

    _cache.set(cache_key, payload, ttl=_ttl())
    return payload, None


def _extract_deezer_track(track: dict):
    artist = track.get('artist') or {}
    album = track.get('album') or {}

    return {
        'id': track.get('id'),
        'title': track.get('title') or '',
        'artist': artist.get('name') or '',
        'artist_id': artist.get('id'),
        'album': album.get('title') or '',
        'album_id': album.get('id'),
        'cover_xl': album.get('cover_xl') or album.get('cover_big') or album.get('cover_medium'),
        'duration': track.get('duration') or 0,
        'preview': track.get('preview'),
        'rank': track.get('rank') or 0,
        'link': track.get('link'),
    }


def _extract_deezer_artist(artist: dict):
    return {
        'id': artist.get('id'),
        'name': artist.get('name') or '',
        'picture_xl': artist.get('picture_xl') or artist.get('picture_big') or artist.get('picture_medium'),
        'nb_fan': artist.get('nb_fan') or 0,
        'nb_album': artist.get('nb_album') or 0,
        'link': artist.get('link'),
    }


def _extract_deezer_album(album: dict):
    artist = album.get('artist') or {}

    return {
        'id': album.get('id'),
        'title': album.get('title') or '',
        'artist': artist.get('name') or '',
        'artist_id': artist.get('id'),
        'cover_xl': album.get('cover_xl') or album.get('cover_big') or album.get('cover_medium'),
        'release_date': album.get('release_date'),
        'tracklist': album.get('tracklist'),
        'link': album.get('link'),
    }


def _strip_html(raw_text: str) -> str:
    if not raw_text:
        return ''
    no_tags = re.sub(r'<[^>]+>', '', raw_text)
    return html.unescape(no_tags).strip()


def _normalize_lyrics(text: str) -> str:
    if not text:
        return ''

    normalized = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    normalized = re.sub(r'\n{3,}', '\n\n', normalized)
    return normalized.strip()


def _closest_lyrics_candidate(title: str, artist: str, candidates: list[dict]):
    if not candidates:
        return None

    target_title = (title or '').strip().lower()
    target_artist = (artist or '').strip().lower()

    best = None
    best_score = -1.0

    for item in candidates:
        candidate_title = (item.get('title') or '').strip().lower()
        candidate_artist = ((item.get('artist') or {}).get('name') or '').strip().lower()

        if not candidate_title:
            continue

        title_score = SequenceMatcher(None, target_title, candidate_title).ratio()
        artist_score = SequenceMatcher(None, target_artist, candidate_artist).ratio() if target_artist else 0.0
        total_score = (title_score * 0.75) + (artist_score * 0.25)

        if total_score > best_score:
            best_score = total_score
            best = item

    return best


@music_sources_bp.route('/search', methods=['GET'])
def search_music():
    query = (request.args.get('q') or '').strip()
    result_type = (request.args.get('type') or 'track').strip().lower()

    if not query:
        return _error('Query parameter q is required', 400)

    if result_type not in {'track', 'artist', 'album'}:
        return _error('Query parameter type must be one of: track, artist, album', 400)

    endpoint = {
        'track': '/search/track',
        'artist': '/search/artist',
        'album': '/search/album',
    }[result_type]

    payload, err = _cached_json_request(
        namespace=f'deezer:search:{result_type}',
        url=f'{DEEZER_BASE_URL}{endpoint}',
        params={'q': query},
    )
    if err:
        return err

    data = payload.get('data') if isinstance(payload, dict) else []

    if result_type == 'track':
        transformed = [_extract_deezer_track(item) for item in data]
    elif result_type == 'artist':
        transformed = [_extract_deezer_artist(item) for item in data]
    else:
        transformed = [_extract_deezer_album(item) for item in data]

    return jsonify({'data': transformed, 'type': result_type, 'total': payload.get('total', len(transformed))}), 200


@music_sources_bp.route('/track/<int:track_id>', methods=['GET'])
@jwt_required()
def get_track(track_id: int):
    payload, err = _cached_json_request(
        namespace='deezer:track',
        url=f'{DEEZER_BASE_URL}/track/{track_id}',
    )
    if err:
        return err

    return jsonify(_extract_deezer_track(payload)), 200


@music_sources_bp.route('/album/<int:album_id>', methods=['GET'])
@jwt_required()
def get_album(album_id: int):
    payload, err = _cached_json_request(
        namespace='deezer:album',
        url=f'{DEEZER_BASE_URL}/album/{album_id}',
    )
    if err:
        return err

    album_data = _extract_deezer_album(payload)
    tracks = ((payload.get('tracks') or {}).get('data') or [])
    album_data['tracks'] = [_extract_deezer_track(item) for item in tracks]
    return jsonify(album_data), 200


@music_sources_bp.route('/artist/<int:artist_id>', methods=['GET'])
@jwt_required()
def get_artist(artist_id: int):
    payload, err = _cached_json_request(
        namespace='deezer:artist',
        url=f'{DEEZER_BASE_URL}/artist/{artist_id}',
    )
    if err:
        return err

    return jsonify(_extract_deezer_artist(payload)), 200


@music_sources_bp.route('/artist/<int:artist_id>/top', methods=['GET'])
@jwt_required()
def get_artist_top_tracks(artist_id: int):
    payload, err = _cached_json_request(
        namespace='deezer:artist:top',
        url=f'{DEEZER_BASE_URL}/artist/{artist_id}/top',
        params={'limit': 10},
    )
    if err:
        return err

    tracks = payload.get('data') if isinstance(payload, dict) else []
    return jsonify({'data': [_extract_deezer_track(item) for item in tracks]}), 200


@music_sources_bp.route('/charts', methods=['GET'])
@jwt_required()
def get_charts():
    payload, err = _cached_json_request(
        namespace='deezer:charts',
        url=f'{DEEZER_BASE_URL}/chart/0/tracks',
    )
    if err:
        return err

    tracks = payload.get('data') if isinstance(payload, dict) else []
    transformed = [_extract_deezer_track(item) for item in tracks[:10]]
    return jsonify({'data': transformed}), 200


@music_sources_bp.route('/artist/<string:artist_name>/info', methods=['GET'])
@jwt_required()
def get_artist_info(artist_name: str):
    api_key = current_app.config.get('LASTFM_API_KEY')
    if not api_key:
        return _error('LASTFM_API_KEY is not configured', 500)

    payload, err = _cached_json_request(
        namespace='lastfm:artist:info',
        url=LASTFM_BASE_URL,
        params={
            'method': 'artist.getInfo',
            'artist': artist_name,
            'api_key': api_key,
            'format': 'json',
        },
    )
    if err:
        return err

    artist = payload.get('artist') or {}
    image_list = artist.get('image') or []
    extralarge = next((img.get('#text') for img in image_list if img.get('size') == 'extralarge' and img.get('#text')), None)

    tags = [item.get('name') for item in ((artist.get('tags') or {}).get('tag') or []) if item.get('name')]

    response = {
        'name': artist.get('name') or artist_name,
        'bio_summary': _strip_html(((artist.get('bio') or {}).get('summary') or '')),
        'listeners': ((artist.get('stats') or {}).get('listeners') or '0'),
        'playcount': ((artist.get('stats') or {}).get('playcount') or '0'),
        'tags': tags,
        'image': extralarge,
    }

    return jsonify(response), 200


@music_sources_bp.route('/artist/<string:artist_name>/similar', methods=['GET'])
@jwt_required()
def get_similar_artists(artist_name: str):
    api_key = current_app.config.get('LASTFM_API_KEY')
    if not api_key:
        return _error('LASTFM_API_KEY is not configured', 500)

    payload, err = _cached_json_request(
        namespace='lastfm:artist:similar',
        url=LASTFM_BASE_URL,
        params={
            'method': 'artist.getSimilar',
            'artist': artist_name,
            'limit': 10,
            'api_key': api_key,
            'format': 'json',
        },
    )
    if err:
        return err

    artist_matches = ((payload.get('similarartists') or {}).get('artist') or [])
    transformed = []
    for item in artist_matches:
        image_list = item.get('image') or []
        image = next((img.get('#text') for img in image_list if img.get('size') == 'extralarge' and img.get('#text')), None)
        transformed.append(
            {
                'name': item.get('name') or '',
                'match': item.get('match') or '0',
                'url': item.get('url'),
                'image': image,
            }
        )

    return jsonify({'data': transformed}), 200


@music_sources_bp.route('/track/<string:artist_name>/<string:track_title>/info', methods=['GET'])
@jwt_required()
def get_track_info(artist_name: str, track_title: str):
    api_key = current_app.config.get('LASTFM_API_KEY')
    if not api_key:
        return _error('LASTFM_API_KEY is not configured', 500)

    payload, err = _cached_json_request(
        namespace='lastfm:track:info',
        url=LASTFM_BASE_URL,
        params={
            'method': 'track.getInfo',
            'artist': artist_name,
            'track': track_title,
            'api_key': api_key,
            'format': 'json',
        },
    )
    if err:
        return err

    track = payload.get('track') or {}
    album = track.get('album') or {}

    response = {
        'name': track.get('name') or track_title,
        'artist': (track.get('artist') or {}).get('name') if isinstance(track.get('artist'), dict) else track.get('artist') or artist_name,
        'listeners': track.get('listeners') or '0',
        'playcount': track.get('playcount') or '0',
        'url': track.get('url'),
        'album': album.get('title'),
        'album_image': next(
            (img.get('#text') for img in (album.get('image') or []) if img.get('size') == 'extralarge' and img.get('#text')),
            None,
        ),
    }

    return jsonify(response), 200


@music_sources_bp.route('/tadb/artist', methods=['GET'])
@jwt_required()
def get_tadb_artist():
    name = (request.args.get('name') or '').strip()
    if not name:
        return _error('Query parameter name is required', 400)

    payload, err = _cached_json_request(
        namespace='tadb:artist',
        url=f'{TADB_BASE_URL}/search.php',
        params={'s': name},
    )
    if err:
        return err

    artists = payload.get('artists') or []
    if not artists:
        return jsonify({'data': None}), 200

    artist = artists[0]
    return jsonify(
        {
            'name': artist.get('strArtist') or name,
            'strArtistThumb': artist.get('strArtistThumb'),
            'strArtistBanner': artist.get('strArtistBanner'),
            'strArtistBiography': artist.get('strBiographyEN') or artist.get('strArtistBiography'),
            'strMusicVid': artist.get('strMusicVid'),
            'idArtist': artist.get('idArtist'),
            'strArtistMBID': artist.get('strMusicBrainzID'),
        }
    ), 200


@music_sources_bp.route('/tadb/album', methods=['GET'])
@jwt_required()
def get_tadb_album():
    mbid = (request.args.get('id') or '').strip()
    if not mbid:
        return _error('Query parameter id is required', 400)

    payload, err = _cached_json_request(
        namespace='tadb:album',
        url=f'{TADB_BASE_URL}/album-mb.php',
        params={'i': mbid},
    )
    if err:
        return err

    albums = payload.get('album') or []
    if not albums:
        return jsonify({'data': None}), 200

    album = albums[0]
    return jsonify(
        {
            'idAlbum': album.get('idAlbum'),
            'strAlbum': album.get('strAlbum'),
            'strArtist': album.get('strArtist'),
            'strAlbumThumb': album.get('strAlbumThumb'),
            'strMusicVid': album.get('strMusicVid'),
            'intYearReleased': album.get('intYearReleased'),
            'strDescriptionEN': album.get('strDescriptionEN'),
        }
    ), 200


@music_sources_bp.route('/tadb/discography', methods=['GET'])
@jwt_required()
def get_tadb_discography():
    artist_id = (request.args.get('id') or '').strip()
    if not artist_id:
        return _error('Query parameter id is required', 400)

    payload, err = _cached_json_request(
        namespace='tadb:discography',
        url=f'{TADB_BASE_URL}/discography.php',
        params={'s': artist_id},
    )
    if err:
        return err

    album_items = payload.get('album') or []
    transformed = [
        {
            'strAlbum': item.get('strAlbum'),
            'intYearReleased': item.get('intYearReleased'),
        }
        for item in album_items
    ]

    return jsonify({'data': transformed}), 200


@music_sources_bp.route('/lyrics', methods=['GET'])
@jwt_required()
def get_lyrics():
    artist = (request.args.get('artist') or '').strip()
    title = (request.args.get('title') or '').strip()

    if not artist or not title:
        return _error('Query parameters artist and title are required', 400)

    direct_url = f"{LYRICS_BASE_URL}/v1/{quote(artist)}/{quote(title)}"

    try:
        direct_response = requests.get(direct_url, timeout=_timeout())
    except requests.RequestException as exc:
        return _error(f'Lyrics request failed: {exc}', 502)

    if direct_response.status_code == 200:
        payload = direct_response.json()
        lyrics = _normalize_lyrics(payload.get('lyrics') or '')
        if lyrics:
            return jsonify({'lyrics': lyrics, 'source': 'lyrics.ovh'}), 200

    if direct_response.status_code != 404:
        return _error(f'Lyrics API returned status {direct_response.status_code}', direct_response.status_code)

    suggest_url = f"{LYRICS_BASE_URL}/suggest/{quote(title)}"
    try:
        suggest_response = requests.get(suggest_url, timeout=_timeout())
    except requests.RequestException as exc:
        return _error(f'Lyrics suggest request failed: {exc}', 502)

    if suggest_response.status_code >= 400:
        return _error('Lyrics not found', 404)

    try:
        suggest_payload = suggest_response.json()
    except ValueError:
        return _error('Failed to parse lyrics suggest response', 502)

    candidates = suggest_payload.get('data') or []
    best_candidate = _closest_lyrics_candidate(title, artist, candidates)

    if not best_candidate:
        return _error('Lyrics not found', 404)

    candidate_title = (best_candidate.get('title') or '').strip()
    candidate_artist = ((best_candidate.get('artist') or {}).get('name') or '').strip()

    if not candidate_title or not candidate_artist:
        return _error('Lyrics not found', 404)

    fallback_url = f"{LYRICS_BASE_URL}/v1/{quote(candidate_artist)}/{quote(candidate_title)}"

    try:
        fallback_response = requests.get(fallback_url, timeout=_timeout())
    except requests.RequestException as exc:
        return _error(f'Lyrics fallback request failed: {exc}', 502)

    if fallback_response.status_code >= 400:
        return _error('Lyrics not found', 404)

    try:
        fallback_payload = fallback_response.json()
    except ValueError:
        return _error('Failed to parse lyrics response', 502)

    lyrics = _normalize_lyrics(fallback_payload.get('lyrics') or '')
    if not lyrics:
        return _error('Lyrics not found', 404)

    return jsonify({'lyrics': lyrics, 'source': 'lyrics.ovh'}), 200


@music_sources_bp.route('/mbid', methods=['GET'])
@jwt_required()
def get_mbid():
    artist = (request.args.get('artist') or '').strip()
    title = (request.args.get('title') or '').strip()

    if not artist or not title:
        return _error('Query parameters artist and title are required', 400)

    user_agent = current_app.config.get('MUSICBRAINZ_USER_AGENT', 'MusicPlayerApp/1.0 (your@email.com)')

    payload, err = _cached_json_request(
        namespace='musicbrainz:recording',
        url=f'{MUSICBRAINZ_BASE_URL}/recording/',
        params={
            'query': f'artist:{artist} recording:{title}',
            'fmt': 'json',
            'limit': 1,
        },
        headers={'User-Agent': user_agent},
    )
    if err:
        return err

    recordings = payload.get('recordings') or []
    if not recordings:
        return jsonify({'recording_mbid': None, 'release_mbid': None}), 200

    first = recordings[0]
    releases = first.get('releases') or []

    return jsonify(
        {
            'recording_mbid': first.get('id'),
            'release_mbid': releases[0].get('id') if releases else None,
        }
    ), 200


@music_sources_bp.route('/coverart', methods=['GET'])
@jwt_required()
def get_cover_art():
    release_mbid = (request.args.get('mbid') or '').strip()
    if not release_mbid:
        return _error('Query parameter mbid is required', 400)

    url = f'{COVER_ART_BASE_URL}/release/{release_mbid}/front'

    try:
        response = requests.get(url, timeout=_timeout(), allow_redirects=False)
    except requests.RequestException as exc:
        return _error(f'Cover art request failed: {exc}', 502)

    if response.status_code in {301, 302, 303, 307, 308}:
        location = response.headers.get('Location')
        return jsonify(location), 200

    if response.status_code == 404:
        return jsonify(None), 200

    if response.status_code >= 400:
        return _error(f'Cover art API returned status {response.status_code}', response.status_code)

    # If upstream returns 200 with direct image URL, return the requested URL.
    return jsonify(url), 200
