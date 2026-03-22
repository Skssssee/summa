from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for
import requests
import firebase_admin
from firebase_admin import credentials, db
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_KEY", "misofy_pro_99")

# --- 1. FIREBASE CONFIG ---
if not firebase_admin._apps:
    fb_cred = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if fb_cred:
        cred = credentials.Certificate(json.loads(fb_cred))
        firebase_admin.initialize_app(cred, {'databaseURL': 'https://kodularlive-default-rtdb.firebaseio.com'})
    else:
        # Pydroid local fallback
        firebase_admin.initialize_app(options={'databaseURL': 'https://kodularlive-default-rtdb.firebaseio.com'})

s_node = requests.Session()
s_node.cookies.update({
    "B": "f7bed719990fcc9630de8f7ca53fab9e",
    "CT": "OTkzNjc5NDEw",
    "geo": "2401%3A4900%3A88a3%3Ac407%3Ad1ba%3Ac7ef%3A6fcc%3A761b%2CIN%2CBihar%2CPatna%2C800001"
})

def encode_email(email): return email.replace('.', ',')
def clean_txt(t): return t.replace("&quot;", '"').replace("&amp;", "&").replace("&#039;", "'").replace("&ndash;", "-") if t else ""
def find_key(data, key):
    if isinstance(data, dict):
        if key in data: return data[key]
        for v in data.values():
            res = find_key(v, key)
            if res: return res
    elif isinstance(data, list):
        for item in data:
            res = find_key(item, key)
            if res: return res
    return None

