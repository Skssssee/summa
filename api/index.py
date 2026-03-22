from flask import Flask, jsonify, request, render_template_string
import requests
import re
import json

app = Flask(__name__)

# --- 1. CONFIGURATION ---
COOKIES = {
    "B": "f7bed719990fcc9630de8f7ca53fab9e",
    "CT": "OTkzNjc5NDEw",
    "geo": "2401%3A4900%3A88a3%3Ac407%3Ad1ba%3Ac7ef%3A6fcc%3A761b%2CIN%2CBihar%2CPatna%2C800001"
}

session = requests.Session()
session.headers.update({
    "user-agent": "Mozilla/5.0 (Linux; Android 16; SM-S921E Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.7632.159 Mobile Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "referer": "https://www.jiosaavn.com/",
    "x-requested-with": "mark.via.gp"
})
session.cookies.update(COOKIES)

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
    if not t: return ""
    return t.replace("&quot;", '"').replace("&amp;", "&").replace("&#039;", "'").replace("&ndash;", "-")

def clean_artists(d):
    if not d: return "Unknown Artist"
    if isinstance(d, str): return clean_txt(d)
    names = [a.get('name') for a in d if isinstance(a, dict) and a.get('name')]
    return clean_txt(", ".join(names)) if names else "Unknown Artist"

