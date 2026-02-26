from game_importer import import_txt_file

# 🔹 Nom du fichier txt à importer
filename = "3131313.txt"

# 🔹 Paramètres de la partie
mode = "2players"             # "2players", "human_vs_ai", ou "ai_vs_ai"
starting_color = "ROUGE"      # "ROUGE" ou "JAUNE"

# 🔹 Appel de la fonction d'import
import_txt_file(filename, mode=mode, starting_color=starting_color)
