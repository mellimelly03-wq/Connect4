const boardDiv = document.getElementById("board");
const info = document.getElementById("info");

boardDiv.style.gridTemplateColumns = `repeat(${COLS}, 60px)`;

let gameStarted = false;
let lastMove = null;

function drawBoard(grid, scores = []) {

    // Nettoyer plateau
    boardDiv.innerHTML = "";

    // Nettoyer anciens scores
    const oldScores = document.getElementById("scoresRow");
    if (oldScores) oldScores.remove();

    // --- DESSIN DU PLATEAU ---
    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {

            const cell = document.createElement("div");
            cell.classList.add("cell");

            if (grid[r][c] === 1)
                cell.style.backgroundColor = "red";
            else if (grid[r][c] === 2)
                cell.style.backgroundColor = "yellow";

            cell.onclick = () => playMove(c);
            boardDiv.appendChild(cell);
        }
    }

    // --- AFFICHAGE SCORES MINIMAX SOUS LE PLATEAU ---
    if (scores && scores.length > 0) {

        const scoreRow = document.createElement("div");
        scoreRow.id = "scoresRow";
        scoreRow.style.display = "grid";
        scoreRow.style.gridTemplateColumns = `repeat(${COLS}, 60px)`;
        scoreRow.style.marginTop = "10px";

        for (let c = 0; c < COLS; c++) {

            const scoreCell = document.createElement("div");
            scoreCell.style.textAlign = "center";
            scoreCell.style.color = "white";
            scoreCell.style.fontSize = "14px";

            const found = scores.find(s => s[0] === c);
            scoreCell.innerText = found ? found[1] : "";

            scoreRow.appendChild(scoreCell);
        }

        boardDiv.parentNode.appendChild(scoreRow);
    }
}

function startGame() {
    const mode = document.getElementById("mode").value;
    const ai_type = document.getElementById("ai_type").value;
    const depth = document.getElementById("depth").value;
    const starting = document.getElementById("starting").value;

    if (mode === "") {
        alert("Choisis un mode !");
        return;
    }

    fetch("/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode, ai_type, depth, starting})
    })
    .then(res => res.json())
    .then(data => {
        gameStarted = true;
        drawBoard(data.grid);
        info.innerText = "Partie commencée";
    });
}

function playMove(col) {
    if (!gameStarted) {
        alert("Choisis un mode !");
        return;
    }

    fetch("/move", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({col})
    })
    .then(res => res.json())
    .then(data => {

        if (data.error === "full") {
            alert("Colonne pleine !");
            drawBoard(data.grid);
            return;
        }

        drawBoard(data.grid, data.scores);

        if (data.winner) {
            highlightWinning(data.winning_cells);
            alert("Victoire joueur " + data.winner);
        }

        if (data.draw && !data.winner) {
            alert("Match nul !");
        }
    });
}

function aiSuggestion() {
    fetch("/ai_suggest", {method: "POST"})
    .then(res => res.json())
    .then(data => {
        alert("IA suggère colonne : " + data.col);
    });
}

function undo() {
    fetch("/undo", {method: "POST"})
    .then(res => res.json())
    .then(data => drawBoard(data.grid));
}

function restart() {
    fetch("/restart", {method: "POST"})
    .then(res => res.json())
    .then(data => {
        drawBoard(data.grid);
        info.innerText = "Partie réinitialisée";
    });
}

drawBoard(INITIAL_GRID);
function saveGame() {
    fetch("/save", {method:"POST"})
    .then(res=>res.json())
    .then(data=>{
        alert("Sauvegarde OK");
    });
}

function pauseGame() {
    fetch("/pause", {method:"POST"})
    .then(()=> alert("Pause activée"));
}

function resumeGame() {
    fetch("/resume", {method:"POST"})
    .then(()=> alert("Reprise"));
}

function highlightWinning(cells) {
    const allCells = document.querySelectorAll(".cell");

    cells.forEach(([r, c]) => {
        const index = r * COLS + c;
        allCells[index].style.border = "4px solid lime";
    });
}