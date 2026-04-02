# Music Player Backend API

A Flask-based REST API for the Music Player app. Handles user authentication, playlists, favorites, and play history.

## Features

- **User Authentication**: Register, login, JWT tokens with refresh
- **Playlists**: Create, update, delete playlists; add/remove songs
- **Favorites**: Add/remove favorite songs, check favorite status
- **Play History**: Track recently played songs
- **Test Page**: Built-in test page to verify all endpoints

## API Endpoints

### Authentication (`/api/auth`)
- `POST /register` - Register new user
- `POST /login` - Login and get tokens
- `POST /refresh` - Refresh access token
- `GET /me` - Get current user profile
- `PUT /update` - Update user profile
- `POST /logout` - Logout

### Playlists (`/api/playlists`)
- `GET /` - Get all user playlists
- `POST /` - Create new playlist
- `GET /<id>` - Get single playlist
- `PUT /<id>` - Update playlist
- `DELETE /<id>` - Delete playlist
- `POST /<id>/songs` - Add song to playlist
- `DELETE /<id>/songs/<song_id>` - Remove song from playlist

### Favorites (`/api/favorites`)
- `GET /` - Get all favorites
- `POST /` - Add to favorites
- `GET /<song_id>/check` - Check if song is favorited
- `DELETE /<song_id>` - Remove from favorites

### History (`/api/history`)
- `GET /` - Get play history
- `POST /` - Add to history
- `DELETE /` - Clear history

## Setup

### Local Development

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
```

### PythonAnywhere Deployment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yamenmod9/music-app-backend.git
   ```

2. **Create virtual environment**:
   ```bash
   cd music-app-backend
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Web App**:
   - Go to Web tab → Add new web app
   - Choose Manual configuration → Python 3.10
   - Set source code path: `/home/yourusername/music-app-backend`
   - Set virtualenv path: `/home/yourusername/music-app-backend/venv`

4. **Edit WSGI file** (`/var/www/yourusername_pythonanywhere_com_wsgi.py`):
   ```python
   import sys
   path = '/home/yourusername/music-app-backend'
   if path not in sys.path:
       sys.path.insert(0, path)
   
   from app import app as application
   ```

5. **Set environment variables** (in Web tab → Environment variables):
   ```
   SECRET_KEY=your-secret-key-here
   JWT_SECRET_KEY=your-jwt-secret-key-here
   ```

6. **Reload the web app**

## Testing

Visit `/test` in your browser to access the built-in test page that runs all API tests automatically.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | (required) |
| `JWT_SECRET_KEY` | JWT signing key | (required) |
| `LASTFM_API_KEY` | Last.fm API key for artist metadata | (required for music enrichment) |
| `MUSICBRAINZ_USER_AGENT` | MusicBrainz user-agent header | `MusicPlayerApp/1.0 (your@email.com)` |
| `API_CACHE_TTL` | In-memory API cache TTL (seconds) | `3600` |
| `DATABASE_URL` | Database connection URL | `sqlite:///music_player.db` |

## License

MIT