# --- 2. THE UI (FIXED CSS & CLICK LOGIC) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Misofy | Pro Player</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --accent: #1db954; --bg: #000; --card: #181818; --input: #282828; }
        body { font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: white; margin: 0; padding: 0; overflow-x: hidden; }
        
        /* Auth Overlay - Fixed Layering */
        .auth-screen { position: fixed; inset: 0; background: #000; z-index: 9999; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .auth-card { background: var(--card); padding: 30px; border-radius: 15px; width: 100%; max-width: 360px; text-align: center; border: 1px solid #333; }
        .auth-card h1 { color: var(--accent); margin-bottom: 5px; }
        .auth-card input { width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: 1px solid #444; background: var(--input); color: white; box-sizing: border-box; font-size: 16px; }
        .main-btn { background: var(--accent); color: black; border: none; padding: 14px; border-radius: 30px; font-weight: bold; width: 100%; cursor: pointer; margin-top: 10px; font-size: 16px; transition: 0.2s; }
        .main-btn:active { transform: scale(0.98); }
        .link-btn { background: none; border: none; color: #b3b3b3; margin-top: 20px; cursor: pointer; text-decoration: underline; font-size: 14px; }

        /* Main App */
        .container { padding: 15px; max-width: 800px; margin: 0 auto; padding-bottom: 150px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .search-box { display: flex; background: var(--input); padding: 12px 15px; border-radius: 25px; align-items: center; gap: 10px; margin-bottom: 20px; }
        .search-box input { flex: 1; background: none; border: none; color: white; outline: none; font-size: 16px; }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 15px; }
        .card { background: var(--card); padding: 12px; border-radius: 10px; cursor: pointer; }
        .card img { width: 100%; border-radius: 8px; aspect-ratio: 1/1; object-fit: cover; }
        .card-title { margin-top: 10px; font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        /* SCROLL PLAYER - FIXED DRAG-UP */
        #player-sheet { 
            position: fixed; bottom: 0; left: 0; width: 100%; height: 85vh; 
            background: linear-gradient(180deg, #222 0%, #000 100%); 
            z-index: 1000; transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1);
            transform: translateY(calc(100% - 80px)); border-radius: 20px 20px 0 0;
            box-shadow: 0 -10px 30px rgba(0,0,0,0.5);
        }
        #player-sheet.expanded { transform: translateY(0); }
        
        .mini-player { height: 80px; display: flex; align-items: center; padding: 0 20px; cursor: pointer; }
        .mini-player img { width: 45px; height: 45px; border-radius: 5px; margin-right: 15px; }
        
        .full-player { padding: 40px 25px; text-align: center; visibility: hidden; opacity: 0; transition: 0.3s; }
        #player-sheet.expanded .full-player { visibility: visible; opacity: 1; }
        #player-sheet.expanded .mini-player { display: none; }
        
        .p-img { width: 80%; max-width: 300px; border-radius: 15px; margin: 0 auto 20px; display: block; box-shadow: 0 10px 40px rgba(0,0,0,0.8); }
        .prog-container { width: 100%; height: 5px; background: #444; border-radius: 3px; margin: 30px 0 10px; cursor: pointer; }
        #prog-bar { height: 100%; background: var(--accent); width: 0%; border-radius: 3px; }
        
        .stats { display: flex; justify-content: space-between; color: #b3b3b3; font-size: 14px; margin-bottom: 20px; }
        .controls { display: flex; justify-content: center; align-items: center; gap: 40px; }
        .hidden { display: none !important; }
        .active-like { color: var(--accent) !important; }
    </style>
</head>
<body>

    {% if not session.user %}
    <div class="auth-screen">
        <div class="auth-card" id="login-box">
            <h1>Misofy</h1>
            <p>Login with your email</p>
            <input type="email" id="l-email" placeholder="Email">
            <input type="password" id="l-pass" placeholder="Password">
            <button class="main-btn" onclick="authAction('login')">Login</button>
            <button class="link-btn" onclick="toggleView(true)">New account? Register</button>
        </div>
        <div class="auth-card hidden" id="reg-box">
            <h1>Register</h1>
            <p>Join for free</p>
            <input type="email" id="r-email" placeholder="Email">
            <input type="password" id="r-pass" placeholder="Create Password">
            <button class="main-btn" onclick="authAction('register')">Register</button>
            <button class="link-btn" onclick="toggleView(false)">Have account? Login</button>
        </div>
    </div>
    {% endif %}

    <div class="container">
        <div class="header">
            <h2 style="color:var(--accent); margin:0">Misofy</h2>
            {% if session.user %}<small>{{ session.user }} | <a href="/logout" style="color:#888">Exit</a></small>{% endif %}
        </div>

        <div class="search-box">
            <i class="fas fa-search" style="color:#888"></i>
            <input type="text" id="q" placeholder="Search music..." onkeypress="if(event.key=='Enter')search()">
        </div>

        <div id="content-grid" class="grid">Loading trending...</div>
    </div>

    <div id="player-sheet">
        <div class="mini-player" onclick="toggleSheet(true)">
            <img id="m-img" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=">
            <div style="flex:1; overflow:hidden">
                <b id="m-name" style="display:block; white-space:nowrap; text-overflow:ellipsis">Not Playing</b>
                <small id="m-artist" style="color:#888">Pick a song</small>
            </div>
            <i class="fas fa-play" id="m-play" style="font-size:24px" onclick="event.stopPropagation(); playPause()"></i>
        </div>

        <div class="full-player">
            <i class="fas fa-chevron-down" style="font-size:24px; float:left" onclick="toggleSheet(false)"></i>
            <div style="clear:both"></div>
            <img id="p-img" class="p-img">
            <div style="text-align:left">
                <h2 id="p-name" style="margin:0">Song Title</h2>
                <p id="p-artist" style="color:#b3b3b3; margin:5px 0 20px">Artist Name</p>
            </div>

            <div class="stats">
                <span><i class="fas fa-headphones"></i> <span id="view-count">0</span> plays</span>
                <span id="like-btn" onclick="toggleLike()"><i class="fas fa-heart"></i> Like</span>
            </div>

            <div class="prog-container" onclick="seek(event)"><div id="prog-bar"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:12px; color:#888">
                <span id="cur-time">0:00</span><span id="tot-time">0:00</span>
            </div>

            <div class="controls">
                <i class="fas fa-backward-step" style="font-size:28px"></i>
                <i class="fas fa-circle-play" id="p-play" style="font-size:70px" onclick="playPause()"></i>
                <i class="fas fa-forward-step" style="font-size:28px"></i>
            </div>
        </div>
    </div>

    <audio id="main-audio" ontimeupdate="onUpdate()"></audio>

    <script>
        let currentToken = null;

        function toggleView(showReg) {
            document.getElementById('login-box').classList.toggle('hidden', showReg);
            document.getElementById('reg-box').classList.toggle('hidden', !showReg);
        }

        async function authAction(type) {
            const email = document.getElementById(type === 'login' ? 'l-email' : 'r-email').value;
            const pass = document.getElementById(type === 'login' ? 'l-pass' : 'r-pass').value;
            const res = await fetch(`/api/auth/${type}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, pass})
            });
            const data = await res.json();
            if(data.success) location.reload(); else alert(data.error);
        }

        function toggleSheet(expand) {
            document.getElementById('player-sheet').classList.toggle('expanded', expand);
        }

        async function search() {
            const q = document.getElementById('q').value;
            const res = await fetch(`/api/search?q=${q}`);
            const data = await res.json();
            draw(data);
        }

        function draw(items) {
            document.getElementById('content-grid').innerHTML = items.map(i => `
                <div class="card" onclick="playSong('${i.token}')">
                    <img src="${i.image}">
                    <div class="card-title">${i.title}</div>
                </div>
            `).join('');
        }

        async function playSong(t) {
            currentToken = t;
            const res = await fetch(`/api/details?token=${t}`);
            const s = await res.json();
            
            document.getElementById('m-name').innerText = document.getElementById('p-name').innerText = s.song;
            document.getElementById('m-artist').innerText = document.getElementById('p-artist').innerText = s.artist;
            document.getElementById('m-img').src = document.getElementById('p-img').src = s.image;
            document.getElementById('tot-time').innerText = s.duration;

            fetch(`/api/stats?token=${t}`).then(r=>r.json()).then(st => {
                document.getElementById('view-count').innerText = st.views;
                document.getElementById('like-btn').className = st.liked ? 'active-like' : '';
            });

            const dl = await fetch(`/api/download?token=${t}`).then(r=>r.json());
            if(dl.url) {
                const a = document.getElementById('main-audio');
                a.src = dl.url;
                a.play();
                updateIcons(false);
            }
        }

        function toggleLike() {
            fetch(`/api/like?token=${currentToken}`).then(r=>r.json()).then(res => {
                document.getElementById('like-btn').className = res.status === 'liked' ? 'active-like' : '';
            });
        }

        function playPause() {
            const a = document.getElementById('main-audio');
            if(a.paused) a.play(); else a.pause();
            updateIcons(a.paused);
        }

        function updateIcons(isPaused) {
            document.getElementById('m-play').className = isPaused ? "fas fa-play" : "fas fa-pause";
            document.getElementById('p-play').className = isPaused ? "fas fa-circle-play" : "fas fa-circle-pause";
        }

        function onUpdate() {
            const a = document.getElementById('main-audio');
            if(!a.duration) return;
            document.getElementById('prog-bar').style.width = (a.currentTime / a.duration * 100) + "%";
            document.getElementById('cur-time').innerText = fmt(a.currentTime);
        }

        function fmt(s) {
            let m = Math.floor(s/60), sc = Math.floor(s%60);
            return m + ":" + (sc < 10 ? '0' : '') + sc;
        }

        function seek(e) {
            const a = document.getElementById('main-audio');
            a.currentTime = (e.offsetX / e.currentTarget.offsetWidth) * a.duration;
        }

        fetch('/api/trending').then(r=>r.json()).then(draw);
    </script>
</body>
</html>
"""

# --- 3. ENDPOINTS ---

@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/auth/register', methods=['POST'])
def register():
    d = request.json
    email, pwd = d.get('email'), d.get('pass')
    if not email or "@" not in email: return jsonify({"error": "Invalid Email"}), 400
    e_path = encode_email(email)
    ref = db.reference(f'users/{e_path}')
    if ref.get(): return jsonify({"error": "Already exists"}), 400
    ref.set({"pass": generate_password_hash(pwd)})
    session['user'] = email
    return jsonify({"success": True})

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.json
    email, pwd = d.get('email'), d.get('pass')
    e_path = encode_email(email)
    udata = db.reference(f'users/{e_path}').get()
    if udata and check_password_hash(udata['pass'], pwd):
        session['user'] = email
        return jsonify({"success": True})
    return jsonify({"error": "Wrong Email/Password"}), 401

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/api/stats')
def stats():
    token = request.args.get('token')
    user = session.get('user')
    ref = db.reference(f'stats/{token}')
    data = ref.get() or {"views": 0, "likes": {}}
    nv = data.get('views', 0) + 1
    ref.update({"views": nv})
    liked = encode_email(user) in data.get('likes', {}) if user else False
    return jsonify({"views": nv, "liked": liked})

@app.route('/api/like')
def like():
    u = session.get('user')
    if not u: return jsonify({"error": "Login required"}), 401
    t = request.args.get('token')
    ref = db.reference(f'stats/{t}/likes/{encode_email(u)}')
    if ref.get():
        ref.delete()
        return jsonify({"status": "unliked"})
    ref.set(True)
    return jsonify({"status": "liked"})

@app.route('/api/trending')
def trending():
    r = s_node.get("https://www.jiosaavn.com/api.php?__call=webapi.getLaunchData&api_version=4&_format=json").json()
    res = []
    for s in ['new_trending', 'charts']:
        if s in r:
            for i in r[s]:
                res.append({'title': clean_txt(i.get('title') or i.get('name')), 'type': i.get('type'), 'token': i.get('perma_url').split('/')[-1], 'image': i.get('image','').replace('150x150','500x500')})
    return jsonify(res)

@app.route('/api/search')
def search():
    q = request.args.get('q')
    r = s_node.get(f"https://www.jiosaavn.com/api.php?__call=search.getResults&q={q}&api_version=4&_format=json").json()
    res = []
    for i in r.get('results', []):
        res.append({'title': clean_txt(i.get('title')), 'token': i.get('perma_url').split('/')[-1], 'image': i.get('image','').replace('150x150','500x500')})
    return jsonify(res)

@app.route('/api/details')
def details():
    t = request.args.get('token')
    r = s_node.get(f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={t}&type=song&api_version=4&_format=json").json()
    s = r[0] if isinstance(r, list) else r.get('songs', [r])[0]
    dur = int(find_key(s, "duration") or 0)
    return jsonify({"song": clean_txt(find_key(s, "song")), "artist": clean_txt(find_key(s, "primary_artists")), "image": find_key(s, "image").replace('150x150','500x500'), "duration": f"{dur // 60}:{dur % 60:02d}"})

@app.route('/api/download')
def download():
    t = request.args.get('token')
    r = s_node.get(f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={t}&type=song&api_version=4&_format=json").json()
    enc = find_key(r, "encrypted_media_url")
    auth = s_node.get("https://www.jiosaavn.com/api.php", params={"__call": "song.generateAuthToken", "url": enc, "bitrate": "128", "api_version": "4", "_format": "json"}).json()
    return jsonify({"url": auth.get('auth_url')})

if __name__ == '__main__':
    app.run(debug=True)
