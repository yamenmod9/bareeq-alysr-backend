import os
from flask import Flask, jsonify, render_template_string
from dotenv import load_dotenv

from config import config
from extensions import db, jwt, cors, migrate
from blueprints import auth_bp, playlists_bp, favorites_bp, history_bp, music_sources_bp


# HTML template for the test page
TEST_PAGE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Music Player API - Test Suite</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { color: #a855f7; margin-bottom: 20px; }
        .controls {
            display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #a855f7, #7c3aed);
            color: white;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(168,85,247,0.4); }
        .btn-danger { background: #ef4444; color: white; }
        .btn-secondary { background: #374151; color: white; }
        .status {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .status.running { background: #3b82f6; }
        .status.success { background: #22c55e; }
        .status.failed { background: #ef4444; }
        .results {
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        .test-group {
            margin-bottom: 20px;
            border: 1px solid #374151;
            border-radius: 8px;
            overflow: hidden;
        }
        .test-group-header {
            background: #1f2937;
            padding: 12px 16px;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
        }
        .test-item {
            padding: 12px 16px;
            border-top: 1px solid #374151;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .test-item:hover { background: rgba(255,255,255,0.02); }
        .test-name { font-weight: 500; }
        .test-details {
            font-size: 12px;
            color: #9ca3af;
            margin-top: 4px;
        }
        .badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge.pass { background: #22c55e; color: white; }
        .badge.fail { background: #ef4444; color: white; }
        .badge.pending { background: #6b7280; color: white; }
        .badge.running { background: #3b82f6; color: white; }
        .badge.skip { background: #f59e0b; color: #111827; }
        .summary {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .summary-card {
            background: #1f2937;
            padding: 16px 24px;
            border-radius: 8px;
            min-width: 120px;
        }
        .summary-value { font-size: 32px; font-weight: 700; }
        .summary-label { color: #9ca3af; font-size: 14px; }
        .log-output {
            background: #0d1117;
            border-radius: 8px;
            padding: 16px;
            margin-top: 20px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .log-entry { margin-bottom: 4px; }
        .log-entry.success { color: #22c55e; }
        .log-entry.error { color: #ef4444; }
        .log-entry.info { color: #3b82f6; }
        .spinner {
            width: 20px; height: 20px;
            border: 2px solid transparent;
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Music Player API Test Suite</h1>
        
        <div class="controls">
            <button class="btn-primary" onclick="runAllTests()" id="runBtn">
                ▶ Run All Tests
            </button>
            <button class="btn-secondary" onclick="clearResults()">
                Clear Results
            </button>
            <span class="status" id="statusBadge">Ready</span>
        </div>
        
        <div class="summary" id="summary" style="display:none;">
            <div class="summary-card">
                <div class="summary-value" id="totalTests">0</div>
                <div class="summary-label">Total</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color:#22c55e" id="passedTests">0</div>
                <div class="summary-label">Passed</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color:#ef4444" id="failedTests">0</div>
                <div class="summary-label">Failed</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color:#f59e0b" id="skippedTests">0</div>
                <div class="summary-label">Skipped</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" style="color:#3b82f6" id="duration">0s</div>
                <div class="summary-label">Duration</div>
            </div>
        </div>
        
        <div class="results" id="results">
            <p style="color:#9ca3af;">Click "Run All Tests" to start the test suite.</p>
        </div>
        
        <div class="log-output" id="logOutput"></div>
    </div>

    <script>
        const API_BASE = window.location.origin + '/api';
        let testUser = null;
        let accessToken = null;
        let refreshToken = null;
        let testPlaylistId = null;
        let testResults = [];

        const testPlaylistSongIds = [1001, 1002];
        const musicProbe = {
            trackId: null,
            albumId: null,
            artistId: null,
            artistName: '',
            trackTitle: '',
            releaseMbid: null,
            recordingMbid: null,
            tadbArtistMbid: null,
        };
        
        function log(msg, type = 'info') {
            const logEl = document.getElementById('logOutput');
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logEl.appendChild(entry);
            logEl.scrollTop = logEl.scrollHeight;
        }
        
        function updateStatus(text, cls) {
            const badge = document.getElementById('statusBadge');
            badge.textContent = text;
            badge.className = 'status ' + cls;
        }

        function createSkip(message) {
            const err = new Error(message);
            err.isSkip = true;
            return err;
        }

        function ensureValue(value, message) {
            if (value === null || value === undefined || value === '') {
                throw createSkip(message);
            }
            return value;
        }

        function encodeSegment(value) {
            return encodeURIComponent(String(value || '').trim());
        }

        function getErrorMessage(response, fallback = 'Request failed') {
            if (!response) {
                return fallback;
            }

            const payload = response.data || {};
            const message = payload.message || payload.error;
            if (typeof message === 'string' && message.trim()) {
                return message;
            }

            return `${fallback} (HTTP ${response.status})`;
        }

        function skipIfLastFmNotConfigured(response) {
            if (!response || response.status !== 500) {
                return;
            }

            const message = getErrorMessage(response, 'Last.fm request failed');
            if (message.includes('LASTFM_API_KEY is not configured')) {
                throw createSkip(message);
            }
        }

        function skipIfExternalBlocked(response, sourceName) {
            if (!response || response.status !== 502) {
                return;
            }

            const message = getErrorMessage(response, `${sourceName} request failed`);
            const blockedPatterns = [
                'Unable to connect to proxy',
                'Tunnel connection failed: 403 Forbidden',
                'ProxyError',
                'Max retries exceeded',
            ];

            const isBlocked = blockedPatterns.some((pattern) => message.includes(pattern));
            if (isBlocked) {
                throw createSkip(`${sourceName} is blocked by host network/proxy restrictions`);
            }
        }
        
        async function api(method, endpoint, data = null, auth = true) {
            const headers = { 'Content-Type': 'application/json' };
            if (auth && accessToken) {
                headers['Authorization'] = 'Bearer ' + accessToken;
            }
            
            const opts = { method, headers };
            if (data) opts.body = JSON.stringify(data);
            
            const resp = await fetch(API_BASE + endpoint, opts);
            const json = await resp.json().catch(() => ({}));
            return { status: resp.status, ok: resp.ok, data: json };
        }
        
        const tests = [
            // Health and utility endpoints
            {
                group: 'Health',
                name: 'Root Page',
                run: async () => {
                    const resp = await fetch(window.location.origin + '/');
                    if (!resp.ok) throw new Error(`Root page failed (HTTP ${resp.status})`);
                    return { status: resp.status };
                }
            },
            {
                group: 'Health',
                name: 'Test Page Endpoint',
                run: async () => {
                    const resp = await fetch(window.location.origin + '/test');
                    if (!resp.ok) throw new Error(`Test page failed (HTTP ${resp.status})`);
                    return { status: resp.status };
                }
            },
            {
                group: 'Health',
                name: 'API Health Check',
                run: async () => {
                    const r = await api('GET', '/health', null, false);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Health check failed'));
                    return r.data;
                }
            },

            // Authentication endpoints
            {
                group: 'Authentication',
                name: 'Register New User',
                run: async () => {
                    const uniqueSeed = Date.now();
                    testUser = {
                        email: `test_${uniqueSeed}@example.com`,
                        password: 'test123456',
                        username: `TestUser_${uniqueSeed}`,
                    };

                    const r = await api('POST', '/auth/register', testUser, false);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Registration failed'));

                    accessToken = r.data.access_token;
                    refreshToken = r.data.refresh_token;
                    return { userId: r.data.user.id, email: r.data.user.email };
                }
            },
            {
                group: 'Authentication',
                name: 'Login',
                run: async () => {
                    ensureValue(testUser?.email, 'Register New User must pass first');

                    const r = await api(
                        'POST',
                        '/auth/login',
                        { email: testUser.email, password: testUser.password },
                        false
                    );

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Login failed'));
                    accessToken = r.data.access_token;
                    refreshToken = r.data.refresh_token;
                    return { success: true };
                }
            },
            {
                group: 'Authentication',
                name: 'Get Profile',
                run: async () => {
                    const r = await api('GET', '/auth/me');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get profile failed'));
                    return { id: r.data.id, email: r.data.email };
                }
            },
            {
                group: 'Authentication',
                name: 'Update Profile',
                run: async () => {
                    const updatedUsername = `Updated_${Date.now()}`;
                    const r = await api('PUT', '/auth/update', {
                        username: updatedUsername,
                        avatar_url: 'https://example.com/avatar.png',
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Update profile failed'));
                    return { username: r.data.username, avatarUrl: r.data.avatarUrl };
                }
            },
            {
                group: 'Authentication',
                name: 'Refresh Token',
                run: async () => {
                    ensureValue(refreshToken, 'Refresh token is not available');

                    const headers = {
                        'Content-Type': 'application/json',
                        Authorization: 'Bearer ' + refreshToken,
                    };

                    const resp = await fetch(API_BASE + '/auth/refresh', { method: 'POST', headers });
                    const data = await resp.json().catch(() => ({}));

                    if (!resp.ok) {
                        throw new Error(data.message || data.error || `Refresh failed (HTTP ${resp.status})`);
                    }

                    accessToken = data.access_token;
                    refreshToken = data.refresh_token;
                    return { refreshed: true };
                }
            },

            // Playlist endpoints
            {
                group: 'Playlists',
                name: 'Create Playlist',
                run: async () => {
                    const r = await api('POST', '/playlists', {
                        name: 'Test Playlist',
                        description: 'Created by automated test',
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Create playlist failed'));
                    testPlaylistId = r.data.id;
                    return { playlistId: testPlaylistId };
                }
            },
            {
                group: 'Playlists',
                name: 'Get All Playlists',
                run: async () => {
                    const r = await api('GET', '/playlists');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get playlists failed'));
                    return { count: Array.isArray(r.data) ? r.data.length : 0 };
                }
            },
            {
                group: 'Playlists',
                name: 'Get Single Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const r = await api('GET', '/playlists/' + playlistId);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get playlist failed'));
                    return { name: r.data.name };
                }
            },
            {
                group: 'Playlists',
                name: 'Add Song 1 to Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const songId = testPlaylistSongIds[0];

                    const r = await api('POST', `/playlists/${playlistId}/songs`, {
                        id: songId,
                        title: 'Test Song 1',
                        artist: 'Test Artist',
                        album: 'Test Album',
                        path: '/music/test1.mp3',
                        duration: 180000,
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Add song 1 failed'));
                    return { songId };
                }
            },
            {
                group: 'Playlists',
                name: 'Add Song 2 to Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const songId = testPlaylistSongIds[1];

                    const r = await api('POST', `/playlists/${playlistId}/songs`, {
                        id: songId,
                        title: 'Test Song 2',
                        artist: 'Test Artist',
                        album: 'Test Album',
                        path: '/music/test2.mp3',
                        duration: 185000,
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Add song 2 failed'));
                    return { songId };
                }
            },
            {
                group: 'Playlists',
                name: 'Reorder Playlist Songs',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const newOrder = [testPlaylistSongIds[1], testPlaylistSongIds[0]];

                    const r = await api('PUT', `/playlists/${playlistId}/reorder`, {
                        song_ids: newOrder,
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Reorder playlist failed'));

                    const songs = Array.isArray(r.data.songs) ? r.data.songs : [];
                    const orderedIds = songs.map((s) => s.id).slice(0, 2);
                    return { expectedOrder: newOrder, returnedOrder: orderedIds };
                }
            },
            {
                group: 'Playlists',
                name: 'Update Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const r = await api('PUT', '/playlists/' + playlistId, {
                        name: 'Updated Test Playlist',
                        description: 'Updated by automated test',
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Update playlist failed'));
                    return { newName: r.data.name };
                }
            },
            {
                group: 'Playlists',
                name: 'Remove Song 1 from Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const songId = testPlaylistSongIds[0];
                    const r = await api('DELETE', `/playlists/${playlistId}/songs/${songId}`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Remove song 1 failed'));
                    return { songId };
                }
            },
            {
                group: 'Playlists',
                name: 'Remove Song 2 from Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'Create Playlist must pass first');
                    const songId = testPlaylistSongIds[1];
                    const r = await api('DELETE', `/playlists/${playlistId}/songs/${songId}`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Remove song 2 failed'));
                    return { songId };
                }
            },

            // Favorites endpoints
            {
                group: 'Favorites',
                name: 'Add to Favorites',
                run: async () => {
                    const r = await api('POST', '/favorites', {
                        id: 2001,
                        title: 'Favorite Song',
                        artist: 'Favorite Artist',
                        album: 'Favorite Album',
                        path: '/music/favorite.mp3',
                        duration: 200000,
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Add favorite failed'));
                    return { success: true };
                }
            },
            {
                group: 'Favorites',
                name: 'Get All Favorites',
                run: async () => {
                    const r = await api('GET', '/favorites');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get favorites failed'));
                    return { count: Array.isArray(r.data) ? r.data.length : 0 };
                }
            },
            {
                group: 'Favorites',
                name: 'Check Favorite Status',
                run: async () => {
                    const r = await api('GET', '/favorites/2001/check');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Check favorite failed'));
                    return { isFavorite: !!r.data.is_favorite };
                }
            },
            {
                group: 'Favorites',
                name: 'Remove from Favorites',
                run: async () => {
                    const r = await api('DELETE', '/favorites/2001');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Remove favorite failed'));
                    return { success: true };
                }
            },

            // History endpoints
            {
                group: 'History',
                name: 'Add to History',
                run: async () => {
                    const r = await api('POST', '/history', {
                        id: 3001,
                        title: 'History Song',
                        artist: 'History Artist',
                        album: 'History Album',
                        path: '/music/history.mp3',
                        duration: 250000,
                    });

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Add history failed'));
                    return { success: true };
                }
            },
            {
                group: 'History',
                name: 'Get Play History',
                run: async () => {
                    const r = await api('GET', '/history?limit=10');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get history failed'));
                    return { count: Array.isArray(r.data) ? r.data.length : 0 };
                }
            },
            {
                group: 'History',
                name: 'Clear History',
                run: async () => {
                    const r = await api('DELETE', '/history');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Clear history failed'));
                    return { success: true };
                }
            },

            // Music source endpoints
            {
                group: 'Music Sources',
                name: 'Search Tracks (public)',
                run: async () => {
                    const r = await api('GET', `/music/search?q=${encodeSegment('Daft Punk')}&type=track`, null, false);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Track search failed'));

                    const tracks = Array.isArray(r.data.data) ? r.data.data : [];
                    if (!tracks.length) throw createSkip('No track search results were returned');

                    const first = tracks[0] || {};
                    musicProbe.trackId = first.id || null;
                    musicProbe.albumId = first.album_id || null;
                    musicProbe.artistId = first.artist_id || null;
                    musicProbe.artistName = first.artist || '';
                    musicProbe.trackTitle = first.title || '';

                    return {
                        count: tracks.length,
                        trackId: musicProbe.trackId,
                        artist: musicProbe.artistName,
                    };
                }
            },
            {
                group: 'Music Sources',
                name: 'Search Artists (public)',
                run: async () => {
                    const r = await api('GET', `/music/search?q=${encodeSegment('Daft Punk')}&type=artist`, null, false);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Artist search failed'));
                    const artists = Array.isArray(r.data.data) ? r.data.data : [];
                    return { count: artists.length };
                }
            },
            {
                group: 'Music Sources',
                name: 'Search Albums (public)',
                run: async () => {
                    const r = await api('GET', `/music/search?q=${encodeSegment('Daft Punk')}&type=album`, null, false);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Album search failed'));
                    const albums = Array.isArray(r.data.data) ? r.data.data : [];
                    return { count: albums.length };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Track Details',
                run: async () => {
                    const trackId = ensureValue(musicProbe.trackId, 'Track ID not available from Search Tracks');
                    const r = await api('GET', `/music/track/${trackId}`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get track details failed'));
                    return { id: r.data.id, title: r.data.title };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Album Details',
                run: async () => {
                    const albumId = ensureValue(musicProbe.albumId, 'Album ID not available from Search Tracks');
                    const r = await api('GET', `/music/album/${albumId}`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get album details failed'));
                    return { id: r.data.id, title: r.data.title };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Artist Details',
                run: async () => {
                    const artistId = ensureValue(musicProbe.artistId, 'Artist ID not available from Search Tracks');
                    const r = await api('GET', `/music/artist/${artistId}`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get artist details failed'));
                    return { id: r.data.id, name: r.data.name };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Artist Top Tracks',
                run: async () => {
                    const artistId = ensureValue(musicProbe.artistId, 'Artist ID not available from Search Tracks');
                    const r = await api('GET', `/music/artist/${artistId}/top`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get artist top tracks failed'));
                    const tracks = Array.isArray(r.data.data) ? r.data.data : [];
                    return { count: tracks.length };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Charts',
                run: async () => {
                    const r = await api('GET', '/music/charts');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Get charts failed'));
                    const tracks = Array.isArray(r.data.data) ? r.data.data : [];
                    return { count: tracks.length };
                }
            },
            {
                group: 'Music Sources',
                name: 'Lookup MusicBrainz MBID',
                run: async () => {
                    const artistName = ensureValue(musicProbe.artistName, 'Artist name not available from Search Tracks');
                    const trackTitle = ensureValue(musicProbe.trackTitle, 'Track title not available from Search Tracks');

                    const r = await api(
                        'GET',
                        `/music/mbid?artist=${encodeSegment(artistName)}&title=${encodeSegment(trackTitle)}`
                    );
                    if (!r.ok) throw new Error(getErrorMessage(r, 'MBID lookup failed'));

                    musicProbe.recordingMbid = r.data.recording_mbid || null;
                    musicProbe.releaseMbid = r.data.release_mbid || null;
                    return {
                        recordingMbid: musicProbe.recordingMbid,
                        releaseMbid: musicProbe.releaseMbid,
                    };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Cover Art',
                run: async () => {
                    const releaseMbid = ensureValue(musicProbe.releaseMbid, 'No release MBID available for cover art lookup');
                    const r = await api('GET', `/music/coverart?mbid=${encodeSegment(releaseMbid)}`);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Cover art lookup failed'));
                    return { coverUrl: r.data || null };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get TheAudioDB Artist',
                run: async () => {
                    const artistName = musicProbe.artistName || 'Adele';
                    const r = await api('GET', `/music/tadb/artist?name=${encodeSegment(artistName)}`);
                    skipIfExternalBlocked(r, 'TheAudioDB');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'TheAudioDB artist lookup failed'));

                    if (r.data && r.data.data === null) {
                        return { found: false };
                    }

                    musicProbe.tadbArtistMbid = r.data.strArtistMBID || null;
                    return { found: true, artist: r.data.name || artistName };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get TheAudioDB Discography',
                run: async () => {
                    const artistName = musicProbe.artistName || 'Adele';
                    const r = await api('GET', `/music/tadb/discography?id=${encodeSegment(artistName)}`);
                    skipIfExternalBlocked(r, 'TheAudioDB');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'TheAudioDB discography lookup failed'));
                    const items = Array.isArray(r.data.data) ? r.data.data : [];
                    return { count: items.length };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get TheAudioDB Album by MBID',
                run: async () => {
                    const mbid = musicProbe.releaseMbid || musicProbe.tadbArtistMbid;
                    ensureValue(mbid, 'No MBID available for TheAudioDB album lookup');

                    const r = await api('GET', `/music/tadb/album?id=${encodeSegment(mbid)}`);
                    skipIfExternalBlocked(r, 'TheAudioDB');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'TheAudioDB album lookup failed'));

                    if (r.data && r.data.data === null) {
                        return { found: false };
                    }

                    return { found: true, album: r.data.strAlbum || null };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Last.fm Artist Info',
                run: async () => {
                    const artistName = ensureValue(musicProbe.artistName, 'Artist name not available from Search Tracks');
                    const r = await api('GET', `/music/artist/${encodeSegment(artistName)}/info`);
                    skipIfLastFmNotConfigured(r);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Last.fm artist info failed'));
                    return { name: r.data.name, listeners: r.data.listeners };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Last.fm Similar Artists',
                run: async () => {
                    const artistName = ensureValue(musicProbe.artistName, 'Artist name not available from Search Tracks');
                    const r = await api('GET', `/music/artist/${encodeSegment(artistName)}/similar`);
                    skipIfLastFmNotConfigured(r);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Last.fm similar artists failed'));
                    const items = Array.isArray(r.data.data) ? r.data.data : [];
                    return { count: items.length };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Last.fm Track Info',
                run: async () => {
                    const artistName = ensureValue(musicProbe.artistName, 'Artist name not available from Search Tracks');
                    const trackTitle = ensureValue(musicProbe.trackTitle, 'Track title not available from Search Tracks');
                    const r = await api(
                        'GET',
                        `/music/track/${encodeSegment(artistName)}/${encodeSegment(trackTitle)}/info`
                    );

                    skipIfLastFmNotConfigured(r);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Last.fm track info failed'));
                    return { name: r.data.name, artist: r.data.artist };
                }
            },
            {
                group: 'Music Sources',
                name: 'Get Lyrics',
                run: async () => {
                    const artistName = ensureValue(musicProbe.artistName, 'Artist name not available from Search Tracks');
                    const trackTitle = ensureValue(musicProbe.trackTitle, 'Track title not available from Search Tracks');
                    const r = await api(
                        'GET',
                        `/music/lyrics?artist=${encodeSegment(artistName)}&title=${encodeSegment(trackTitle)}`
                    );

                    if (r.status === 404) {
                        return { lyricsFound: false };
                    }

                    if (!r.ok) throw new Error(getErrorMessage(r, 'Lyrics lookup failed'));
                    const lyrics = typeof r.data.lyrics === 'string' ? r.data.lyrics : '';
                    return { lyricsFound: !!lyrics, length: lyrics.length };
                }
            },

            // Cleanup endpoints
            {
                group: 'Cleanup',
                name: 'Delete Test Playlist',
                run: async () => {
                    const playlistId = ensureValue(testPlaylistId, 'No test playlist to delete');
                    const r = await api('DELETE', '/playlists/' + playlistId);
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Delete playlist failed'));
                    return { success: true };
                }
            },
            {
                group: 'Cleanup',
                name: 'Logout',
                run: async () => {
                    ensureValue(accessToken, 'No access token available for logout');
                    const r = await api('POST', '/auth/logout');
                    if (!r.ok) throw new Error(getErrorMessage(r, 'Logout failed'));
                    accessToken = null;
                    refreshToken = null;
                    return { success: true };
                }
            },
        ];
        
        function renderResults() {
            const container = document.getElementById('results');
            const groups = {};
            
            tests.forEach((test, idx) => {
                if (!groups[test.group]) groups[test.group] = [];
                groups[test.group].push({ ...test, result: testResults[idx] });
            });
            
            let html = '';
            for (const [groupName, groupTests] of Object.entries(groups)) {
                const passed = groupTests.filter(t => t.result?.status === 'pass').length;
                const skipped = groupTests.filter(t => t.result?.status === 'skip').length;
                const total = groupTests.length;
                
                html += `<div class="test-group">
                    <div class="test-group-header">
                        <span>${groupName}</span>
                        <span>${passed} pass, ${skipped} skip, ${total} total</span>
                    </div>`;
                    
                for (const test of groupTests) {
                    const r = test.result || { status: 'pending' };
                    const badge = r.status === 'pass' ? 'pass' : 
                                  r.status === 'fail' ? 'fail' :
                                  r.status === 'skip' ? 'skip' :
                                  r.status === 'running' ? 'running' : 'pending';
                    
                    html += `<div class="test-item">
                        <div>
                            <div class="test-name">${test.name}</div>
                            ${r.details ? `<div class="test-details">${r.details}</div>` : ''}
                        </div>
                        <span class="badge ${badge}">${r.status?.toUpperCase() || 'PENDING'}</span>
                    </div>`;
                }
                html += '</div>';
            }
            
            container.innerHTML = html;
        }
        
        function updateSummary() {
            const passed = testResults.filter(r => r?.status === 'pass').length;
            const failed = testResults.filter(r => r?.status === 'fail').length;
            const skipped = testResults.filter(r => r?.status === 'skip').length;
            
            document.getElementById('summary').style.display = 'flex';
            document.getElementById('totalTests').textContent = tests.length;
            document.getElementById('passedTests').textContent = passed;
            document.getElementById('failedTests').textContent = failed;
            document.getElementById('skippedTests').textContent = skipped;
        }
        
        async function runAllTests() {
            const btn = document.getElementById('runBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Running...';
            
            testResults = [];
            accessToken = null;
            refreshToken = null;
            testPlaylistId = null;
            
            document.getElementById('logOutput').innerHTML = '';
            updateStatus('Running...', 'running');
            log('Starting test suite...', 'info');
            
            const startTime = Date.now();
            
            for (let i = 0; i < tests.length; i++) {
                const test = tests[i];
                testResults[i] = { status: 'running' };
                renderResults();
                
                log(`Running: ${test.group} > ${test.name}`, 'info');
                
                try {
                    const result = await test.run();
                    testResults[i] = { 
                        status: 'pass', 
                        details: JSON.stringify(result).slice(0, 100) 
                    };
                    log(`✓ PASS: ${test.name}`, 'success');
                } catch (err) {
                    if (err?.isSkip) {
                        testResults[i] = {
                            status: 'skip',
                            details: err.message,
                        };
                        log(`↷ SKIP: ${test.name} - ${err.message}`, 'info');
                    } else {
                        testResults[i] = {
                            status: 'fail',
                            details: err.message,
                        };
                        log(`✗ FAIL: ${test.name} - ${err.message}`, 'error');
                    }
                }
                
                renderResults();
                updateSummary();
            }
            
            const duration = ((Date.now() - startTime) / 1000).toFixed(2);
            document.getElementById('duration').textContent = duration + 's';
            
            const passed = testResults.filter(r => r?.status === 'pass').length;
            const failed = testResults.filter(r => r?.status === 'fail').length;
            const skipped = testResults.filter(r => r?.status === 'skip').length;
            
            if (failed === 0 && skipped === 0) {
                updateStatus(`All ${passed} tests passed!`, 'success');
                log(`\n✓ All ${passed} tests passed in ${duration}s`, 'success');
            } else if (failed === 0) {
                updateStatus(`${passed} passed, ${skipped} skipped`, 'success');
                log(`\n✓ ${passed} passed, ${skipped} skipped in ${duration}s`, 'success');
            } else {
                updateStatus(`${failed} failed, ${passed} passed`, 'failed');
                log(`\n✗ ${failed} failed, ${passed} passed, ${skipped} skipped in ${duration}s`, 'error');
            }
            
            btn.disabled = false;
            btn.innerHTML = '▶ Run All Tests';
        }
        
        function clearResults() {
            testResults = [];
            document.getElementById('results').innerHTML = '<p style="color:#9ca3af;">Click "Run All Tests" to start the test suite.</p>';
            document.getElementById('logOutput').innerHTML = '';
            document.getElementById('summary').style.display = 'none';
            updateStatus('Ready', '');
        }
        
        // Initial render
        renderResults();
    </script>
</body>
</html>
'''


def create_app(config_name=None):
    load_dotenv()
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])
    migrate.init_app(app, db)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(playlists_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(music_sources_bp)
    
    # Health check endpoint
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'message': 'Music Player API is running'})
    
    # Test page endpoint
    @app.route('/test')
    def test_page():
        return render_template_string(TEST_PAGE_HTML)
    
    # Root redirect to test page
    @app.route('/')
    def index():
        return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Music Player API</title>
                <style>
                    body { font-family: sans-serif; background: #1a1a2e; color: #fff; 
                           display: flex; justify-content: center; align-items: center; 
                           height: 100vh; margin: 0; }
                    .card { background: #16213e; padding: 40px; border-radius: 16px; text-align: center; }
                    h1 { color: #a855f7; }
                    a { color: #a855f7; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>🎵 Music Player API</h1>
                    <p>Server is running!</p>
                    <p><a href="/test">Open Test Suite →</a></p>
                    <p><a href="/api/health">Health Check →</a></p>
                </div>
            </body>
            </html>
        ''')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': True, 'message': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'error': True, 'message': 'Internal server error'}), 500
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': True, 'message': 'Token has expired'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': True, 'message': 'Invalid token'}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': True, 'message': 'Authorization required'}), 401
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app


# Create app instance for running directly
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
