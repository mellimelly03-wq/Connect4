const boardDiv = document.getElementById("board");
const scoresRowDiv = document.getElementById("scoresRow");
const info = document.getElementById("info");

let gameStarted = false;
let lastScores = [];
let currentMode = null;
let isAITurn = false;
let aiInterval = null;

function drawBoard(grid, scores = null, winning_cells = []) {
    if (scores !== null) lastScores = scores;
    const displayScores = lastScores;

    // Taille cellule selon viewport
    const cellSize = window.innerWidth <= 600 ? 38 : 52;
    const gap = 6;
    const gridWidth = COLS * cellSize + (COLS - 1) * gap;

    boardDiv.style.gridTemplateColumns = `repeat(${COLS}, ${cellSize}px)`;
    boardDiv.innerHTML = "";

    // Winning cells set
    const winSet = new Set((winning_cells || []).map(([r,c]) => r * COLS + c));

    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            const cell = document.createElement("div");
            cell.classList.add("cell");

            const idx = r * COLS + c;

            if (grid[r][c] === 1) {
                cell.classList.add("red");
                if (winSet.has(idx)) cell.classList.add("winning");
            } else if (grid[r][c] === 2) {
                cell.classList.add("yellow");
                if (winSet.has(idx)) cell.classList.add("winning");
            }

            cell.onclick = () => playMove(c);
            boardDiv.appendChild(cell);
        }
    }

    // Scores minimax
    scoresRowDiv.innerHTML = "";
    if (displayScores && displayScores.length > 0) {
        scoresRowDiv.style.gridTemplateColumns = `repeat(${COLS}, ${cellSize}px)`;

        for (let c = 0; c < COLS; c++) {
            const scoreCell = document.createElement("div");
            scoreCell.classList.add("score-cell");

            const found = displayScores.find(s => s[0] === c);
            if (found) {
                scoreCell.innerText = found[1];
                if (found[1] > 0) scoreCell.classList.add("score-pos");
                else if (found[1] < 0) scoreCell.classList.add("score-neg");
                else scoreCell.classList.add("score-zero");
            }
            scoresRowDiv.appendChild(scoreCell);
        }
    }
}

function setInfo(msg, color = null) {
    info.innerText = msg;
    info.style.color = color || "var(--text)";
}

function startGame() {
    const mode = document.getElementById("mode").value;
    const ai_type = document.getElementById("ai_type").value;
    const depth = document.getElementById("depth").value;
    const starting = document.getElementById("starting").value;

    if (mode === "") { alert("Choisis un mode !"); return; }

    currentMode = mode;
    stopAIVsAI();

    fetch("/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode, ai_type, depth, starting})
    })
    .then(res => res.json())
    .then(data => {
        gameStarted = true;
        lastScores = [];
        drawBoard(data.grid);
        setInfo("SYSTÈME ACTIF — BONNE CHANCE", "var(--neon-green)");

        if (currentMode === "ai_vs_ai") launchAIVsAI();
    });
}

function playMove(col) {
    if (!gameStarted || isAITurn) return;
    if (currentMode === "ai_vs_ai") return;

    fetch("/move", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({col})
    })
    .then(res => res.json())
    .then(data => {
        if (data.error === "full") { setInfo("COLONNE PLEINE !", "var(--neon-pink)"); return; }
        if (data.error) return;

        drawBoard(data.grid, data.scores, data.winning_cells || []);

        if (data.winner) {
            const who = data.winner === 1 ? "ROUGE" : "JAUNE";
            const col = data.winner === 1 ? "var(--player-red)" : "var(--player-yellow)";
            setInfo(`⬤ VICTOIRE — JOUEUR ${who} !`, col);
            setTimeout(() => alert(`Victoire joueur ${who} !`), 100);
        } else if (data.draw) {
            setInfo("MATCH NUL — ÉGALITÉ PARFAITE", "var(--neon-blue)");
            setTimeout(() => alert("Match nul !"), 100);
        } else {
            const next = data.grid ? "TOUR SUIVANT" : "";
            setInfo("EN ATTENTE DU PROCHAIN COUP...");
        }
    });
}

function aiMove() {
    if (!gameStarted) return;
    isAITurn = true;
    setInfo("IA EN CALCUL...", "var(--neon-blue)");

    fetch("/ai_move", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        isAITurn = false;

        if (data.error) { stopAIVsAI(); return; }

        drawBoard(data.grid, data.scores || [], data.winning_cells || []);

        if (data.winner) {
            stopAIVsAI();
            const who = data.winner === 1 ? "ROUGE" : "JAUNE";
            const col = data.winner === 1 ? "var(--player-red)" : "var(--player-yellow)";
            setInfo(`⬤ VICTOIRE — JOUEUR ${who} !`, col);
            setTimeout(() => alert(`Victoire joueur ${who} !`), 100);
        } else if (data.draw) {
            stopAIVsAI();
            setInfo("MATCH NUL — ÉGALITÉ PARFAITE", "var(--neon-blue)");
            setTimeout(() => alert("Match nul !"), 100);
        } else {
            setInfo("SYSTÈME ACTIF — EN COURS...", "var(--neon-green)");
        }
    });
}

function launchAIVsAI() {
    stopAIVsAI();
    aiInterval = setInterval(() => { if (!isAITurn) aiMove(); }, 900);
}

function stopAIVsAI() {
    if (aiInterval) clearInterval(aiInterval);
    aiInterval = null;
    isAITurn = false;
}

function aiSuggestion() {
    setInfo("ANALYSE EN COURS...", "var(--neon-blue)");
    fetch("/ai_suggest", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        setInfo(`IA SUGGÈRE COLONNE : ${data.col}`, "var(--neon-yellow)");
        alert("IA suggère colonne : " + data.col);
    });
}

function undo() {
    fetch("/undo", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        lastScores = [];
        drawBoard(data.grid);
        setInfo("COUP ANNULÉ");
    });
}

function restart() {
    stopAIVsAI();
    fetch("/restart", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        lastScores = [];
        drawBoard(data.grid);
        setInfo("SYSTÈME RÉINITIALISÉ", "var(--neon-green)");
        if (currentMode === "ai_vs_ai") launchAIVsAI();
    });
}

function saveGame() {
    fetch("/save", { method: "POST" })
    .then(res => res.json())
    .then(() => {
        setInfo("PARTIE SAUVEGARDÉE ✓", "var(--neon-green)");
        alert("Sauvegarde OK");
    });
}

function pauseGame() {
    stopAIVsAI();
    fetch("/pause", { method: "POST" })
    .then(() => setInfo("SYSTÈME EN PAUSE", "var(--neon-yellow)"));
}

function resumeGame() {
    fetch("/resume", { method: "POST" })
    .then(() => {
        setInfo("SYSTÈME ACTIF", "var(--neon-green)");
        if (currentMode === "ai_vs_ai") launchAIVsAI();
    });
}

drawBoard(INITIAL_GRID);