import hashlib
from database import get_connection
from board import RED, YELLOW

class AIBaseDeDonnees:

    def __init__(self, couleur="JAUNE"):
        self.couleur = couleur
        self.couleur_int = YELLOW if couleur == "JAUNE" else RED

    # ==============================
    # MÉTHODE PRINCIPALE
    # ==============================
    def choisir_coup(self, board):
        coups_joues = [col for (_, col, _) in board.history]
        nb_coups = len(coups_joues)

        print("[AI_BDD] coups:", coups_joues)

        # 1. Victoire immédiate
        for col in self._cols_valides(board):
            board.drop_piece(col, self.couleur_int)
            if board.check_winner(self.couleur_int):
                board.undo()
                print(f"[AI_BDD] Victoire immédiate → {col}")
                return col
            board.undo()

        # 2. Bloquer adversaire
        opp = RED if self.couleur_int == YELLOW else YELLOW
        for col in self._cols_valides(board):
            board.drop_piece(col, opp)
            if board.check_winner(opp):
                board.undo()
                print(f"[AI_BDD] Blocage → {col}")
                return col
            board.undo()

        # 3. BDD
        scores = self._calculer_scores(coups_joues, nb_coups, board)

        if scores and max(scores.values(), default=0) > 0:
            meilleur_col = max(scores, key=scores.get)
            print(f"[AI_BDD] BDD → {scores} → {meilleur_col}")
            return meilleur_col

        # 4. fallback SAFE
        print("[AI_BDD] fallback minimax")
        return self._fallback_minimax(board)

    # ==============================
    # BDD (SAFE)
    # ==============================
    def _calculer_scores(self, coups_joues, nb_coups, board):
        try:
            conn = get_connection()
            cur = conn.cursor(dictionary=True)

            hash_seq = self._hash_sequence(coups_joues)

            cur.execute("""
                SELECT c_next.colonne, p.statut, p.confiance,
                       COUNT(*) as nb_fois
                FROM partie p
                JOIN coup c_next ON c_next.partie_id = p.id
                                 AND c_next.numero = %s
                WHERE p.statut != 'EN_COURS'
                AND p.id IN (
                    SELECT partie_id
                    FROM coup
                    WHERE numero <= %s
                    GROUP BY partie_id
                    HAVING MD5(GROUP_CONCAT(colonne ORDER BY numero SEPARATOR '')) = %s
                )
                GROUP BY c_next.colonne, p.statut, p.confiance
            """, (nb_coups + 1, nb_coups, hash_seq))

            lignes = cur.fetchall()
            conn.close()

            return self._agreger(lignes, board)

        except Exception as e:
            print(f"[AI_BDD] BDD OFF → {e}")
            return {}   # ⚠️ super important → jamais None

    # ==============================
    # AGRÉGATION
    # ==============================
    def _agreger(self, lignes, board):
        scores = {}

        for ligne in lignes:
            col = ligne["colonne"]

            if board.is_column_full(col):
                continue

            statut = ligne["statut"]
            confiance = ligne.get("confiance") or 1
            nb_fois = ligne.get("nb_fois") or 1

            gain = self._calculer_gain(statut)
            poids = gain * confiance * nb_fois

            scores[col] = scores.get(col, 0) + poids

        return scores

    # ==============================
    # OUTILS
    # ==============================
    def _hash_sequence(self, coups):
        s = ''.join(map(str, coups))
        return hashlib.md5(s.encode()).hexdigest()

    def _calculer_gain(self, statut):
        if statut == f"TERMINE_{self.couleur}":
            return 1
        elif statut == "TERMINE_NUL":
            return 0.1
        elif statut in ("TERMINE_ROUGE", "TERMINE_JAUNE"):
            return -1
        return 0

    # ==============================
    # FALLBACK CORRIGÉ
    # ==============================
    def _fallback_minimax(self, board):
        try:
            from minmax import MiniMaxAI
            ai = MiniMaxAI(depth=4)

            # ✅ FIX ICI
            col = ai.choose_move(board, self.couleur_int)

            if col is not None:
                return col

        except Exception as e:
            print(f"[AI_BDD] minimax error → {e}")

        return self._fallback_centre(board)

    def _fallback_centre(self, board):
        centre = board.cols // 2
        valides = self._cols_valides(board)

        if not valides:
            return None

        valides.sort(key=lambda c: abs(c - centre))
        return valides[0]

    def _cols_valides(self, board):
        return [c for c in range(board.cols) if not board.is_column_full(c)]