# --- 3. THE UI ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Misofy</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --accent: #1db954; --bg: #000; }
        body { font-family: sans-serif; background: var(--bg); color: white; margin: 0; padding-bottom: 100px; overflow-x: hidden; }
        .container { padding: 15px; max-width: 800px; margin: 0 auto; }
        .logo { color: var(--accent); font-size: 2.2rem; font-weight: 800; cursor: pointer; display: inline-block; margin: 10px 0; }
        .search-box { display: flex; gap: 10px; background: #222; padding: 12px 15px; border-radius: 25px; align-items: center; margin-bottom: 20px; }
        input { flex: 1; background: transparent; border: none; color: white; outline: none; font-size: 1rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
        .card { background: #121212; padding: 10px; border-radius: 10px; text-align: center; cursor: pointer; }
        .card img { width: 100%; border-radius: 8px; aspect-ratio: 1/1; object-fit: cover; }
        .song-item { display: flex; align-items: center; padding: 12px; gap: 15px; border-bottom: 1px solid #222; cursor: pointer; }
        .song-item img { width: 50px; height: 50px; border-radius: 4px; }
        .song-info { flex: 1; overflow: hidden; }
        .song-info b { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        
        #popup { position: fixed; top: 100%; left: 0; width: 100%; height: 100%; background: linear-gradient(180deg, #333, #000); z-index: 1000; transition: 0.4s; padding: 40px 25px; box-sizing: border-box; text-align: center; }
        #popup.active { top: 0; }
        .p-img { width: 85%; border-radius: 15px; margin-top: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .prog-bg { width: 100%; height: 5px; background: #444; border-radius: 3px; margin-top: 30px; cursor: pointer; }
        #prog { height: 100%; background: #fff; width: 0%; border-radius: 3px; }
        
        .player-bar { position: fixed; bottom: 0; width: 100%; background: #080808; height: 80px; display: flex; align-items: center; padding: 0 20px; box-sizing: border-box; border-top: 1px solid #222; z-index: 100; }
        #m-img { width: 50px; height: 50px; border-radius: 4px; margin-right: 15px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo" onclick="goHome()">Misofy</div>
        <div class="search-box">
            <input id="q" placeholder="Search..." onkeypress="if(event.key=='Enter')search()">
            <i class="fas fa-search" onclick="search()"></i>
        </div>
        <div id="content" class="grid">Loading...</div>
    </div>

    <div class="player-bar" onclick="showPop(true)">
        <img id="m-img"><div class="song-info"><b id="m-name">Not Playing</b><small id="m-artist" style="color:#888"></small></div>
        <i class="fas fa-play" id="m-play" style="font-size:1.8rem" onclick="event.stopPropagation();playPause()"></i>
    </div>

    <div id="popup">
        <i class="fas fa-chevron-down" style="position:absolute; top:25px; left:25px; font-size:1.5rem" onclick="showPop(false)"></i>
        <i class="fas fa-download" style="position:absolute; top:25px; right:25px; font-size:1.5rem; color:var(--accent)" onclick="dl()"></i>
        <img id="p-img" class="p-img">
        <div style="text-align:left; margin-top:30px;"><h2 id="p-name" style="margin:0">Track</h2><p id="p-artist" style="color:#888">Artist</p></div>
        <div class="prog-bg" onclick="seek(event)"><div id="prog"></div></div>
        <div style="display:flex; justify-content:space-between; color:#888; font-size:0.8rem; margin-top:10px;"><span id="cur">0:00</span><span id="tot">0:00</span></div>
        <i class="fas fa-circle-play" id="p-play" style="font-size:4.5rem; margin-top:30px" onclick="playPause()"></i>
    </div>

    <audio id="aud" ontimeupdate="upd()"></audio>

    <script>
        let curLink = "";
        function goHome() { history.pushState(null,"","/"); load(); }
        window.onpopstate = () => { if(document.getElementById('popup').classList.contains('active')) showPop(false); else load(); };
        function load() { fetch('/api/trending').then(r=>r.json()).then(draw); }
        function search() { fetch(`/api/search?q=${document.getElementById('q').value}`).then(r=>r.json()).then(draw); }
        function draw(d) {
            let c = document.getElementById('content');
            c.className = "grid";
            c.innerHTML = d.map(i => `<div class="card" onclick="openCol('${i.token}','${i.type}')"><img src="${i.image}"><div style="margin-top:8px; font-weight:bold; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">${i.title}</div></div>`).join('');
        }
        function openCol(t, y) {
            if(y=='song') { play(t); return; }
            history.pushState({v:1},"");
            fetch(`/api/playlist?token=${t}&type=${y}`).then(r=>r.json()).then(songs => {
                let c = document.getElementById('content'); c.className = "";
                c.innerHTML = '<button onclick="goHome()" style="background:#222; color:white; border:none; padding:10px 20px; border-radius:20px; margin:10px; font-weight:bold">⬅ BACK</button>' + 
                songs.map(s => `<div class="song-item" onclick="play('${s.token}')"><img src="${s.image}"><div class="song-info"><b>${s.song}</b><small style="color:#888">${s.artist}</small></div><span style="color:#666; font-size:0.8rem">${s.duration}</span></div>`).join('');
            });
        }
        function play(t) {
            curLink = "";
            fetch(`/api/details?token=${t}`).then(r=>r.json()).then(s => {
                document.getElementById('m-name').innerText = document.getElementById('p-name').innerText = s.song;
                document.getElementById('m-artist').innerText = document.getElementById('p-artist').innerText = s.artist;
                document.getElementById('m-img').src = document.getElementById('p-img').src = s.image;
                document.getElementById('m-img').style.display = "block";
                document.getElementById('tot').innerText = s.duration;
                fetch(`/api/download?token=${t}`).then(r=>r.json()).then(d => {
                    if(!d.url) { alert("Playback failed. This song might be restricted to Pro users."); return; }
                    curLink = d.url; let a = document.getElementById('aud'); a.src = d.url; a.play();
                    document.getElementById('m-play').className = "fas fa-pause";
                    document.getElementById('p-play').className = "fas fa-circle-pause";
                });
            });
        }
        function showPop(s) { document.getElementById('popup').classList.toggle('active', s); if(s) history.pushState({v:2},""); }
        function playPause() { let a = document.getElementById('aud'); if(a.paused) a.play(); else a.pause(); let p = a.paused; document.getElementById('m-play').className = p ? "fas fa-play":"fas fa-pause"; document.getElementById('p-play').className = p ? "fas fa-circle-play":"fas fa-circle-pause"; }
        function upd() { let a = document.getElementById('aud'); if(!a.duration) return; document.getElementById('prog').style.width = (a.currentTime/a.duration*100)+"%"; document.getElementById('cur').innerText = fmt(a.currentTime); }
        function fmt(s) { let m=Math.floor(s/60), sc=Math.floor(s%60); return m+":"+(sc<10?'0':'')+sc; }
        function seek(e) { let a = document.getElementById('aud'); a.currentTime = (e.offsetX/e.currentTarget.offsetWidth)*a.duration; }
        function dl() { if(curLink) window.open(curLink, '_blank'); }
        load();
    </script>
</body>
</html>
"""

# --- 4. BACKEND ROUTES ---
@app.route('/')
def home(): 
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/trending')
def trending():
    res = session.get("https://www.jiosaavn.com/api.php?__call=webapi.getLaunchData&api_version=4&_format=json").json()
    items = []
    for sec in ['new_trending', 'charts', 'new_albums', 'top_playlists']:
        if sec in res:
            for item in res[sec]:
                items.append({
                    'title': clean_txt(item.get('title') or item.get('name')), 
                    'type': item.get('type'), 
                    'token': item.get('perma_url').split('/')[-1], 
                    'image': item.get('image','').replace('150x150','500x500')
                })
    return jsonify(items)

@app.route('/api/search')
def search():
    q = request.args.get('q')
    res = session.get(f"https://www.jiosaavn.com/api.php?__call=search.getResults&q={q}&api_version=4&_format=json").json()
    items = []
    for i in res.get('results', []):
        items.append({
            'title': clean_txt(i.get('title')), 
            'type': i.get('type'), 
            'token': i.get('perma_url').split('/')[-1], 
            'image': i.get('image','').replace('150x150','500x500')
        })
    return jsonify(items)

@app.route('/api/details')
def details():
    token = request.args.get('token')
    url = f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type=song&api_version=4&_format=json"
    res = session.get(url).json()
    song = res[0] if isinstance(res, list) else res.get('songs', [res])[0]
    
    dur = "0:00"
    try:
        s = int(find_key(song, "duration"))
        dur = f"{s // 60}:{s % 60:02d}"
    except: pass
    
    return jsonify({
        "song": clean_txt(find_key(song, "song") or find_key(song, "title")),
        "artist": clean_artists(find_key(song, "primary_artists")),
        "image": find_key(song, "image").replace('150x150','500x500'),
        "duration": dur
    })

@app.route('/api/playlist')
def playlist():
    token, ptype = request.args.get('token'), request.args.get('type')
    url = f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type={ptype}&api_version=4&_format=json"
    res = session.get(url).json()
    raw = find_key(res, "songs") or find_key(res, "list") or []
    songs = []
    for s in (raw if isinstance(raw, list) else [raw]):
        dur = "0:00"
        try:
            sec = int(s.get('duration'))
            dur = f"{sec // 60}:{sec % 60:02d}"
        except: pass
        songs.append({
            "song": clean_txt(s.get('song') or s.get('title')), 
            "artist": clean_artists(s.get('primary_artists')), 
            "image": s.get('image','').replace('150x150','500x500'), 
            "token": s.get('perma_url').split('/')[-1], 
            "duration": dur
        })
    return jsonify(songs)

@app.route('/api/download')
def download():
    token = request.args.get('token')
    res = session.get(f"https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}&type=song&api_version=4&_format=json").json()
    enc_url = find_key(res, "encrypted_media_url")
    
    if not enc_url:
        return jsonify({"url": None})

    # Generate Token
    auth_params = {"__call": "song.generateAuthToken", "url": enc_url, "bitrate": "320", "api_version": "4", "_format": "json"}
    auth_res = session.get("https://www.jiosaavn.com/api.php", params=auth_params).json()
    link = auth_res.get('auth_url')
    
    if not link:
        auth_params["bitrate"] = "128"
        auth_res = session.get("https://www.jiosaavn.com/api.php", params=auth_params).json()
        link = auth_res.get('auth_url')

    return jsonify({"url": link})

# Vercel needs the app object, it doesn't run the __main__ block
if __name__ == '__main__':
    app.run(debug=True)
