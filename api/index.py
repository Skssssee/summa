from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for
import requests
import firebase_admin
from firebase_admin import credentials, db
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_KEY", "misofy_premium_ultra_secret")

# --- 1. FIREBASE CONFIG ---
if not firebase_admin._apps:
    fb_cred = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if fb_cred:
        cred = credentials.Certificate(json.loads(fb_cred))
        firebase_admin.initialize_app(cred, {'databaseURL': 'https://kodularlive-default-rtdb.firebaseio.com'})
    else:
        # Fallback for local Pydroid testing
        firebase_admin.initialize_app(options={'databaseURL': 'https://kodularlive-default-rtdb.firebaseio.com'})

# JioSaavn Session
s_node = requests.Session()
s_node.cookies.update({
    "B": "f7bed719990fcc9630de8f7ca53fab9e",
    "CT": "OTkzNjc5NDEw",
    "geo": "2401%3A4900%3A88a3%3Ac407%3Ad1ba%3Ac7ef%3A6fcc%3A761b%2CIN%2CBihar%2CPatna%2C800001"
})

# --- 2. HELPERS ---
def encode_email(email):
    # Firebase keys cannot contain dots. We replace '.' with ','
    return email.replace('.', ',')

def clean_txt(t):
    return t.replace("&quot;", '"').replace("&amp;", "&").replace("&#039;", "'").replace("&ndash;", "-") if t else ""

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

