'''
Spotify playlist exporter. 
CONTROL FLOW:
/ > /login > /callback > /connected
'''

from flask import (
	Flask, 
	render_template,   
	request, 
	url_for, 
	flash, 
	redirect,
	make_response,
	session,
	abort, 
	send_file, 
)
from spotify_exporter import build_playlist
import string 
import secrets
import requests
from urllib.parse import urlencode
import os 						 

CLI_ID 	= os.getenv('CLI_ID') # CLIENT ID 
CLI_KEY = os.getenv('CLI_KEY') # CLIENT SECRET 
REDIRECT_URI = "http://127.0.0.1:5000/callback"
AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'

app = Flask(__name__)
app.secret_key = 'selectARandomsecret_Key-forTheAPP'


@app.route("/")
def home():
	return render_template("home.html") 


@app.route("/export", methods={"POST"})
def export():
	# get form inputs
	form_data = request.form.to_dict(flat=False)
	user = form_data['name'][0]
	playlist_url = form_data['url'][0]
	# get playlist data 
	uri_len = 22
	start = playlist_url.find("playlist")
	mid = len("playlist/")
	end = start + mid
	playlist_uri = playlist_url[end:end+uri_len] 

	# create tsv file
	filename = build_playlist(user, playlist_uri, token=session.get('tokens').get('access_token'))

	if filename == "error":
		return render_template("home.html", value="reauthorize")

	# prepare file export
	file_export = send_file(filename, as_attachment=True)
	# remove file from path as its no longer needed
	os.remove(f"./{filename}")
	# download file export
	return file_export


@app.route("/login")
def login():
	state = ''.join(
		secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16)
	)
	scope = "playlist-read-private"
	payload = {
		'client_id': CLI_ID,
		'response_type': 'code',
		'redirect_uri': REDIRECT_URI,
		'state': state,
		'scope': scope
	}
	res = make_response(redirect(f'{AUTH_URL}/?{urlencode(payload)}'))
	res.set_cookie('spotify_auth_state', state, samesite="Strict")
	print("cookie set")
	return res


@app.route("/callback")
def callback():
	print("Callback")
	error = request.args.get('error') # Test (it's in orig code)
	stored_state = request.cookies.get('spotify_auth_state') # Test
	code = request.args.get('code')
	state = request.args.get('state') or None

	# check state 
	if state is None:
		print("State is None, attempting to render_template home.html...")
		return render_template("home.html", value="error")
	
	# request token's payload 
	payload = {
		'grant_type': 'authorization_code',
		'code': code,
		'redirect_uri': REDIRECT_URI,
	}
	res = requests.post(TOKEN_URL, auth=(CLI_ID, CLI_KEY), data=payload)
	res_data = res.json()
	print(res_data)

	if res_data.get('error') or res.status_code != 200:
		app.logger.error(
			'Failed to get tokens {}'.format(
				res_data.get('error', 'No error information received.'),
			)
		)
		abort(res.status_code)
	
	session['tokens'] = {
		'access_token': res_data.get('access_token'),
		'refresh_token': res_data.get('refresh_token'),
	}
	session.modified = True 

	return redirect(url_for('connected'))


@app.route('/refresh')
def refresh():
	tokens = session.get('tokens') or None
	print("refresh")
	if tokens is None:
		return render_template("home.html", value="reauthorize")

	payload = {
		'grant_type': 'refresh_token',
		'refresh_token': tokens.get('refresh_token'),
	}
	headers = {'Content-Type': 'application/x-www-form-urlencoded'}

	res = requests.post(
		TOKEN_URL, auth=(CLI_ID, CLI_KEY), data=payload, headers=headers
	)
	res_data = res.json()
	# load new tokens into session
	session['tokens']['access_token'] = res_data.get('access_token')
	print("connected, redirecting..")
	return redirect(url_for('connected'))


@app.route('/connected')
def connected():
	print("connected")
	token = session.get('tokens').get('access_token')
	if token:
		return render_template("home_connected.html") 
	else:
		return render_template("home.html")


if __name__ == "__main__":
	app.run(debug=True)