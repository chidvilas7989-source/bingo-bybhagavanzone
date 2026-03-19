const socket = io();

// State
let currentRoomCode = null;
let myName = "";
let currentTurn = null; // socket ID
let myPlayerType = null; // 'host' or 'guest'
let myBoard = [];
let selectedNumbers = [];
let currentGridSize = 5;
let winningLines = [];

// DOM Elements
const screenWelcome = document.getElementById('screenWelcome');
const screenLobby = document.getElementById('screenLobby');
const screenGame = document.getElementById('screenGame');

const btnCreate = document.getElementById('btn-create-room');
const btnJoin = document.getElementById('btn-join-room');
const inputCode = document.getElementById('joinCode');
const createName = document.getElementById('createName');
const joinName = document.getElementById('joinName');

const headerMeta = document.getElementById('headerMeta');
const hRoomCode = document.getElementById('hRoomCode');
const lobbyRoomCode = document.getElementById('display-room-code');
const lobbyPlayers = document.getElementById('lobbyPlayers');
const bingoGrid = document.getElementById('bingo-grid');
const turnIndicator = document.getElementById('turn-indicator');
const gameOverModal = document.getElementById('gameOverModal');
const winnerText = document.getElementById('winner-text');

const letters = ['B', 'I', 'N', 'G', 'O'];

const COLORS = ['#7c3aed', '#ec4899', '#f97316', '#22c55e', '#38bdf8', '#a855f7', '#fb923c'];
function avatarColor(name) { return COLORS[(name||"A").charCodeAt(0) % COLORS.length]; }
function avatarLetter(name) { return (name||"A").charAt(0).toUpperCase(); }

// ==================== NOTIFICATIONS ====================
function notify(type, msg, icon = '') {
    const c = document.getElementById('notifContainer');
    const el = document.createElement('div');
    el.className = `notif ${type}`;
    el.innerHTML = `<span>${icon || { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' }[type]}</span><div><div>${msg}</div><div class="notif-progress"></div></div>`;
    c.prepend(el);
    setTimeout(() => el.remove(), 4200);
}

// SCREEN ROUTING
function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

// Socket connection
socket.on('connect', () => {
    console.log("Connected to server:", socket.id);
});

// Create Room
btnCreate.addEventListener('click', () => {
    const name = createName.value.trim();
    if(!name) { notify('error', 'Please enter your name.'); return; }
    myName = name;
    socket.emit('create_room', { username: name });
});

// Join Room
btnJoin.addEventListener('click', () => {
    const code = inputCode.value.trim().toUpperCase();
    const name = joinName.value.trim();
    if(!name) { notify('error', 'Please enter your name.'); return; }
    myName = name;
    if (code.length === 6) {
        socket.emit('join_room', { room_code: code, username: name });
    } else {
        notify('error', 'Please enter a valid 6-digit code.');
    }
});

// Add enter key support
inputCode.addEventListener('keypress', (e) => {
    if(e.key === 'Enter') { btnJoin.click(); }
});

// Server Responses
socket.on('room_created', (data) => {
    currentRoomCode = data.room_code;
    myPlayerType = data.player_type;
    
    showScreen('screenLobby');
    hRoomCode.textContent = currentRoomCode;
    headerMeta.classList.remove('hidden');
    lobbyRoomCode.textContent = currentRoomCode;
    
    // Add me to list
    renderPlayersList([{username: data.host_name, isHost: true}]);
    // The grid info in lobby will be updated when the host selects or game starts
    document.getElementById('display-grid-size').textContent = `5x5 (Default)`;
    notify('success', 'Room Created!');
});

socket.on('room_joined', (data) => {
    currentRoomCode = data.room_code;
    myPlayerType = data.player_type;
    
    showScreen('screenLobby');
    hRoomCode.textContent = currentRoomCode;
    headerMeta.classList.remove('hidden');
    lobbyRoomCode.textContent = currentRoomCode;
    
    // Update player list (Wait for host_name and guest_name)
    renderPlayersList([
        {username: data.host_name, isHost: true},
        {username: data.guest_name, isHost: false}
    ]);
    document.getElementById('display-grid-size').textContent = `${currentGridSize}x${currentGridSize}`;
    notify('success', 'Joined Room!');
});