# --- 3. UI TEMPLATE (Email Version) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Misofy | Email Login</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --accent: #1db954; --bg: #000; --panel: #121212; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: white; margin: 0; overflow-x: hidden; }
        .container { padding: 15px; max-width: 800px; margin: 0 auto; padding-bottom: 120px; }
        
        /* Auth Screen */
        .auth-overlay { position: fixed; inset: 0; background: #000; z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .auth-card { background: var(--panel); padding: 35px; border-radius: 25px; width: 100%; max-width: 400px; text-align: center; }
        input { width: 100%; padding: 15px; margin: 10px 0; border-radius: 12px; border: 1px solid #333; background: #1a1a1a; color: white; box-sizing: border-box; }
        .btn { background: var(--accent); color: black; border: none; padding: 15px; border-radius: 30px; font-weight: 800; cursor: pointer; width: 100%; margin-top: 15px; font-size: 1rem; }
        .btn-alt { background: transparent; color: #888; border: none; margin-top: 20px; cursor: pointer; font-size: 0.9rem; }
        
        /* Search & Nav */
        .nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }
        .search-bar { display: flex; background: #222; padding: 12px 20px; border-radius: 30px; align-items: center; gap: 12px; }
        .search-bar input { margin: 0; padding: 0; border: none; background: transparent; }

        /* Grid */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 15px; margin-top: 20px; }
        .card { background: var(--panel); padding: 12px; border-radius: 15px; cursor: pointer; }
        .card img { width: 100%; border-radius: 10px; aspect-ratio: 1/1; object-fit: cover; }
        
        /* SLIDING PLAYER */
        #player-sheet { 
            position: fixed; bottom: 0; left: 0; width: 100%; height: 88vh; 
            background: linear-gradient(180deg, #1f1f1f 0%, #000 100%); 
            z-index: 1000; transition: transform 0.4s cubic-bezier(0.3, 1, 0.5, 1);
            transform: translateY(calc(100% - 80px)); border-radius: 30px 30px 0 0;
            box-shadow: 0 -10px 40px rgba(0,0,0,0.8);
        }
        #player-sheet.expanded { transform: translateY(0); }
        
        .mini-p { height: 80px; display: flex; align-items: center; padding: 0 25px; cursor: pointer; }
        .mini-p img { width: 45px; height: 45px; border-radius: 5px; margin-right: 15px; }
        
        .full-p { padding: 40px 30px; text-align: center; display: none; }
        #player-sheet.expanded .full-p { display: block; }
        #player-sheet.expanded .mini-p { display: none; }
        
        .p-art { width: 80%; border-radius: 20px; margin: 20px auto; box-shadow: 0 10px 40px rgba(0,0,0,0.6); display: block; }
        .prog-bg { width: 100%; height: 5px; background: #444; border-radius: 3px; margin: 30px 0 10px 0; cursor: pointer; }
        #prog { height: 100%; background: var(--accent); width: 0%; border-radius: 3px; }
        
        .controls { display: flex; justify-content: center; align-items: center; gap: 40px; margin-top: 40px; }
        .active-heart { color: var(--accent); }
        .hidden { display: none; }
    </style>
</head>
<body>
    {% if not session.user %}
    <div class="auth-overlay">
        <div class="auth-card" id="login-form">
            <h1 style="color:var(--accent)">Misofy</h1>
            <p style="color:#888">Listen with your email</p>
            <input type="email" id="l-email" placeholder="Email Address">
            <input type="password" id="l-pass" placeholder="Password">
            <button class="btn" onclick="auth('login')">Login</button>
            <button class="btn-alt" onclick="toggleAuth(true)">Don't have an account? Sign Up</button>
        </div>
        <div class="auth-card hidden" id="reg-form">
            <h1 style="color:var(--accent)">Register</h1>
            <p style="color:#888">Join the community</p>
            <input type="email" id="r-email" placeholder="Enter Email">
            <input type="password" id="r-pass" placeholder="Create Password">
            <button class="btn" onclick="auth('register')">Create Account</button>
            <button class="btn-alt" onclick="toggleAuth(false)">Already have an account? Login</button>
        </div>
    </div>
    {% endif %}

    <div class="container">
        <div class="nav">
            <div style="font-size: 1.8rem; font-weight: 900; color: var(--accent);">Misofy</div>
            {% if session.user %}
            <div style="font-size: 0.8rem; color:#888">
                {{ session.user }} | <a href="/logout" style="color:var(--accent); text-decoration:none">Logout</a>
            </div>
            {% endif %}
        </div>

        <div class="search-bar">
            <i class="fas fa-search" style="color:#666"></i>
            <input id="q" placeholder="Search songs..." onkeypress="if(event.key=='Enter')search()">
        </div>

        <div id="content" class="grid">Loading trending...</div>
    </div>

    <div id="player-sheet" onclick="if(!this.classList.contains('expanded')) togglePlayer(true)">
        <div class="mini-p">
            <img id="m-img" src="https://via.placeholder.com/50">
            <div style="flex:1; overflow:hidden">
                <b id="m-name" style="white-space:nowrap; display:block; overflow:hidden; text-overflow:ellipsis">Not Playing</b>
                <small id="m-artist" style="color:#888">Tap to open</small>
            </div>
            <i class="fas fa-play" id="m-play" style="font-size:1.5rem" onclick="event.stopPropagation(); playPause()"></i>
        </div>

        <div class="full-p">
            <i class="fas fa-chevron-down" style="float:left; font-size:1.5rem" onclick="togglePlayer(false)"></i>
            <div style="clear:both"></div>
            <img id="p-img" class="p-art">
            <div style="text-align:left; margin-top:25px">
                <h2 id="p-name" style="margin:0; font-size:1.6rem">Song Name</h2>
                <p id="p-artist" style="color:#888; font-size:1.1rem">Artist</p>
            </div>

            <div style="display:flex; justify-content:space-between; color:#888; font-size:0.9rem; margin-top:20px">
                <span><i class="fas fa-headphones"></i> <span id="v-count">0</span> views</span>
                <span id="like-btn" onclick="toggleLike()"><i class="fas fa-heart"></i> Like</span>
            </div>

            <div class="prog-bg" onclick="seek(event)"><div id="prog"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#666">
                <span id="cur">0:00</span><span id="tot">0:00</span>
            </div>

            <div class="controls">
                <i class="fas fa-backward-step" style="font-size:1.8rem"></i>
                <i class="fas fa-circle-play" id="p-play" style="font-size:4.5rem" onclick="playPause()"></i>
                <i class="fas fa-forward-step" style="font-size:1.8rem"></i>
            </div>
        </div>
    </div>

    <audio id="aud" ontimeupdate="upd()"></audio>

    <script>
        let curToken = null;
        function toggleAuth(reg) {
            document.getElementById('login-form').classList.toggle('hidden', reg);
            document.getElementById('reg-form').classList.toggle('hidden', !reg);
        }
        async function auth(type) {
            const email = document.getElementById(type=='login'?'l-email':'r-email').value;
            const pass = document.getElementById(type=='login'?'l-pass':'r-pass').value;
            const res = await fetch(`/api/auth/${type}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, pass})
            });
            const data = await res.json();
            if(data.success) location.reload(); else alert(data.error);
        }
        function togglePlayer(ex) { document.getElementById('player-sheet').classList.toggle('expanded', ex); }
        function load() { fetch('/api/trending').then(r=>r.json()).then(draw); }
        function search() { fetch(`/api/search?q=${document.getElementById('q').value}`).then(r=>r.json()).then(draw); }
        function draw(d) {
            document.getElementById('content').innerHTML = d.map(i => `
                <div class="card" onclick="play('${i.token}')">
                    <img src="${i.image}">
                    <div style="margin-top:10px; font-weight:bold; font-size:0.85rem; overflow:hidden; white-space:nowrap; text-overflow:ellipsis">${i.title}</div>
                </div>
            `).join('');
        }
        function play(t) {
            curToken = t;
            fetch(`/api/details?token=${t}`).then(r=>r.json()).then(s => {
                document.getElementById('m-name').innerText = document.getElementById('p-name').innerText = s.song;
                document.getElementById('m-artist').innerText = document.getElementById('p-artist').innerText = s.artist;
                document.getElementById('m-img').src = document.getElementById('p-img').src = s.image;
                document.getElementById('tot').innerText = s.duration;
                fetch(`/api/stats?token=${t}`).then(r=>r.json()).then(st => {
                    document.getElementById('v-count').innerText = st.views;
                    document.getElementById('like-btn').className = st.liked ? 'active-heart' : '';
                });
                fetch(`/api/download?token=${t}`).then(r=>r.json()).then(d => {
                    if(!d.url) return;
                    let a = document.getElementById('aud'); a.src = d.url; a.play();
                    document.getElementById('m-play').className = "fas fa-pause";
                    document.getElementById('p-play').className = "fas fa-circle-pause";
                });
            });
        }
        function toggleLike() {
            fetch(`/api/like?token=${curToken}`).then(r=>r.json()).then(res => {
                document.getElementById('like-btn').className = res.status == 'liked' ? 'active-heart' : '';
            });
        }
        function playPause() {
            let a = document.getElementById('aud');
            if(a.paused) a.play(); else a.pause();
            document.getElementById('m-play').className = a.paused ? "fas fa-play" : "fas fa-pause";
            document.getElementById('p-play').className = a.paused ? "fas fa-circle-play" : "fas fa-circle-pause";
        }
        function upd() {
            let a = document.getElementById('aud');
            if(!a.duration) return;
            document.getElementById('prog').style.width = (a.currentTime/a.duration*100)+"%";
            document.getElementById('cur').innerText = fmt(a.currentTime);
        }
        function fmt(s) { let m=Math.floor(s/60), sc=Math.floor(s%60); return m+":"+(sc<10?'0':'')+sc; }
        function seek(e) { let a = document.getElementById('aud'); a.currentTime = (e.offsetX/e.currentTarget.offsetWidth)*a.duration; }
        load();
    </script>
</body>
</html>
"""

# --- 4. BACKEND AUTH (Email Logic) ---
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    email, pwd = data.get('email'), data.get('pass')
    if not email or "@" not in email: return jsonify({"error": "Valid email required"}), 400
    
    e_path = encode_email(email)
    ref = db.reference(f'users/{e_path}')
    if ref.get(): return jsonify({"error": "Account already exists"}), 400
    
    ref.set({"pass": generate_password_hash(pwd)})
    session['user'] = email
    return jsonify({"success": True})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email, pwd = data.get('email'), data.get('pass')
    e_path = encode_email(email)
    user_data = db.reference(f'users/{e_path}').get()
    
    if user_data and check_password_hash(user_data['pass'], pwd):
        session['user'] = email
        return jsonify({"success": True})
    return jsonify({"error": "Invalid email or password"}), 401

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

# --- 5. DATA ROUTES ---
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def stats():
    token = request.args.get('token')
    user = session.get('user')
    ref = db.reference(f'stats/{token}')
    data = ref.get() or {"views": 0, "likes": {}}
    
    new_views = data.get('views', 0) + 1
    ref.update({"views": new_views})
    
    liked = encode_email(user) in data.get('likes', {}) if user else False
    return jsonify({"views": new_views, "liked": liked})

@app.route('/api/like')
def like():
    user = session.get('user')
    if not user: return jsonify({"error": "Login required"}), 401
    token = request.args.get('token')
    e_user = encode_email(user)
    ref = db.reference(f'stats/{token}/likes/{e_user}')
    if ref.get():
        ref.delete()
        return jsonify({"status": "unliked"})
    ref.set(True)
    return jsonify({"status": "liked"})

# --- 6. JIOSAAVN API ---
@app.route('/api/trending')
def trending():
    res = s_node.get("https://www.jiosaavn.com/api.php?__call=webapi.getLaunchData&api_version=4&_format=json").json()
    items = []
    for sec in ['new_trending', 'charts', 'new_albums']:
        if sec in res:
            for i in res[sec]:
                items.append({'title': clean_txt(i.get('title') or i.get('name')), 'type': i.get('type'), 'token': i.get('perma_url').split('/')[-1], 'image': i.get('image','').replace('150x150','500x500')})
    return jsonify(items)

@app.route('/api/search')
def search():
    q = request.args.get('q')
    res = s_node.get(f"https://www.jiosaavn.com/api.php?__call=search.getResults&q={q}&api_version=4&_format=json").json()
    items = []
    for i in res.get('results', []):
        items.append({'title': clean_txt(i.get('title')), 'type': i.get('type'), 'token': i.get('perma_url').split('/')[-1], 'image': i.get('image','').replace('150x150','500x500')})
    return jsonify(items)

@app.route('/api/details')
def details():
    token = request.args.get('token')
    res = s_node.get(f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type=song&api_version=4&_format=json").json()
    song = res[0] if isinstance(res, list) else res.get('songs', [res])[0]
    dur = int(find_key(song, "duration") or 0)
    return jsonify({"song": clean_txt(find_key(song, "song") or find_key(song, "title")), "artist": clean_txt(find_key(song, "primary_artists")), "image": find_key(song, "image").replace('150x150','500x500'), "duration": f"{dur // 60}:{dur % 60:02d}"})

@app.route('/api/download')
def download():
    token = request.args.get('token')
    res = s_node.get(f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type=song&api_version=4&_format=json").json()
    enc_url = find_key(res, "encrypted_media_url")
    auth_params = {"__call": "song.generateAuthToken", "url": enc_url, "bitrate": "128", "api_version": "4", "_format": "json"}
    auth_res = s_node.get("https://www.jiosaavn.com/api.php", params=auth_params).json()
    return jsonify({"url": auth_res.get('auth_url')})

if __name__ == '__main__':
    app.run(debug=True)
                    
