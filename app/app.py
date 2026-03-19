import random
import string
import os
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
# Secret key for sessions/cookies
app.config['SECRET_KEY'] = 's3cr3t_k3y_b1ng0'

# Use 'threading' mode for compatibility with Python 3.14 on Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# In-memory storage for rooms
rooms = {}

def generate_board(size=5):
    """Generates a shuffled 1 to (size*size) bingo board."""
    board = list(range(1, (size * size) + 1))
    random.shuffle(board)
    return board

def generate_room_code():
    """Generates a random 6-character room code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@app.route('/')
def index():
    return render_template('index.html')

# ===== SOCKET.IO EVENTS =====

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Cleanup room if host or guest leaves
    for room_code, room_data in dict(rooms).items():
        if room_data['host'] == request.sid or room_data['guest'] == request.sid:
            emit('player_left', {'message': 'The other player has disconnected.'}, room=room_code)
            # Remove room from memory (optional logic depending on how strict you want to be)
            # del rooms[room_code]

@socketio.on('create_room')
def on_create_room(data):
    room_code = generate_room_code()
    username = data.get('username', 'Host').strip()
    if not username:
        username = 'Host'
    
    grid_size = 5 # Default on creation
    
    rooms[room_code] = {
        'host': request.sid,
        'host_name': username,
        'guest': None,
        'guest_name': None,
        'status': 'lobby',
        'turn': request.sid,
        'grid_size': 5, # Default, will be set at start
        'board1': None,
        'board2': None,
        'selected_numbers': []
    }
    join_room(room_code)
    emit('room_created', {
        'room_code': room_code,
        'player_type': 'host',
        'host_name': username
    })
    print(f"Room {room_code} created by {request.sid} ({username})")

@socketio.on('join_room')
def on_join_room(data):
    room_code = data.get('room_code', '').upper()
    username = data.get('username', 'Guest').strip()
    if not username:
        username = 'Guest'

    if room_code in rooms:
        room = rooms[room_code]
        if room['status'] == 'lobby' and room['guest'] is None:
            room['guest'] = request.sid
            room['guest_name'] = username
            # Join room but stay in lobby status
            join_room(room_code)
            
            # Broadcast to everyone in the room that guest joined
            emit('room_joined', {
                'room_code': room_code,
                'player_type': 'guest',
                'host_name': room['host_name'],
                'guest_name': room['guest_name']
            })
            
            # Tell host to show "Start Game" button
            emit('guest_joined_lobby', {
                'guest_name': room['guest_name']
            }, to=room['host'])

            print(f"{request.sid} ({username}) joined room {room_code}")
        else:
            emit('error', {'message': 'Room is full or already playing.'})
    else:
        emit('error', {'message': 'Invalid room code.'})

@socketio.on('start_game')
def on_start_game(data):
    room_code = data.get('room_code')
    grid_size = int(data.get('grid_size', 5))
    
    if room_code in rooms:
        room = rooms[room_code]
        if room['host'] == request.sid and room['guest']:
            room['status'] = 'playing'
            room['grid_size'] = grid_size
            room['board1'] = generate_board(grid_size)
            room['board2'] = generate_board(grid_size)
            room['selected_numbers'] = []
            
            emit('game_started', {
                'turn': room['turn'],
                'host_name': room['host_name'],
                'guest_name': room['guest_name'],
                'grid_size': grid_size
            }, room=room_code)
            
            emit('board_update', {'board': room['board1'], 'selected_numbers': room['selected_numbers']}, to=room['host'])
            emit('board_update', {'board': room['board2'], 'selected_numbers': room['selected_numbers']}, to=room['guest'])

@socketio.on('update_grid_size')
def on_update_grid_size(data):
    room_code = data.get('room_code')
    grid_size = int(data.get('grid_size', 5))
    if room_code in rooms:
        room = rooms[room_code]
        if room['host'] == request.sid:
            room['grid_size'] = grid_size
            emit('grid_size_updated', {'grid_size': grid_size}, room=room_code)

@socketio.on('select_number')
def on_select_number(data):
    room_code = data.get('room_code')
    number = int(data.get('number'))
    
    if room_code in rooms:
        room = rooms[room_code]
        
        # Check if it's currently this user's turn
        if room['turn'] == request.sid:
            # Check if number is not already selected
            if number not in room['selected_numbers']:
                room['selected_numbers'].append(number)
                
                # Toggle turn
                if room['turn'] == room['host']:
                    room['turn'] = room['guest']
                else:
                    room['turn'] = room['host']
                
                # Broadcast the number selected and the new turn
                emit('number_selected', {
                    'number': number,
                    'turn': room['turn']
                }, room=room_code)
        else:
            emit('error', {'message': 'Not your turn!'})

@socketio.on('player_won')
def on_player_won(data):
    room_code = data.get('room_code')
    winner_name = data.get('winner_name')
    if room_code in rooms:
        emit('game_over', {'winner_name': winner_name}, room=room_code)

@socketio.on('play_again')
def on_play_again(data):
    room_code = data.get('room_code')
    if room_code in rooms:
        room = rooms[room_code]
        if 'play_again' not in room:
            room['play_again'] = 0
        room['play_again'] += 1
        
        if room['play_again'] >= 2:
            room['play_again'] = 0
            # Reset to lobby status to allow host to select grid size again if desired
            room['status'] = 'lobby'
            room['selected_numbers'] = []
            room['board1'] = None
            room['board2'] = None
            
            emit('reset_to_lobby', {
                'room_code': room_code,
                'host_name': room['host_name'],
                'guest_name': room['guest_name']
            }, room=room_code)

if __name__ == '__main__':
    def open_browser():
        # Open two tabs for easy 2-player testing
        webbrowser.open('http://127.0.0.1:5000')
        Timer(0.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()

    # Only open browser in the main process, not the reloader child
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        Timer(1.25, open_browser).start()

    # Check if we are on Render (which defines PORT) or running locally
    port = int(os.environ.get("PORT", 5000))
    # allow_unsafe_werkzeug=True is needed for newer Flask/Werkzeug versions in production
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