socket.on('guest_joined_lobby', (data) => {
    notify('info', `${data.guest_name} has joined the lobby!`);
    if (myPlayerType === 'host') {
        document.getElementById('lobby-status-text').textContent = "Select grid and start game";
        document.getElementById('hostControls').classList.remove('hidden');
    } else {
        document.getElementById('lobby-status-text').textContent = "Host is selecting grid...";
    }
});

socket.on('error', (data) => {
    notify('error', data.message);
});

function renderPlayersList(players) {
    lobbyPlayers.innerHTML = '';
    players.forEach(p => {
        const div = document.createElement('div');
        div.className = 'player-item' + (p.isHost ? ' is-host' : '');
        div.innerHTML = `
        <div class="player-avatar" style="background:${avatarColor(p.username)}">${avatarLetter(p.username)}</div>
        <span class="player-name-text">${p.username}</span>
        ${p.isHost ? '<span class="pip pip-host">👑 HOST</span>' : ''}
        `;
        lobbyPlayers.appendChild(div);
    });
}

// Game Started
socket.on('game_started', (data) => {
    currentTurn = data.turn;
    
    renderPlayersList([
        {username: data.host_name, isHost: true},
        {username: data.guest_name, isHost: false}
    ]);

    showScreen('screenGame');
    updateTurnIndicator(data);
    
    // Hide host controls if they were visible
    document.getElementById('hostControls').classList.add('hidden');

    // Update local grid size if it changed
    if (data.grid_size) {
        currentGridSize = data.grid_size;
        winningLines = generateWinningLines(currentGridSize);
    }

    // Hide modals if restarting
    gameOverModal.classList.remove('open');
    const leaveModal = document.getElementById('leaveGameModal');
    if(leaveModal) leaveModal.classList.remove('open');
    
    notify('info', 'Game started!');
});

// Receive initial board
socket.on('board_update', (data) => {
    myBoard = data.board;
    selectedNumbers = data.selected_numbers;
    currentGridSize = Math.sqrt(myBoard.length);
    winningLines = generateWinningLines(currentGridSize);
    renderBoard();
    checkWinCondition();
});

// Receive number selection from server
socket.on('number_selected', (data) => {
    const number = data.number;
    currentTurn = data.turn;
    selectedNumbers.push(number);
    
    // Visually Select Cell
    const cell = document.getElementById(`cell-${number}`);
    if (cell) {
        cell.classList.add('selected');
        renderCellStates(); 
    }
    
    updateTurnIndicator({host_name: "Player 1", guest_name: "Player 2"}); // Just trigger update, generic text used
    checkWinCondition();
});

// Opponent Left
socket.on('player_left', (data) => {
    notify('warning', data.message);
    setTimeout(() => { location.reload(); }, 2000);
});

// Game Over handled by server
socket.on('game_over', (data) => {
    triggerGameOver(data.winner_name);
});

socket.on('reset_to_lobby', (data) => {
    showScreen('screenLobby');
    gameOverModal.classList.remove('open');
    notify('info', 'Host is selecting a new grid size...');
    // Clear board in UI
    bingoGrid.innerHTML = '';
    
    // Show start button for host
    if (myPlayerType === 'host') {
        document.getElementById('lobby-status-text').textContent = "Select grid and start game";
        document.getElementById('hostControls').classList.remove('hidden');
    } else {
        document.getElementById('lobby-status-text').textContent = "Host is selecting grid...";
    }
});

// Start Game (Host only)
document.getElementById('btn-start-game').addEventListener('click', () => {
    // Read grid size from the selector in the lobby
    const gridSize = document.getElementById('gridSize').value;
    socket.emit('start_game', { room_code: currentRoomCode, grid_size: gridSize });
});

// Sync Grid Size selection (Host only)
document.getElementById('gridSize').addEventListener('change', (e) => {
    if (myPlayerType === 'host') {
        const gridSize = e.target.value;
        socket.emit('update_grid_size', { room_code: currentRoomCode, grid_size: gridSize });
    }
});

socket.on('grid_size_updated', (data) => {
    currentGridSize = parseInt(data.grid_size);
    document.getElementById('display-grid-size').textContent = `${currentGridSize}x${currentGridSize}`;
});

