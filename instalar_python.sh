#!/usr/bin/env bash
# ============================================================================
#  instalar_python.sh  ·  Linux / macOS
#
#  Comprueba que hay Python 3.8 o superior y, si no lo hay, lo instala con el
#  gestor de paquetes de tu sistema. Después prueba el conversor de skins de
#  Actions & Stuff (si el .py está en la misma carpeta).
#
#  Uso:   bash instalar_python.sh            (pregunta antes de instalar nada)
#         bash instalar_python.sh --si       (sin preguntar)
#         bash instalar_python.sh mi_skin.png   (además convierte esa skin)
# ============================================================================
set -u

AUTO=0
SKIN=""
for arg in "$@"; do
  case "$arg" in
    --si|--yes|-y) AUTO=1 ;;
    *.png) SKIN="$arg" ;;
  esac
done

MIN_MAYOR=3
MIN_MENOR=8
AQUI="$(cd "$(dirname "$0")" && pwd)"
CONVERSOR="$AQUI/conversor_actions_stuff.py"

verde() { printf '\033[32m%s\033[0m\n' "$1"; }
rojo()  { printf '\033[31m%s\033[0m\n' "$1"; }
gris()  { printf '\033[90m%s\033[0m\n' "$1"; }

# ---------------------------------------------------------------- 1) ¿hay Python?
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" - <<'EOF' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
EOF
    then PY="$cand"; break; fi
  fi
done

if [ -n "$PY" ]; then
  verde "✔ Python ya instalado: $("$PY" -c 'import sys; print(sys.version.split()[0])')  (comando: $PY)"
else
  echo "No hay Python 3.8+ en este sistema. Voy a instalarlo."
  # ¿con qué gestor?
  GESTOR=""
  for g in apt-get dnf yum pacman zypper apk brew; do
    command -v "$g" >/dev/null 2>&1 && { GESTOR="$g"; break; }
  done
  if [ -z "$GESTOR" ]; then
    rojo "No reconozco el gestor de paquetes de este sistema."
    echo "Instala Python 3 a mano desde https://www.python.org/downloads/ y vuelve a ejecutar este script."
    exit 1
  fi
  case "$GESTOR" in
    apt-get) ORDEN="sudo apt-get update && sudo apt-get install -y python3 python3-pip" ;;
    dnf)     ORDEN="sudo dnf install -y python3 python3-pip" ;;
    yum)     ORDEN="sudo yum install -y python3 python3-pip" ;;
    pacman)  ORDEN="sudo pacman -Sy --noconfirm python python-pip" ;;
    zypper)  ORDEN="sudo zypper install -y python3 python3-pip" ;;
    apk)     ORDEN="sudo apk add python3 py3-pip" ;;
    brew)    ORDEN="brew install python@3.12" ;;
  esac
  echo "  gestor: $GESTOR"
  echo "  orden : $ORDEN"
  echo
  if [ "$AUTO" -eq 0 ]; then
    printf "¿La ejecuto? [s/N] "
    read -r resp
    case "$resp" in s|S|si|sí|y|Y) ;; *) echo "Cancelado. No se ha instalado nada."; exit 1 ;; esac
  fi
  if eval "$ORDEN"; then
    PY=""
    for cand in python3 python; do
      command -v "$cand" >/dev/null 2>&1 && { PY="$cand"; break; }
    done
    [ -n "$PY" ] && verde "✔ Instalado: $("$PY" -c 'import sys; print(sys.version.split()[0])')"
  fi
  if [ -z "$PY" ]; then
    rojo "✘ No ha quedado un Python 3.8+ disponible. Revisa los mensajes de arriba."
    exit 1
  fi
fi

# ---------------------------------------------------------------- 2) el conversor
if [ ! -f "$CONVERSOR" ]; then
  gris "Aviso: no encuentro conversor_actions_stuff.py en esta carpeta ($AQUI)."
  gris "Ponlo al lado de este script para probarlo."
  exit 0
fi

echo
echo "Prueba real del conversor (tipos de la plantilla oficial):"
"$PY" "$CONVERSOR" --estilos || { rojo "✘ El conversor no ha arrancado."; exit 1; }

if [ -n "$SKIN" ]; then
  echo
  echo "Convirtiendo: $SKIN"
  "$PY" "$CONVERSOR" "$SKIN" --info
fi

echo
gris "Cómo se usa:"
gris "  $PY conversor_actions_stuff.py mi_skin.png                 -> mi_skin_as.png (la que subes al juego)"
gris "  $PY conversor_actions_stuff.py mi_skin.png --info           -> informe completo"
gris "  $PY conversor_actions_stuff.py *.png -d salida --pack mis_skins.mcpack"
echo
gris "Si en el juego no pestañea la skin:"
gris "  - Actions & Stuff 1.5 o superior"
gris "  - Ajustes - Recursos - Actions & Stuff - engranaje - \"Enable Expressions\" ACTIVADO"
gris "  - Vibrant Visuals DESACTIVADO"
gris "  - la skin debe ser una skin clásica subida (no del creador de personajes)"
