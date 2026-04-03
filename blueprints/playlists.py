from datetime import datetime
import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from extensions import db
from models import Playlist, PlaylistSong
from utils import error_response

playlists_bp = Blueprint('playlists', __name__, url_prefix='/api/playlists')


def _clean_text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ''
    return str(value).strip()


@playlists_bp.route('', methods=['GET'])
@jwt_required()
def get_playlists():
    current_user_id = get_jwt_identity()
    
    playlists = Playlist.query.filter_by(user_id=current_user_id)\
        .order_by(Playlist.updated_at.desc()).all()
    
    return jsonify([p.to_dict() for p in playlists]), 200


@playlists_bp.route('/<playlist_id>', methods=['GET'])
@jwt_required()
def get_playlist(playlist_id):
    current_user_id = get_jwt_identity()
    
    playlist = Playlist.query.filter_by(
        id=playlist_id, 
        user_id=current_user_id
    ).first()
    
    if not playlist:
        return error_response('Playlist not found', 404)
    
    return jsonify(playlist.to_dict()), 200


@playlists_bp.route('', methods=['POST'])
@jwt_required()
def create_playlist():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return error_response('No data provided', 400)
    
    name = _clean_text(data.get('name'))
    if not name:
        return error_response('Playlist name is required', 400)

    description = _clean_text(data.get('description')) or None
    
    playlist = Playlist(
        id=str(uuid.uuid4()),
        user_id=current_user_id,
        name=name,
        description=description,
        cover_art=data.get('cover_art'),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.session.add(playlist)
    db.session.commit()
    
    return jsonify(playlist.to_dict()), 201


@playlists_bp.route('/<playlist_id>', methods=['PUT'])
@jwt_required()
def update_playlist(playlist_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)
    
    playlist = Playlist.query.filter_by(
        id=playlist_id,
        user_id=current_user_id
    ).first()
    
    if not playlist:
        return error_response('Playlist not found', 404)
    
    if 'name' in data:
        name = _clean_text(data.get('name'))
        if name:
            playlist.name = name
    
    if 'description' in data:
        playlist.description = _clean_text(data.get('description')) or None
    
    if 'cover_art' in data:
        playlist.cover_art = data['cover_art']
    
    playlist.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify(playlist.to_dict()), 200


@playlists_bp.route('/<playlist_id>', methods=['DELETE'])
@jwt_required()
def delete_playlist(playlist_id):
    current_user_id = get_jwt_identity()
    
    playlist = Playlist.query.filter_by(
        id=playlist_id,
        user_id=current_user_id
    ).first()
    
    if not playlist:
        return error_response('Playlist not found', 404)
    
    db.session.delete(playlist)
    db.session.commit()
    
    return jsonify({'message': 'Playlist deleted'}), 200


@playlists_bp.route('/<playlist_id>/songs', methods=['POST'])
@jwt_required()
def add_song_to_playlist(playlist_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    playlist = Playlist.query.filter_by(
        id=playlist_id,
        user_id=current_user_id
    ).first()
    
    if not playlist:
        return error_response('Playlist not found', 404)
    
    if not data or 'id' not in data:
        return error_response('Song data is required', 400)
    
    song_id = data['id']
    
    # Check if song already exists in playlist
    existing = PlaylistSong.query.filter_by(
        playlist_id=playlist_id,
        song_id=song_id
    ).first()
    
    if existing:
        return error_response('Song already in playlist', 409)
    
    # Get max position
    max_pos = db.session.query(db.func.max(PlaylistSong.position))\
        .filter_by(playlist_id=playlist_id).scalar() or -1
    
    playlist_song = PlaylistSong(
        playlist_id=playlist_id,
        song_id=song_id,
        song_data=data,
        position=max_pos + 1
    )
    
    db.session.add(playlist_song)
    playlist.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'message': 'Song added to playlist'}), 200


@playlists_bp.route('/<playlist_id>/songs/<song_id>', methods=['DELETE'])
@jwt_required()
def remove_song_from_playlist(playlist_id, song_id):
    current_user_id = get_jwt_identity()
    
    playlist = Playlist.query.filter_by(
        id=playlist_id,
        user_id=current_user_id
    ).first()
    
    if not playlist:
        return error_response('Playlist not found', 404)
    
    playlist_song = PlaylistSong.query.filter_by(
        playlist_id=playlist_id,
        song_id=int(song_id)
    ).first()
    
    if not playlist_song:
        return error_response('Song not found in playlist', 404)
    
    db.session.delete(playlist_song)
    playlist.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'message': 'Song removed from playlist'}), 200


@playlists_bp.route('/<playlist_id>/reorder', methods=['PUT'])
@jwt_required()
def reorder_playlist(playlist_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    playlist = Playlist.query.filter_by(
        id=playlist_id,
        user_id=current_user_id
    ).first()
    
    if not playlist:
        return error_response('Playlist not found', 404)
    
    if not data or 'song_ids' not in data:
        return error_response('Song IDs required', 400)
    
    song_ids = data['song_ids']
    
    for position, song_id in enumerate(song_ids):
        playlist_song = PlaylistSong.query.filter_by(
            playlist_id=playlist_id,
            song_id=song_id
        ).first()
        
        if playlist_song:
            playlist_song.position = position
    
    playlist.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify(playlist.to_dict()), 200
