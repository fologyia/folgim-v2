import os
import sys
import subprocess

def main():
    """
    Launcher para o FologyHUB Defin.
    Identifica o ambiente e executa o servidor Streamlit de forma limpa.
    """
    # Obtém o diretório onde este script está localizado
    base_path = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_path, "app.py")

    # Comando para executar o Streamlit usando o interpretador atual
    cmd = [sys.executable, "-m", "streamlit", "run", app_path, "--browser.gatherUsageStats=false"]

    print("========================================")
    print("      INICIANDO FOLOGYHUB DEFIN         ")
    print("========================================")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[SISTEMA] Encerrando FologyHUB...")

if __name__ == "__main__":
    main()