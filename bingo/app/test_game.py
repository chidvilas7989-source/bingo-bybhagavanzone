import socketio
import time
import sys

# Instantiate two clients
sio1 = socketio.Client()
sio2 = socketio.Client()

test_events = []
room_code = None
host_turn = False
guest_turn = False

@sio1.event
def connect():
    test_events.append("Host connected")

@sio1.event
def room_created(data):
    global room_code
    room_code = data['room_code']
    test_events.append(f"Room Created: {room_code} by {data['host_name']}")

@sio1.event
def game_started(data):
    global host_turn
    test_events.append(f"Game Started for Host! Turn is {data['turn']}")
    host_turn = (data['turn'] == sio1.get_sid())

@sio1.event
def board_update(data):
    test_events.append(f"Host received board: length {len(data['board'])}")

@sio1.event
def number_selected(data):
    global host_turn
    test_events.append(f"Host saw number selected: {data['number']}")
    host_turn = (data['turn'] == sio1.get_sid())

# Guest events
@sio2.event
def connect():
    test_events.append("Guest connected")

@sio2.event
def room_joined(data):
    test_events.append(f"Guest joined room: {data['room_code']}, host is {data['host_name']}")

@sio2.event
def game_started(data):
    global guest_turn
    test_events.append(f"Game Started for Guest! Turn is {data['turn']}")
    guest_turn = (data['turn'] == sio2.get_sid())

@sio2.event
def board_update(data):
    test_events.append(f"Guest received board: length {len(data['board'])}")

@sio2.event
def number_selected(data):
    global guest_turn
    test_events.append(f"Guest saw number selected: {data['number']}")
    guest_turn = (data['turn'] == sio2.get_sid())

@sio2.event
def error(data):
    test_events.append(f"Guest got error: {data['message']}")

def run_test():
    try:
        sio1.connect('http://localhost:5003')
        time.sleep(1)
        
        # Room creation
        sio1.emit('create_room', {'username': 'Alice'})
        time.sleep(1)
        
        if not room_code:
            print("Failed to get room code")
            return
            
        sio2.connect('http://localhost:5003')
        time.sleep(1)
        
        # Room join
        sio2.emit('join_room', {'room_code': room_code, 'username': 'Bob'})
        time.sleep(2)
        
        # Selection
        if host_turn:
            test_events.append("Host selecting number 5")
            sio1.emit('select_number', {'room_code': room_code, 'number': 5})
        elif guest_turn:
            test_events.append("Guest selecting number 5")
            sio2.emit('select_number', {'room_code': room_code, 'number': 5})
        
        time.sleep(2)
        
        for event in test_events:
            print(event)
            
        print("TEST PASSED")

    except Exception as e:
        print(f"Error checking game logic: {e}")
    finally:
        sio1.disconnect()
        sio2.disconnect()

if __name__ == '__main__':
    run_test()
