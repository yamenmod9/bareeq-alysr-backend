from datetime import datetime
import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)

from extensions import db
from models import User
from utils import error_response

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _clean_text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ''
    return str(value).strip()


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data:
        return error_response('No data provided', 400)
    
    email = _clean_text(data.get('email')).lower()
    password = data.get('password', '')
    username = _clean_text(data.get('username')) or None
    
    if not email or not password:
        return error_response('Email and password are required', 400)
    
    if len(password) < 6:
        return error_response('Password must be at least 6 characters', 400)
    
    # Check if user exists
    if User.query.filter_by(email=email).first():
        return error_response('Email already registered', 409)
    
    # Create user
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        username=username,
        created_at=datetime.utcnow()
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    # Generate tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data:
        return error_response('No data provided', 400)
    
    email = _clean_text(data.get('email')).lower()
    password = data.get('password', '')
    
    if not email or not password:
        return error_response('Email and password are required', 400)
    
    # Find user
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return error_response('Invalid email or password', 401)
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.session.commit()
    
    # Generate tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    
    user = User.query.get(current_user_id)
    if not user:
        return error_response('User not found', 404)
    
    access_token = create_access_token(identity=current_user_id)
    refresh_token = create_refresh_token(identity=current_user_id)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    current_user_id = get_jwt_identity()
    
    user = User.query.get(current_user_id)
    if not user:
        return error_response('User not found', 404)
    
    return jsonify(user.to_dict()), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # In a real app, you might want to blacklist the token
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/update', methods=['PUT'])
@jwt_required()
def update_profile():
    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)
    
    user = User.query.get(current_user_id)
    if not user:
        return error_response('User not found', 404)
    
    if 'username' in data:
        user.username = _clean_text(data.get('username')) or None
    
    if 'avatar_url' in data:
        user.avatar_url = data['avatar_url']
    
    db.session.commit()
    
    return jsonify(user.to_dict()), 200
