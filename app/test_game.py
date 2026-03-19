import socketio
import time
import sys

# Instantiate two clients
sio1 = socketio.Client()
sio2 = socketio.Client()

# Shared state
state = {
    'room_code': None,
    'host_joined': False,
    'guest_joined': False,
    'host_game_started': False,
    'guest_game_started': False,
    'host_saw_number': False,
    'guest_saw_number': False,
    'host_turn': False
}

@sio1.on('room_created')
def on_room_created(data):
    state['room_code'] = data['room_code']
    print(f"Host: Room created {data['room_code']}")

@sio1.on('game_started')
def on_host_game_started(data):
    state['host_game_started'] = True
    state['host_turn'] = (data['turn'] == sio1.sid)
    print(f"Host: Game started. My turn? {state['host_turn']}")

@sio1.on('number_selected')
def on_host_number_selected(data):
    if data['number'] == 1:
        state['host_saw_number'] = True
        print("Host: Saw number 1 selected")

@sio2.on('room_joined')
def on_room_joined(data):
    state['guest_joined'] = True
    print(f"Guest: Joined room {data['room_code']}")

@sio2.on('game_started')
def on_guest_game_started(data):
    state['guest_game_started'] = True
    print(f"Guest: Game started")

@sio2.on('number_selected')
def on_guest_number_selected(data):
    if data['number'] == 1:
        state['guest_saw_number'] = True
        print("Guest: Saw number 1 selected")

def run_test(grid_size=5):
    # Reset state
    for key in state: state[key] = False if isinstance(state[key], bool) else None
    
    try:
        sio1.connect('http://localhost:5000')
        sio1.emit('create_room', {'username': 'Alice'})
        
        # Wait for room code
        for _ in range(10):
            if state['room_code']: break
            time.sleep(0.5)
        
        if not state['room_code']: return False
            
        sio2.connect('http://localhost:5000')
        sio2.emit('join_room', {'room_code': state['room_code'], 'username': 'Bob'})
        
        # Wait for guest to join
        for _ in range(10):
            if state['guest_joined']: break
            time.sleep(0.5)
            
        if not state['guest_joined']: return False
        
        print(f"--- Testing Grid Size: {grid_size}x{grid_size} ---")
        sio1.emit('start_game', {'room_code': state['room_code'], 'grid_size': grid_size})
        
        # Wait for game to start for both
        for _ in range(10):
            if state['host_game_started'] and state['guest_game_started']: break
            time.sleep(0.5)
            
        if not (state['host_game_started'] and state['guest_game_started']):
            print(f"Sync Issue: HostStart={state['host_game_started']}, GuestStart={state['guest_game_started']}")
            return False
            
        # Select number 1
        if state['host_turn']:
            sio1.emit('select_number', {'room_code': state['room_code'], 'number': 1})
        else:
            sio2.emit('select_number', {'room_code': state['room_code'], 'number': 1})
            
        # Wait for selection sync
        for _ in range(10):
            if state['host_saw_number'] and state['guest_saw_number']: break
            time.sleep(0.5)
            
        if state['host_saw_number'] and state['guest_saw_number']:
            print(f"SUCCESS: {grid_size}x{grid_size} verified.")
            return True
        else:
            print(f"FAILURE: Sync results - HostSaw={state['host_saw_number']}, GuestSaw={state['guest_saw_number']}")
            return False

    except Exception as e:
        import traceback
        print(f"Error during test: {e}")
        traceback.print_exc()
        return False
    finally:
        if sio1.connected: sio1.disconnect()
        if sio2.connected: sio2.disconnect()

if __name__ == '__main__':
    for size in [4, 5, 8, 10]:
        if not run_test(size):
            sys.exit(1)
        time.sleep(1)
    print("\nALL GRID SIZES VERIFIED SUCCESSFULLY!")
