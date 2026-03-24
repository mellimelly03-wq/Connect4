const boardDiv = document.getElementById("board");
const scoresRowDiv = document.getElementById("scoresRow");
const info = document.getElementById("info");

let gameStarted = false;
let lastScores = [];
let currentMode = null;
let isAITurn = false;
let aiInterval = null;
let humanColor = HUMAN_COLOR; // 1=rouge, 2=jaune — injecté depuis Flask

// Mode painting
let paintMode = false;
let paintColor = 1;

// ══════════════════════════════════════════
// DESSIN DU PLATEAU
// ══════════════════════════════════════════
function drawBoard(grid, scores = null, winning_cells = []) {
    if (scores !== null) lastScores = scores;
    const displayScores = lastScores;

    const cellSize = window.innerWidth <= 600 ? 38 : 52;
    boardDiv.style.gridTemplateColumns = `repeat(${COLS}, ${cellSize}px)`;
    boardDiv.innerHTML = "";

    const winSet = new Set((winning_cells || []).map(([r,c]) => r * COLS + c));

    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            const cell = document.createElement("div");
            cell.classList.add("cell");
            cell.dataset.row = r;
            cell.dataset.col = c;

            const idx = r * COLS + c;

            if (grid[r][c] === 1) {
                cell.classList.add("red");
                if (winSet.has(idx)) cell.classList.add("winning");
            } else if (grid[r][c] === 2) {
                cell.classList.add("yellow");
                if (winSet.has(idx)) cell.classList.add("winning");
            }

            if (paintMode) {
                cell.classList.add("paint-cursor");
                cell.onclick = () => paintCell(r, c);
            } else {
                cell.onclick = () => playMove(c);
            }

            boardDiv.appendChild(cell);
        }
    }

    // Scores minimax
    scoresRowDiv.innerHTML = "";
    if (!paintMode && displayScores && displayScores.length > 0) {
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

// ══════════════════════════════════════════
// DÉMARRER UNE PARTIE
// ══════════════════════════════════════════
function startGame() {
    const mode = document.getElementById("mode").value;
    const ai_type = document.getElementById("ai_type").value;
    const depth = document.getElementById("depth").value;
    const starting = document.getElementById("starting").value;

    if (mode === "") { alert("Choisis un mode !"); return; }

    currentMode = mode;
    humanColor = parseInt(starting);
    stopAIVsAI();
    exitPaintMode();

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

// ══════════════════════════════════════════
// JOUER UN COUP
// ══════════════════════════════════════════
function playMove(col) {
    if (!gameStarted || isAITurn) return;
    if (currentMode === "ai_vs_ai") return;
    if (paintMode) return;

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
            return;
        }
        if (data.draw) {
            setInfo("MATCH NUL — ÉGALITÉ PARFAITE", "var(--neon-blue)");
            setTimeout(() => alert("Match nul !"), 100);
            return;
        }

        if (data.ai_pending) {
            isAITurn = true;
            setInfo("IA EN CALCUL...", "var(--neon-blue)");
            setTimeout(() => triggerAIMove(), 150);
        } else {
            setInfo("EN ATTENTE DU PROCHAIN COUP...");
        }
    });
}

function triggerAIMove() {
    fetch("/ai_move", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        isAITurn = false;
        if (data.error) return;

        drawBoard(data.grid, data.scores || [], data.winning_cells || []);

        if (data.winner) {
            const who = data.winner === 1 ? "ROUGE" : "JAUNE";
            const col = data.winner === 1 ? "var(--player-red)" : "var(--player-yellow)";
            setInfo(`⬤ VICTOIRE — JOUEUR ${who} !`, col);
            setTimeout(() => alert(`Victoire joueur ${who} !`), 100);
        } else if (data.draw) {
            setInfo("MATCH NUL — ÉGALITÉ PARFAITE", "var(--neon-blue)");
            setTimeout(() => alert("Match nul !"), 100);
        } else {
            const whoNow = humanColor === 1 ? "ROUGE" : "JAUNE";
            setInfo(`À TON TOUR — ${whoNow} !`, humanColor === 1 ? "var(--player-red)" : "var(--player-yellow)");
        }
    });
}

// ══════════════════════════════════════════
// IA VS IA
// ══════════════════════════════════════════
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

// ══════════════════════════════════════════
// IA SUGGESTION
// ══════════════════════════════════════════
function aiSuggestion() {
    setInfo("ANALYSE EN COURS...", "var(--neon-blue)");
    fetch("/ai_suggest", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        if (data.col === null) return;
        setInfo(`IA SUGGÈRE COLONNE : ${data.col}`, "var(--neon-yellow)");
        highlightColumn(data.col);
    });
}

function highlightColumn(col) {
    const cells = boardDiv.querySelectorAll('.cell');
    const toHighlight = [];
    for (let r = 0; r < ROWS; r++) {
        toHighlight.push(cells[r * COLS + col]);
    }
    let count = 0;
    const interval = setInterval(() => {
        toHighlight.forEach(cell => {
            cell.style.boxShadow = count % 2 === 0
                ? '0 0 20px var(--neon-yellow), 0 0 40px var(--neon-yellow)'
                : '';
            cell.style.background = count % 2 === 0
                ? 'rgba(255,230,0,0.25)'
                : '';
        });
        count++;
        if (count >= 6) {
            clearInterval(interval);
            toHighlight.forEach(cell => {
                cell.style.boxShadow = '';
                cell.style.background = '';
            });
        }
    }, 250);
}

