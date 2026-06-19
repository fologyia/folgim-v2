import os
import sys
import streamlit.web.cli as stcli

def resolve_path(path):
    """Garante que as pastas e arquivos sejam encontrados quando o app virar .exe"""
    if getattr(sys, 'frozen', False):
        # Se estiver rodando como .exe, o PyInstaller descompacta os arquivos na pasta temporária _MEIPASS
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, path)

def main():
    app_path = resolve_path('app.py')
    
    # Simula o comando "streamlit run app.py" nativamente
    sys.argv = [
        "streamlit", 
        "run", 
        app_path, 
        "--global.developmentMode=false"
    ]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()