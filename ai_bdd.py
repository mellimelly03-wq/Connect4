import json
import hashlib
from database import get_connection

# ==============================
# IA BASE DE DONNÉES
# ==============================
# Stratégie :
#   1. Récupère la séquence des coups joués jusqu'ici
#   2. Cherche en base les parties qui ont la MÊME séquence de début
#   3. Regarde quel coup a été joué ensuite dans ces parties
#   4. Choisit le coup avec le meilleur score (victoires - défaites × confiance)
#
# Indice de confiance :
#   1 = parties aléatoires
#   2 = parties minimax
#   3 = parties humains local
#   4 = parties BGA (très fiables)
# ==============================

class AIBaseDeDonnees:

    def __init__(self, couleur="JAUNE"):
        self.couleur = couleur

    # ==============================
    # MÉTHODE PRINCIPALE
    # ==============================
    def choisir_coup(self, board):
        # Récupérer la séquence de coups joués jusqu'ici
        coups_joues = [col for (_, col, _) in board.history]
        nb_coups    = len(coups_joues)

        scores = self._calculer_scores(coups_joues, nb_coups, board)

        if not scores:
            print(f"[AI_BDD] Aucune situation trouvée après {nb_coups} coups → fallback")
            return self._fallback(board)

        meilleur_col   = max(scores, key=scores.get)
        meilleur_score = scores[meilleur_col]

        print(f"[AI_BDD] Scores : {scores} → choix colonne {meilleur_col} (score={meilleur_score})")

        if meilleur_score <= 0:
            return self._fallback(board)

        return meilleur_col

    # ==============================
    # CALCUL DES SCORES
    # ==============================
    def _calculer_scores(self, coups_joues, nb_coups, board):
        """
        Cherche les parties en base dont les N premiers coups
        correspondent exactement à la séquence actuelle.
        Puis regarde quel coup a été joué en N+1.
        """
        try:
            conn = get_connection()
            cur  = conn.cursor(dictionary=True)

            if nb_coups == 0:
                # Début de partie → regarder le 1er coup de toutes les parties
                cur.execute("""
                    SELECT c.colonne, p.statut, p.confiance
                    FROM coup c
                    JOIN partie p ON p.id = c.partie_id
                    WHERE c.numero = 1
                """)
            else:
                # Trouver les parties dont les N premiers coups correspondent
                # On construit le hash de la séquence actuelle
                hash_seq = self._hash_sequence(coups_joues)

                cur.execute("""
                    SELECT c_next.colonne, p.statut, p.confiance
                    FROM partie p
                    JOIN coup c_next ON c_next.partie_id = p.id
                                    AND c_next.numero = %s
                    WHERE p.id IN (
                        SELECT partie_id
                        FROM coup
                        WHERE numero <= %s
                        GROUP BY partie_id
                        HAVING MD5(GROUP_CONCAT(colonne ORDER BY numero SEPARATOR '')) = %s
                    )
                """, (nb_coups + 1, nb_coups, hash_seq))

            lignes = cur.fetchall()
            conn.close()

            if not lignes:
                return {}

            scores = {}
            for ligne in lignes:
                col       = ligne["colonne"]
                statut    = ligne["statut"]
                confiance = ligne["confiance"] or 1

                if board.is_column_full(col):
                    continue

                gain  = self._calculer_gain(statut)
                poids = gain * confiance

                scores[col] = scores.get(col, 0) + poids

            return scores

        except Exception as e:
            print(f"[AI_BDD] Erreur SQL : {e}")
            return {}

    # ==============================
    # HASH DE LA SÉQUENCE
    # ==============================
    def _hash_sequence(self, coups):
        """
        Hash MD5 de la séquence de coups
        ex: [3, 4, 3] → md5("343")
        Même format que GROUP_CONCAT en SQL.
        """
        s = ''.join(map(str, coups))
        return hashlib.md5(s.encode()).hexdigest()

    # ==============================
    # GAIN SELON RÉSULTAT
    # ==============================
    def _calculer_gain(self, statut):
        if statut == f"TERMINE_{self.couleur}":
            return 1    # victoire
        elif statut in ("TERMINE_ROUGE", "TERMINE_JAUNE"):
            return -1   # défaite
        else:
            return 0    # nul ou en cours

    # ==============================
    # FALLBACK — joue proche du centre
    # ==============================
    def _fallback(self, board):
        centre  = board.cols // 2
        valides = [c for c in range(board.cols) if not board.is_column_full(c)]
        if not valides:
            return None
        valides.sort(key=lambda c: abs(c - centre))
        return valides[0]