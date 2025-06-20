import firebase_admin
from firebase_admin import credentials, db
import websocket
import json

cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://your-db.firebaseio.com'
})

def stream_handler(event):
    ws = websocket.create_connection("ws://localhost:6789")
    ws.send(json.dumps(event.data))
    ws.close()

ref = db.reference("/sensor_data")
ref.listen(stream_handler)