// ══════════════════════════════════════════
// PRÉDICTION
// ══════════════════════════════════════════
function analyzeGame() {
    setInfo("ANALYSE PRÉDICTIVE EN COURS...", "var(--neon-blue)");
    fetch("/predict", { method: "POST" })
    .then(res => res.json())
    .then(data => {
        if (data.prediction) {
            setInfo("🔮 " + data.prediction, "var(--neon-yellow)");
        } else {
            setInfo("ANALYSE : PARTIE NON COMMENCÉE", "var(--text-dim)");
        }
    });
}

// ══════════════════════════════════════════
// MODE PAINTING
// ══════════════════════════════════════════
function togglePaintMode() {
    paintMode = !paintMode;
    const btn = document.getElementById("paintBtn");
    const paintControls = document.getElementById("paintControls");

    if (paintMode) {
        btn.classList.add("btn-active-paint");
        btn.textContent = "🖌 PAINT ON";
        paintControls.style.display = "flex";
        stopAIVsAI();
        gameStarted = false;
        setInfo("MODE PAINTING — CLIQUE SUR LES CASES", "var(--neon-yellow)");
        fetch("/get_grid")
        .then(r => r.json())
        .then(d => drawBoard(d.grid));
    } else {
        exitPaintMode();
    }
}

function exitPaintMode() {
    paintMode = false;
    const btn = document.getElementById("paintBtn");
    const paintControls = document.getElementById("paintControls");
    if (btn) {
        btn.classList.remove("btn-active-paint");
        btn.textContent = "🖌 PAINT";
    }
    if (paintControls) paintControls.style.display = "none";
}

function setPaintColor(color) {
    paintColor = color;
    document.querySelectorAll(".paint-color-btn").forEach(b => b.classList.remove("active-paint-btn"));
    document.getElementById("paintColor" + color).classList.add("active-paint-btn");
}

function paintCell(row, col) {
    fetch("/paint", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({row, col, color: paintColor})
    })
    .then(res => res.json())
    .then(data => {
        drawBoard(data.grid);

        // Afficher clairement à qui c'est de jouer avec couleur visuelle
        const nextColor = data.next_color === "red" ? "var(--player-red)" : "var(--player-yellow)";
        const nextIcon = data.next_color === "red" ? "🔴" : "🟡";
        setInfo(
            `${nextIcon} PROCHAIN: ${data.next_player}  |  Rouge: ${data.red_count}  Jaune: ${data.yellow_count}`,
            nextColor
        );

        // Mettre à jour l'indicateur visuel dans le panneau painting
        const indicator = document.getElementById("paintNextPlayer");
        if (indicator) {
            indicator.textContent = `⬤ ${data.next_player}`;
            indicator.style.color = nextColor;
        }
    });
}

function startFromPaint() {
    const mode = document.getElementById("paintMode").value;
    const ai_type = document.getElementById("paintAiType").value;
    const depth = document.getElementById("depth").value;
    const human_color = document.getElementById("paintHumanColor").value;

    fetch("/start_from_paint", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode, ai_type, depth: parseInt(depth), human_color})
    })
    .then(res => res.json())
    .then(data => {
        exitPaintMode();
        gameStarted = true;
        currentMode = mode;
        humanColor = human_color === "rouge" ? 1 : 2;
        lastScores = [];
        drawBoard(data.grid);
        setInfo(`PARTIE DEPUIS PAINTING — TOUR : ${data.next_player}`, "var(--neon-green)");
        if (currentMode === "ai_vs_ai") launchAIVsAI();
        if (data.ai_pending) {
            isAITurn = true;
            setTimeout(() => triggerAIMove(), 300);
        }
    });
}

// ══════════════════════════════════════════
// CHANGER CONTRÔLE EN COURS DE PARTIE
// ══════════════════════════════════════════
function switchControl() {
    const newMode = document.getElementById("switchMode").value;
    const newAiType = document.getElementById("ai_type").value;
    const newHumanColor = document.getElementById("switchHumanColor").value;

    fetch("/switch_control", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode: newMode, ai_type: newAiType, human_color: newHumanColor})
    })
    .then(res => res.json())
    .then(data => {
        currentMode = newMode;
        humanColor = newHumanColor === "rouge" ? 1 : 2;
        stopAIVsAI();

        const colorLabel = newHumanColor === "rouge" ? "ROUGE 🔴" : "JAUNE 🟡";
        setInfo(`MODE → ${newMode} | HUMAIN = ${colorLabel}`, "var(--neon-yellow)");

        if (currentMode === "ai_vs_ai") launchAIVsAI();

        // Si c'est à l'IA de jouer maintenant
        if (data.ai_pending) {
            isAITurn = true;
            setTimeout(() => triggerAIMove(), 300);
        }
    });
}

// ══════════════════════════════════════════
// AUTRES ACTIONS
// ══════════════════════════════════════════
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

// ══════════════════════════════════════════
// INIT
// ══════════════════════════════════════════
drawBoard(INITIAL_GRID);
if (RESUMED) {
    gameStarted = true;
    currentMode = RESUMED_MODE;
    setInfo("PARTIE REPRISE — À TON TOUR !", "var(--neon-green)");
    if (currentMode === "ai_vs_ai") launchAIVsAI();
}