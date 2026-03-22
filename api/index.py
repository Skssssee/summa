from flask import Flask, jsonify, request, render_template_string, session
import requests
import firebase_admin
from firebase_admin import credentials, db
import json
import os

app = Flask(__name__)
app.secret_key = "misofy_secret_key" # Change this for production

# --- 1. FIREBASE & CONFIG ---
# Initialize Firebase using your Realtime DB URL
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "project_id": "kodularlive",
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL", "")
    }) if os.getenv("FIREBASE_PRIVATE_KEY") else None
    
    # If deploying to Vercel, use the DB URL from your JSON
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://kodularlive-default-rtdb.firebaseio.com'
    })

COOKIES = {
    "B": "f7bed719990fcc9630de8f7ca53fab9e",
    "CT": "OTkzNjc5NDEw",
    "geo": "2401%3A4900%3A88a3%3Ac407%3Ad1ba%3Ac7ef%3A6fcc%3A761b%2CIN%2CBihar%2CPatna%2C800001"
}

s_node = requests.Session()
s_node.cookies.update(COOKIES)

# --- 2. HELPERS ---
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

def clean_txt(t):
    return t.replace("&quot;", '"').replace("&amp;", "&").replace("&#039;", "'").replace("&ndash;", "-") if t else ""

# --- 3. UI TEMPLATE (With Google Login & Scroll Player) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Misofy | Premium</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    <style>
        :root { --accent: #1db954; --bg: #000; --panel: #181818; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: white; margin: 0; overflow-x: hidden; }
        .container { padding: 15px; max-width: 800px; margin: 0 auto; padding-bottom: 120px; }
        
        /* Login Bar */
        .user-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; }
        #user-info { display: flex; align-items: center; gap: 10px; font-size: 0.9rem; }
        #user-info img { width: 30px; border-radius: 50%; }

        .search-box { display: flex; gap: 10px; background: #222; padding: 12px 15px; border-radius: 25px; margin: 15px 0; }
        input { flex: 1; background: transparent; border: none; color: white; outline: none; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 15px; }
        .card { background: var(--panel); padding: 12px; border-radius: 12px; transition: 0.3s; }
        .card img { width: 100%; border-radius: 8px; aspect-ratio: 1/1; object-fit: cover; }
        
        /* SCROLL PLAYER (Bottom Sheet) */
        #player-sheet { 
            position: fixed; top: calc(100% - 80px); left: 0; width: 100%; height: 100%; 
            background: linear-gradient(180deg, #222, #000); z-index: 1000; 
            transition: transform 0.4s cubic-bezier(0.33, 1, 0.68, 1); 
            border-radius: 20px 20px 0 0; box-shadow: 0 -5px 20px rgba(0,0,0,0.5);
        }
        #player-sheet.expanded { transform: translateY(calc(-100% + 80px)); }
        
        /* Mini Player Part */
        .mini-player { height: 80px; display: flex; align-items: center; padding: 0 20px; cursor: pointer; }
        .mini-player img { width: 50px; height: 50px; border-radius: 5px; margin-right: 15px; }
        
        /* Full Player Part */
        .full-content { padding: 40px 25px; text-align: center; opacity: 0; transition: 0.3s; pointer-events: none; }
        #player-sheet.expanded .full-content { opacity: 1; pointer-events: all; }
        .p-img { width: 80%; border-radius: 15px; margin: 20px 0; box-shadow: 0 10px 40px rgba(0,0,0,0.8); }
        
        .controls { display: flex; justify-content: center; align-items: center; gap: 30px; margin-top: 20px; }
        .stats { display: flex; justify-content: center; gap: 20px; margin: 15px 0; color: #888; font-size: 0.9rem; }
        .like-btn.active { color: var(--accent); }
        
        .prog-bg { width: 100%; height: 6px; background: #444; border-radius: 3px; margin: 20px 0; cursor: pointer; }
        #prog { height: 100%; background: var(--accent); width: 0%; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="user-bar">
            <div style="font-size: 1.8rem; font-weight: 800; color: var(--accent);">Misofy</div>
            <div id="user-info">
                <div id="g_id_onload"
                     data-client_id="808693598001-iom354vtrg0t7dft3055pholnrlqct7h.apps.googleusercontent.com"
                     data-callback="handleAuth">
                </div>
                <div class="g_id_signin" data-type="standard"></div>
            </div>
        </div>

        <div class="search-box">
            <input id="q" placeholder="Search Artists, Songs, Albums..." onkeypress="if(event.key=='Enter')search()">
            <i class="fas fa-search" onclick="search()"></i>
        </div>
        <div id="content" class="grid">Loading trending...</div>
    </div>

    <div id="player-sheet">
        <div class="mini-player" onclick="togglePlayer()">
            <img id="m-img" src="https://via.placeholder.com/50">
            <div style="flex:1; overflow:hidden">
                <b id="m-name" style="display:block; white-space:nowrap; text-overflow:ellipsis">Not Playing</b>
                <small id="m-artist" style="color:#888">Select a song</small>
            </div>
            <i class="fas fa-play" id="m-play" style="font-size:1.5rem" onclick="event.stopPropagation();playPause()"></i>
        </div>

        <div class="full-content">
            <i class="fas fa-chevron-down" style="font-size:1.5rem; float:left" onclick="togglePlayer()"></i>
            <div style="clear:both"></div>
            <img id="p-img" class="p-img">
            <div style="text-align:left">
                <h2 id="p-name" style="margin:0">Track Name</h2>
                <p id="p-artist" style="color:#888">Artist Name</p>
            </div>
            
            <div class="stats">
                <span><i class="fas fa-headphones"></i> <span id="v-count">0</span> views</span>
                <span onclick="toggleLike()" class="like-btn" id="l-btn"><i class="fas fa-heart"></i> Like</span>
            </div>

            <div class="prog-bg" onclick="seek(event)"><div id="prog"></div></div>
            <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#888">
                <span id="cur">0:00</span><span id="tot">0:00</span>
            </div>

            <div class="controls">
                <i class="fas fa-backward-step" style="font-size:1.8rem"></i>
                <i class="fas fa-circle-play" id="p-play" style="font-size:4rem" onclick="playPause()"></i>
                <i class="fas fa-forward-step" style="font-size:1.8rem"></i>
            </div>
            <button onclick="dl()" style="margin-top:30px; background:transparent; border:1px solid #444; color:white; padding:10px 20px; border-radius:20px"><i class="fas fa-download"></i> Download</button>
        </div>
    </div>

    <audio id="aud" ontimeupdate="upd()"></audio>

    <script>
        let curUser = null;
        let curToken = null;
        let isExpanded = false;

        // AUTH
        function handleAuth(resp) {
            const payload = JSON.parse(atob(resp.credential.split('.')[1]));
            curUser = payload.sub;
            document.getElementById('user-info').innerHTML = `<img src="${payload.picture}"> <span>${payload.given_name}</span>`;
        }

        function togglePlayer() {
            isExpanded = !isExpanded;
            document.getElementById('player-sheet').classList.toggle('expanded', isExpanded);
        }

        function load() { fetch('/api/trending').then(r=>r.json()).then(draw); }
        function search() { fetch(`/api/search?q=${document.getElementById('q').value}`).then(r=>r.json()).then(draw); }
        
        function draw(d) {
            document.getElementById('content').innerHTML = d.map(i => `
                <div class="card" onclick="openCol('${i.token}','${i.type}')">
                    <img src="${i.image}">
                    <div style="margin-top:8px; font-weight:bold; font-size:0.9rem; overflow:hidden; white-space:nowrap; text-overflow:ellipsis">${i.title}</div>
                </div>
            `).join('');
        }

        function openCol(t, y) {
            if(y=='song') { play(t); return; }
            fetch(`/api/playlist?token=${t}&type=${y}`).then(r=>r.json()).then(songs => {
                document.getElementById('content').innerHTML = songs.map(s => `
                    <div style="display:flex; align-items:center; gap:15px; padding:10px; border-bottom:1px solid #222" onclick="play('${s.token}')">
                        <img src="${s.image}" style="width:40px; border-radius:4px">
                        <div style="flex:1"><b>${s.song}</b><br><small style="color:#888">${s.artist}</small></div>
                    </div>
                `).join('');
            });
        }

        function play(t) {
            curToken = t;
            fetch(`/api/details?token=${t}`).then(r=>r.json()).then(s => {
                document.getElementById('m-name').innerText = document.getElementById('p-name').innerText = s.song;
                document.getElementById('m-artist').innerText = document.getElementById('p-artist').innerText = s.artist;
                document.getElementById('m-img').src = document.getElementById('p-img').src = s.image;
                document.getElementById('tot').innerText = s.duration;
                
                // Fetch Stats
                fetch(`/api/stats?token=${t}&uid=${curUser||'anon'}`).then(r=>r.json()).then(st => {
                    document.getElementById('v-count').innerText = st.views;
                    document.getElementById('l-btn').classList.toggle('active', st.liked);
                });

                fetch(`/api/download?token=${t}`).then(r=>r.json()).then(d => {
                    if(!d.url) return alert("Song unavailable");
                    let a = document.getElementById('aud'); a.src = d.url; a.play();
                    document.getElementById('m-play').className = "fas fa-pause";
                    document.getElementById('p-play').className = "fas fa-circle-pause";
                });
            });
        }

        function toggleLike() {
            if(!curUser) return alert("Please login to like songs");
            fetch(`/api/like?token=${curToken}&uid=${curUser}`).then(r=>r.json()).then(res => {
                document.getElementById('l-btn').classList.toggle('active', res.status == 'liked');
            });
        }

        function playPause() {
            let a = document.getElementById('aud');
            if(a.paused) a.play(); else a.pause();
            let p = a.paused;
            document.getElementById('m-play').className = p ? "fas fa-play" : "fas fa-pause";
            document.getElementById('p-play').className = p ? "fas fa-circle-play" : "fas fa-circle-pause";
        }

        function upd() {
            let a = document.getElementById('aud');
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

# --- 4. BACKEND LOGIC ---

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def get_stats():
    token = request.args.get('token')
    uid = request.args.get('uid')
    ref = db.reference(f'stats/{token}')
    data = ref.get() or {"views": 0, "likes": {}}
    
    # Increment views on load
    new_views = data.get('views', 0) + 1
    ref.update({"views": new_views})
    
    liked = False
    if uid != 'anon' and 'likes' in data:
        liked = uid in data['likes']
        
    return jsonify({"views": new_views, "liked": liked})

@app.route('/api/like')
def toggle_like():
    token = request.args.get('token')
    uid = request.args.get('uid')
    ref = db.reference(f'stats/{token}/likes/{uid}')
    if ref.get():
        ref.delete()
        return jsonify({"status": "unliked"})
    else:
        ref.set(True)
        return jsonify({"status": "liked"})

@app.route('/api/trending')
def trending():
    res = s_node.get("https://www.jiosaavn.com/api.php?__call=webapi.getLaunchData&api_version=4&_format=json").json()
    items = []
    for sec in ['new_trending', 'charts', 'new_albums']:
        if sec in res:
            for i in res[sec]:
                items.append({'title': clean_txt(i.get('title') or i.get('name')), 'type': i.get('type'), 'token': i.get('perma_url').split('/')[-1], 'image': i.get('image','').replace('150x150','500x500')})
    return jsonify(items)

# Add your existing /api/search, /api/details, /api/playlist, /api/download here from the previous code...
# (The logic remains the same as your CLI)

if __name__ == '__main__':
    app.run(debug=True)
    