// --- RENDER FUNCTIONS ---
function renderBoard() {
    bingoGrid.innerHTML = '';
    bingoGrid.style.gridTemplateColumns = `repeat(${currentGridSize}, 1fr)`;
    
    // Adjust font size for larger grids
    let fontSize = '1.4rem';
    if (currentGridSize >= 8) fontSize = '1rem';
    if (currentGridSize >= 10) fontSize = '0.8rem';

    myBoard.forEach((num, index) => {
        const cell = document.createElement('div');
        cell.className = 'bingo-cell';
        cell.id = `cell-${num}`;
        cell.textContent = num;
        cell.style.fontSize = fontSize;
        
        if (selectedNumbers.includes(num)) {
            cell.classList.add('selected');
        }
        
        cell.addEventListener('click', () => { handleCellClick(num); });
        
        bingoGrid.appendChild(cell);
    });
    
    renderCellStates();
}

function renderCellStates() {
    const cells = document.querySelectorAll('.bingo-cell:not(.selected)');
    cells.forEach(cell => {
        if (currentTurn === socket.id) {
            cell.classList.remove('disabled');
        } else {
            cell.classList.add('disabled');
        }
    });
}

function updateTurnIndicator(namesData) {
    turnIndicator.className = "turn-banner"; // reset
    if (currentTurn === socket.id) {
        turnIndicator.textContent = "Your Turn to draw!";
        turnIndicator.classList.add("my-turn");
    } else {
        turnIndicator.textContent = "Opponent is drawing...";
        turnIndicator.classList.add("opponent-turn");
    }
}

function handleCellClick(num) {
    if (currentTurn !== socket.id) return;
    if (selectedNumbers.includes(num)) return;
    
    socket.emit('select_number', {
        room_code: currentRoomCode,
        number: num
    });
}

// Dynamic Win Logic
function generateWinningLines(size) {
    const lines = [];
    // Rows
    for (let r = 0; r < size; r++) {
        const row = [];
        for (let c = 0; c < size; c++) row.push(r * size + c);
        lines.push(row);
    }
    // Cols
    for (let c = 0; c < size; c++) {
        const col = [];
        for (let r = 0; r < size; r++) col.push(r * size + c);
        lines.push(col);
    }
    // Diagonals
    const diag1 = [];
    const diag2 = [];
    for (let i = 0; i < size; i++) {
        diag1.push(i * size + i);
        diag2.push(i * size + (size - 1 - i));
    }
    lines.push(diag1);
    lines.push(diag2);
    return lines;
}

function checkWinCondition() {
    let completedLines = 0;
    
    const selectedStatus = myBoard.map(num => selectedNumbers.includes(num));
    
    for (const line of winningLines) {
        if (line.every(index => selectedStatus[index])) {
            completedLines++;
        }
    }
    
    updateBingoWord(completedLines);
    
    if (completedLines >= 5) {
        socket.emit('player_won', { room_code: currentRoomCode, winner_name: myName });
    }
}

function updateBingoWord(lines) {
    for (let i = 0; i < 5; i++) {
        const span = document.getElementById(`letter-${letters[i]}`);
        if (i < lines) {
            span.classList.add('active');
        } else {
            span.classList.remove('active');
        }
    }
}

function triggerGameOver(winnerName) {
    gameOverModal.classList.add('open');
    if (winnerName === myName) {
        winnerText.textContent = "You are the winner!";
        winnerText.style.color = "var(--primary-light)";
    } else {
        winnerText.textContent = `${winnerName} has won the game!`;
        winnerText.style.color = "var(--error)";
    }
}

function requestPlayAgain() {
    socket.emit('play_again', { room_code: currentRoomCode });
    document.getElementById('gameOverModal').classList.remove('open');
    notify('info', 'Waiting for other player to play again...');
}

function confirmLeave() {
    document.getElementById('gameOverModal').classList.remove('open');
    document.getElementById('leaveGameModal').classList.add('open');
}

function cancelLeave() {
    document.getElementById('leaveGameModal').classList.remove('open');
    document.getElementById('gameOverModal').classList.add('open');
}
