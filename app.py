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
            // Health Check
            {
                group: 'Health',
                name: 'Health Check',
                run: async () => {
                    const r = await api('GET', '/health', null, false);
                    if (!r.ok) throw new Error('Health check failed');
                    return r.data;
                }
            },
            
            // Auth Tests
            {
                group: 'Authentication',
                name: 'Register New User',
                run: async () => {
                    testUser = {
                        email: `test_${Date.now()}@example.com`,
                        password: 'test123456',
                        username: 'TestUser'
                    };
                    const r = await api('POST', '/auth/register', testUser, false);
                    if (!r.ok) throw new Error(r.data.message || 'Registration failed');
                    accessToken = r.data.access_token;
                    refreshToken = r.data.refresh_token;
                    return { userId: r.data.user.id, email: r.data.user.email };
                }
            },
            {
                group: 'Authentication',
                name: 'Login',
                run: async () => {
                    const r = await api('POST', '/auth/login', {
                        email: testUser.email,
                        password: testUser.password
                    }, false);
                    if (!r.ok) throw new Error(r.data.message || 'Login failed');
                    accessToken = r.data.access_token;
                    return { success: true };
                }
            },
            {
                group: 'Authentication',
                name: 'Get Profile',
                run: async () => {
                    const r = await api('GET', '/auth/me');
                    if (!r.ok) throw new Error(r.data.message || 'Get profile failed');
                    return r.data;
                }
            },
            {
                group: 'Authentication',
                name: 'Refresh Token',
                run: async () => {
                    const headers = {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + refreshToken
                    };
                    const resp = await fetch(API_BASE + '/auth/refresh', { method: 'POST', headers });
                    const data = await resp.json();
                    if (!resp.ok) throw new Error(data.message || 'Refresh failed');
                    accessToken = data.access_token;
                    return { newTokenReceived: true };
                }
            },
            
            // Playlist Tests
            {
                group: 'Playlists',
                name: 'Create Playlist',
                run: async () => {
                    const r = await api('POST', '/playlists', {
                        name: 'Test Playlist',
                        description: 'Created by automated test'
                    });
                    if (!r.ok) throw new Error(r.data.message || 'Create playlist failed');
                    testPlaylistId = r.data.id;
                    return { playlistId: testPlaylistId };
                }
            },
            {
                group: 'Playlists',
                name: 'Get All Playlists',
                run: async () => {
                    const r = await api('GET', '/playlists');
                    if (!r.ok) throw new Error(r.data.message || 'Get playlists failed');
                    return { count: r.data.length };
                }
            },
            {
                group: 'Playlists',
                name: 'Get Single Playlist',
                run: async () => {
                    const r = await api('GET', '/playlists/' + testPlaylistId);
                    if (!r.ok) throw new Error(r.data.message || 'Get playlist failed');
                    return { name: r.data.name };
                }
            },
            {
                group: 'Playlists',
                name: 'Add Song to Playlist',
                run: async () => {
                    const r = await api('POST', `/playlists/${testPlaylistId}/songs`, {
                        id: 1001,
                        title: 'Test Song',
                        artist: 'Test Artist',
                        album: 'Test Album',
                        path: '/music/test.mp3',
                        duration: 180000
                    });
                    if (!r.ok) throw new Error(r.data.message || 'Add song failed');
                    return { success: true };
                }
            },
            {
                group: 'Playlists',
                name: 'Update Playlist',
                run: async () => {
                    const r = await api('PUT', '/playlists/' + testPlaylistId, {
                        name: 'Updated Test Playlist'
                    });
                    if (!r.ok) throw new Error(r.data.message || 'Update playlist failed');
                    return { newName: r.data.name };
                }
            },
            {
                group: 'Playlists',
                name: 'Remove Song from Playlist',
                run: async () => {
                    const r = await api('DELETE', `/playlists/${testPlaylistId}/songs/1001`);
                    if (!r.ok) throw new Error(r.data.message || 'Remove song failed');
                    return { success: true };
                }
            },
            
            // Favorites Tests
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
                        duration: 200000
                    });
                    if (!r.ok) throw new Error(r.data.message || 'Add favorite failed');
                    return { success: true };
                }
            },
            {
                group: 'Favorites',
                name: 'Get All Favorites',
                run: async () => {
                    const r = await api('GET', '/favorites');
                    if (!r.ok) throw new Error(r.data.message || 'Get favorites failed');
                    return { count: r.data.length };
                }
            },
            {
                group: 'Favorites',
                name: 'Check Favorite Status',
                run: async () => {
                    const r = await api('GET', '/favorites/2001/check');
                    if (!r.ok) throw new Error(r.data.message || 'Check favorite failed');
                    return { isFavorite: r.data.is_favorite };
                }
            },
            {
                group: 'Favorites',
                name: 'Remove from Favorites',
                run: async () => {
                    const r = await api('DELETE', '/favorites/2001');
                    if (!r.ok) throw new Error(r.data.message || 'Remove favorite failed');
                    return { success: true };
                }
            },
            
            // History Tests
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
                        duration: 250000
                    });
                    if (!r.ok) throw new Error(r.data.message || 'Add history failed');
                    return { success: true };
                }
            },
            {
                group: 'History',
                name: 'Get Play History',
                run: async () => {
                    const r = await api('GET', '/history');
                    if (!r.ok) throw new Error(r.data.message || 'Get history failed');
                    return { count: r.data.length };
                }
            },
            {
                group: 'History',
                name: 'Clear History',
                run: async () => {
                    const r = await api('DELETE', '/history');
                    if (!r.ok) throw new Error(r.data.message || 'Clear history failed');
                    return { success: true };
                }
            },
            
            // Cleanup
            {
                group: 'Cleanup',
                name: 'Delete Test Playlist',
                run: async () => {
                    const r = await api('DELETE', '/playlists/' + testPlaylistId);
                    if (!r.ok) throw new Error(r.data.message || 'Delete playlist failed');
                    return { success: true };
                }
            }
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
                const total = groupTests.length;
                
                html += `<div class="test-group">
                    <div class="test-group-header">
                        <span>${groupName}</span>
                        <span>${passed}/${total}</span>
                    </div>`;
                    
                for (const test of groupTests) {
                    const r = test.result || { status: 'pending' };
                    const badge = r.status === 'pass' ? 'pass' : 
                                  r.status === 'fail' ? 'fail' :
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
            
            document.getElementById('summary').style.display = 'flex';
            document.getElementById('totalTests').textContent = tests.length;
            document.getElementById('passedTests').textContent = passed;
            document.getElementById('failedTests').textContent = failed;
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
                    testResults[i] = { 
                        status: 'fail', 
                        details: err.message 
                    };
                    log(`✗ FAIL: ${test.name} - ${err.message}`, 'error');
                }
                
                renderResults();
                updateSummary();
            }
            
            const duration = ((Date.now() - startTime) / 1000).toFixed(2);
            document.getElementById('duration').textContent = duration + 's';
            
            const passed = testResults.filter(r => r?.status === 'pass').length;
            const failed = testResults.filter(r => r?.status === 'fail').length;
            
            if (failed === 0) {
                updateStatus(`All ${passed} tests passed!`, 'success');
                log(`\\n✓ All ${passed} tests passed in ${duration}s`, 'success');
            } else {
                updateStatus(`${failed} test(s) failed`, 'failed');
                log(`\\n✗ ${failed} test(s) failed, ${passed} passed in ${duration}s`, 'error');
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
