#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor de skins -> Actions & Stuff Expresiones   ·   versión con INTERFAZ GRÁFICA
====================================================================================

Ventana de escritorio (tkinter, que viene con Python: no hay que instalar nada más)
para convertir skins de Minecraft en skins compatibles con el addon
**Actions & Stuff — Expresiones** (Oreville Studios, 1.5 / 1.10 / 1.11).

Usa el motor de `conversor_actions_stuff.py`, que tiene que estar en la misma carpeta.

CÓMO SE ABRE
------------
    python conversor_actions_stuff_gui.py
    python conversor_actions_stuff_gui.py mi_skin.png      (abre ya esa skin)
    pythonw conversor_actions_stuff_gui.py                 (Windows, sin consola detrás)

QUÉ TIENE
---------
  · Abrir un PNG de 64x64 (o 128x128 / 256x256) y ver al momento cómo queda (textura, cara, backFace y blinkFace).
  · Simulación de los estados: ojos abiertos, cerrar cada ojo, mirar a los lados.
  · Los mismos ajustes que la versión del navegador: tipo de ojo y ceja, fila de sorpresa,
    parpadeo oficial o sencillo, combinar la capa de sombrero, limpiar el arte anterior,
    ajustar a la plantilla y colores fijos (pupila, ceja, esclerótica, párpado, cubos).
  · Informe de lo que ha detectado y de lo que ha escrito.
  · Guardar la skin convertida, y montar un pack de varias skins (.mcpack) con modelo
    clásico o delgado para cada una.
  · Descargar desde la ventana la PLANTILLA oficial (.zip) y el PACK oficial de skins
    (.mcpack) que publica Oreville gratis, y abrir la guía oficial en el navegador.

Si en el juego no pestañea: A&S 1.5+, y en Ajustes -> Recursos -> Actions & Stuff ->
⚙️ «Enable Expressions» activado, con Vibrant Visuals desactivado; y la skin tiene que
ser una skin clásica subida (no del creador de personajes).

Autor: no está afiliado a Oreville Studios ni a Mojang. Licencia: úsalo como quieras.
"""

from __future__ import annotations

import base64
import os
import sys
import threading
import traceback
import urllib.request
import webbrowser

# ----------------------------------------------------------------------------
#  Motor (tiene que estar al lado)
# ----------------------------------------------------------------------------
AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)
try:
    import conversor_actions_stuff as cas
except Exception as exc:  # pragma: no cover
    sys.stderr.write(
        "No encuentro el motor del conversor (conversor_actions_stuff.py) en:\n  %s\n\nError: %s\n" % (AQUI, exc))
    sys.exit(2)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter import colorchooser
except Exception as exc:  # pragma: no cover
    sys.stderr.write("Este Python no trae tkinter. En Linux: sudo apt install python3-tk\n(%s)\n" % exc)
    sys.exit(2)


VERSION = "1.0"
FUENTE = ("Segoe UI", 9) if os.name == "nt" else ("Helvetica", 10)
ESCALA_TEXTURA = 4        # 64x64 -> 256x256 en la ventana
ESCALA_CARA = 18          # 8x8 -> 144x144
ESCALA_CAPA = 12          # 8x8 -> 96x96 en los cuadros de capas
FONDO = "#0f1418"
FONDO2 = "#161d23"
TEXTO = "#e8eef2"
TEXTO2 = "#93a4b1"
ACENTO = "#57c78a"

# Descargas oficiales de Oreville Studios (gratis). Se descargan desde la propia ventana.
OFICIAL = {
    "plantilla": ("https://orevillestudios.com/api/downloads/actions-stuff-expressions-template",
                  "Actions & Stuff Expressions Template.zip",
                  "la plantilla oficial (.bbmodel de Blockbench + hoja de estilos + Read Me)"),
    "pack": ("https://orevillestudios.com/api/downloads/actions-and-stuff-expressions-skins-1-0-0",
             "Actions & Stuff Expressions Skins.mcpack",
             "el pack oficial de skins con expresiones (33 skins de ejemplo)"),
}
URL_PAGINA_OFICIAL = "https://orevillestudios.com/actions-&-stuff/expressions-template/download"
URL_GUIA = "https://guides.orevillestudios.com/actions-and-stuff-expressions"

ESTADOS = [
    ("abiertos", "Ojos abiertos"),
    ("cerrar_R", "Cerrar el ojo derecho (x0-3)"),
    ("cerrar_L", "Cerrar el ojo izquierdo (x4-7)"),
    ("mirar_izq", "Mirar a la izquierda"),
    ("mirar_der", "Mirar a la derecha"),
]


# ============================================================================
#  Imágenes (sin tkinter: se pueden probar sin ventana)
# ============================================================================

# el servidor de Oreville devuelve 403 si no se pide como un navegador
CABECERAS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
             "Accept": "*/*"}


def descargar_a(url, ruta, progreso=None):
    """Descarga un archivo y lo guarda en disco. Devuelve los bytes escritos.

    Se escribe primero en un archivo temporal y al final se renombra, para que
    en la carpeta elegida nunca quede un archivo a medias si se corta la conexión.
    """
    peticion = urllib.request.Request(url, headers=CABECERAS)
    temporal = ruta + ".descargando"
    try:
        with urllib.request.urlopen(peticion, timeout=60) as r, open(temporal, "wb") as fh:
            total = int(r.headers.get("Content-Length") or 0)
            leido = 0
            while True:
                trozo = r.read(16384)
                if not trozo:
                    break
                fh.write(trozo)
                leido += len(trozo)
                if progreso:
                    progreso(leido, total)
        if total and leido != total:
            raise IOError("descarga incompleta (%d de %d bytes)" % (leido, total))
        os.replace(temporal, ruta)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    return leido


def escalar(px, w, h, escala, con_fondo=True):
    """Amplía por vecino más cercano (px: bytes RGBA)."""
    ws, hs = w * escala, h * escala
    fuera = bytearray(ws * hs * 4)
    for y in range(hs):
        oy = (y // escala) * w * 4
        fo = y * ws * 4
        for x in range(ws):
            sx = (x // escala) * 4 + oy
            dx = x * 4 + fo
            fuera[dx:dx + 4] = px[sx:sx + 4]
    if con_fondo:
        # el transparente sobre el fondo de la ventana, para que se vea parecido al juego
        fr, fg, fb = int(FONDO2[1:3], 16), int(FONDO2[3:5], 16), int(FONDO2[5:7], 16)
        for i in range(0, len(fuera), 4):
            a = fuera[i + 3]
            if a == 0:
                fuera[i], fuera[i + 1], fuera[i + 2], fuera[i + 3] = fr, fg, fb, 255
            elif a < 255:
                for k, f in ((0, fr), (1, fg), (2, fb)):
                    fuera[i + k] = (fuera[i + k] * a + f * (255 - a)) // 255
                fuera[i + 3] = 255
    return bytes(fuera)


def recorte(px, x0, y0, w, h, ancho_tex=64):
    """Saca un trozo rectangular de la textura (RGBA bytes)."""
    fuera = bytearray(w * h * 4)
    for y in range(h):
        si = ((y0 + y) * ancho_tex + x0) * 4
        di = y * w * 4
        fuera[di:di + w * 4] = px[si:si + w * 4]
    return bytes(fuera)


def cara_simulada(face, det, pal, estado):
    """Simulación (aproximada) de lo que anima A&S, para hacerse una idea."""
    out = bytearray(face)
    if estado == "abiertos":
        return bytes(out)

    def pon(x, y, c):
        i = (y * 8 + x) * 4
        if 0 <= x < 8 and 0 <= y < 8:
            out[i], out[i + 1], out[i + 2], out[i + 3] = int(c[0]), int(c[1]), int(c[2]), 255

    if estado in ("cerrar_R", "cerrar_L"):
        t = "R" if estado.endswith("R") else "L"
        e, pe = det["eyes"].get(t), pal["perEye"].get(t)
        if e and e["box"] and pe:
            x0, x1 = e["box"][0], e["box"][2]
            top, bot = e["box"][1], e["box"][3]
            for y in range(top, bot + 1):
                col = pal["lid"] if (y == bot or not pe.get("brow")) else pe["brow"]
                for x in range(x0, x1 + 1):
                    pon(x, y, col)
        return bytes(out)

    if estado in ("mirar_izq", "mirar_der"):
        d = -1 if estado == "mirar_izq" else 1
        for t in ("R", "L"):
            e, pe = det["eyes"].get(t), pal["perEye"].get(t)
            if not e or not pe or not e["pupils"]:
                continue
            x0, x1 = e["box"][0], e["box"][2]
            for c in e["pupils"]:
                nx = c[0] + d
                if nx < x0 or nx > x1:
                    continue
                pon(c[0], c[1], pe["scleraRows"].get(c[1]) or pe["sclera"])
                pon(nx, c[1], pe["pupil"])
        return bytes(out)
    return bytes(out)


# ============================================================================
#  La ventana
# ============================================================================

class App:
    def __init__(self, raiz, ruta_inicial=None):
        self.raiz = raiz
        raiz.title("Conversor de skins · Actions & Stuff Expresiones")
        raiz.configure(bg=FONDO)
        raiz.minsize(900, 620)

        self.datos = None          # bytes del PNG de entrada
        self.nombre = None
        self.det = None
        self.res = None
        self.png_out = None
        self.data_out = None
        self.escala = 1
        self.fotos = {}            # para que tkinter no borre las imágenes
        self.pack = []             # skins añadidas al pack
        self.estado = tk.StringVar(value="abiertos")
        self.var = {}
        self.color = {"pupila": "#3b2a1a", "ceja": "#553311", "esclerotica": "#ffffff",
                      "parpado": "#8a6a4a", "cubos": "#57c78a"}
        self._crear()
        if ruta_inicial:
            self.abrir(ruta_inicial)

    # ---------------------------------------------------------------- interfaz
    def _crear(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure(".", background=FONDO, foreground=TEXTO, fieldbackground=FONDO2,
                         bordercolor="#2f3d47", lightcolor=FONDO2, darkcolor=FONDO2)
        estilo.configure("TFrame", background=FONDO)
        estilo.configure("P.TFrame", background=FONDO2)
        estilo.configure("TLabel", background=FONDO, foreground=TEXTO)
        estilo.configure("T2.TLabel", background=FONDO, foreground=TEXTO2, font=(FUENTE[0], FUENTE[1] - 1))
        estilo.configure("TCheckbutton", background=FONDO, foreground=TEXTO)
        estilo.configure("TRadiobutton", background=FONDO, foreground=TEXTO)
        estilo.configure("TButton", padding=6)
        estilo.configure("Pri.TButton", padding=7, font=(FUENTE[0], FUENTE[1], "bold"))
        estilo.configure("TLabelframe", background=FONDO, foreground=TEXTO2, bordercolor="#2f3d47")
        estilo.configure("TLabelframe.Label", background=FONDO, foreground=ACENTO)
        estilo.configure("TCombobox", fieldbackground=FONDO2)
        estilo.configure("Encabezado.TLabel", font=(FUENTE[0], FUENTE[1] + 6, "bold"), foreground=TEXTO)

        # ---- barra superior
        barra = ttk.Frame(self.raiz)
        barra.pack(fill="x", padx=12, pady=(12, 6))
        ttk.Label(barra, text="Conversor de skins · Actions & Stuff Expresiones",
                  style="Encabezado.TLabel").pack(side="left")
        ttk.Label(barra, text="  todo se hace en tu ordenador · no se sube nada",
                  style="T2.TLabel").pack(side="left", pady=(8, 0))

        cuerpo = ttk.Frame(self.raiz)
        cuerpo.pack(fill="both", expand=True, padx=12, pady=6)
        izq = ttk.Frame(cuerpo)
        izq.pack(side="left", fill="both", expand=True)

        # el panel de controles va dentro de un lienzo con barra, para que nunca se corte
        contenedor = ttk.Frame(cuerpo, width=330)
        contenedor.pack(side="right", fill="y", padx=(12, 0))
        contenedor.pack_propagate(False)
        self.canvas_der = tk.Canvas(contenedor, bg=FONDO, highlightthickness=0, width=318)
        barra_der = ttk.Scrollbar(contenedor, orient="vertical", command=self.canvas_der.yview)
        self.canvas_der.configure(yscrollcommand=barra_der.set)
        barra_der.pack(side="right", fill="y")
        self.canvas_der.pack(side="left", fill="both", expand=True)
        der = ttk.Frame(self.canvas_der)
        self.canvas_der.create_window((0, 0), window=der, anchor="nw", width=316)
        der.bind("<Configure>", lambda e: self.canvas_der.configure(scrollregion=self.canvas_der.bbox("all")))
        self.canvas_der.bind_all("<MouseWheel>", lambda ev: self.canvas_der.yview_scroll(int(-ev.delta / 120), "units"))
        self.canvas_der.bind_all("<Button-4>", lambda ev: self.canvas_der.yview_scroll(-1, "units"))
        self.canvas_der.bind_all("<Button-5>", lambda ev: self.canvas_der.yview_scroll(1, "units"))

        # ---------------- columna izquierda: vistas
        caja = ttk.Frame(izq)
        caja.pack(fill="x")
        self.lbl_tex = ttk.Label(caja, text="Tu skin convertida (64×64)", style="T2.TLabel")
        self.lbl_tex.grid(row=0, column=0, sticky="w")
        ttk.Label(caja, text="La cara, como se verá en el juego (simulación)", style="T2.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0))
        self.lienzo_tex = tk.Canvas(caja, width=64 * ESCALA_TEXTURA, height=64 * ESCALA_TEXTURA,
                                    bg=FONDO2, highlightthickness=1, highlightbackground="#2f3d47")
        self.lienzo_tex.grid(row=1, column=0, sticky="nw")
        self.lienzo_cara = tk.Canvas(caja, width=8 * ESCALA_CARA, height=8 * ESCALA_CARA,
                                     bg=FONDO2, highlightthickness=1, highlightbackground="#2f3d47")
        self.lienzo_cara.grid(row=1, column=1, sticky="nw", padx=(14, 0))

        estados = ttk.Frame(izq)
        estados.pack(fill="x", pady=(8, 0))
        for valor, etiqueta in ESTADOS:
            ttk.Radiobutton(estados, text=etiqueta, value=valor, variable=self.estado,
                            command=self.refrescar).pack(side="left", padx=(0, 10))

        capas = ttk.Frame(izq)
        capas.pack(fill="x", pady=(10, 0))
        self.lienzos_capa = {}
        for i, (clave, titulo) in enumerate((("cara", "cara original (sin A&S)"),
                                             ("back", "backFace (x24-31, y0-7)"),
                                             ("blink", "blinkFace (x0-7, y0-7)"))):
            marco = ttk.Frame(capas)
            marco.grid(row=0, column=i, padx=(0, 14), sticky="nw")
            ttk.Label(marco, text=titulo, style="T2.TLabel").pack(anchor="w")
            lienzo = tk.Canvas(marco, width=8 * ESCALA_CAPA, height=8 * ESCALA_CAPA,
                               bg=FONDO2, highlightthickness=1, highlightbackground="#2f3d47")
            lienzo.pack(anchor="w")
            self.lienzos_capa[clave] = lienzo

        self.lbl_info = ttk.Label(izq, text="Abre una skin para empezar.", style="T2.TLabel",
                                  wraplength=560, justify="left")
        self.lbl_info.pack(fill="x", pady=(10, 4))

        ttk.Label(izq, text="Si en el juego no pestañea: A&S 1.5 o superior · Ajustes → Recursos → "
                            "Actions & Stuff → ⚙️ «Enable Expressions» ACTIVADO · Vibrant Visuals DESACTIVADO · "
                            "la skin debe ser una skin clásica subida (no del creador de personajes).",
                  style="T2.TLabel", wraplength=660, justify="left").pack(fill="x", pady=(6, 0))

        # ---------------- columna derecha: controles
        botones = ttk.Frame(der)
        botones.pack(fill="x")
        ttk.Button(botones, text="Abrir skin…", command=self.elegir, style="Pri.TButton").pack(fill="x", pady=(0, 6))
        self.btn_guardar = ttk.Button(botones, text="Guardar skin convertida…", command=self.guardar, state="disabled")
        self.btn_guardar.pack(fill="x")

        ajustes = ttk.Labelframe(der, text=" Ajustes de la conversión ")
        ajustes.pack(fill="x", pady=(10, 0))
        self.var["sorpresa"] = tk.BooleanVar(value=True)
        self.var["simple"] = tk.BooleanVar(value=False)
        self.var["sombrero"] = tk.BooleanVar(value=False)
        self.var["limpiar"] = tk.BooleanVar(value=True)
        self.var["ajustar"] = tk.BooleanVar(value=True)
        self.var["respetar"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(ajustes, text="Fila de «sorpresa» sobre el ojo", variable=self.var["sorpresa"],
                        command=self.refrescar).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(ajustes, text="Parpadeo sencillo (como los tutoriales)",
                        variable=self.var["simple"], command=self.refrescar).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(ajustes, text="Combinar la capa de sombrero", variable=self.var["sombrero"],
                        command=self.refrescar).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(ajustes, text="Borrar el arte anterior de los cubos", variable=self.var["limpiar"],
                        command=self.refrescar).grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(ajustes, text="Respetar las capas que la skin ya trae", variable=self.var["respetar"],
                        command=self.refrescar).grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(ajustes, text="Ajustar a la plantilla si el ojo no encaja", variable=self.var["ajustar"],
                        command=self.refrescar).grid(row=5, column=0, columnspan=2, sticky="w")

        ttk.Label(ajustes, text="Tipo de ojo").grid(row=6, column=0, sticky="w", pady=(6, 0))
        self.combo_ojo = ttk.Combobox(ajustes, width=17, state="readonly",
                                      values=["auto (el que encaje)"] + list(cas.EYE_STYLES))
        self.combo_ojo.current(0)
        self.combo_ojo.grid(row=6, column=1, sticky="w", pady=(6, 0))
        self.combo_ojo.bind("<<ComboboxSelected>>", lambda e: self.refrescar())
        ttk.Label(ajustes, text="Tipo de ceja").grid(row=7, column=0, sticky="w")
        self.combo_ceja = ttk.Combobox(ajustes, width=17, state="readonly",
                                       values=["auto (el que encaje)"] + list(cas.BROW_STYLES))
        self.combo_ceja.current(0)
        self.combo_ceja.grid(row=7, column=1, sticky="w")
        self.combo_ceja.bind("<<ComboboxSelected>>", lambda e: self.refrescar())

        colores = ttk.Labelframe(der, text=" Colores (si no, los toma de tu skin) ")
        colores.pack(fill="x", pady=(10, 0))
        self.var_col = {}
        for i, (clave, etiqueta) in enumerate((("pupila", "Pupila"), ("ceja", "Ceja"),
                                               ("esclerotica", "Esclerótica"), ("parpado", "Párpado"),
                                               ("cubos", "Cubos"))) :
            v = tk.BooleanVar(value=False)
            self.var_col[clave] = v
            ttk.Checkbutton(colores, text=etiqueta, variable=v, command=self.refrescar).grid(row=i, column=0, sticky="w")
            b = tk.Button(colores, width=3, bg=self.color[clave], relief="flat",
                          command=lambda c=clave: self.elegir_color(c))
            b.grid(row=i, column=1, sticky="w", padx=(6, 0))
            b.clave = clave

        pack = ttk.Labelframe(der, text=" Pack de varias skins ")
        pack.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Button(pack, text="Añadir la convertida al pack", command=self.pack_add).pack(fill="x")
        self.lista = tk.Listbox(pack, height=6, bg=FONDO2, fg=TEXTO, selectbackground="#245139",
                                highlightthickness=1, highlightbackground="#2f3d47", font=FUENTE)
        self.lista.pack(fill="both", expand=True, pady=(6, 6))
        fila = ttk.Frame(pack)
        fila.pack(fill="x")
        ttk.Button(fila, text="Quitar", command=self.pack_quitar).pack(side="left")
        ttk.Label(fila, text="Modelo:").pack(side="left", padx=(8, 4))
        self.modelo = ttk.Combobox(fila, width=13, state="readonly",
                                   values=["clásico (Steve)", "delgado (Alex)"])
        self.modelo.current(0)
        self.modelo.pack(side="left")
        ttk.Button(pack, text="Guardar pack .mcpack…", command=self.pack_guardar).pack(fill="x", pady=(8, 0))

        oficial = ttk.Labelframe(der, text=" Descargas oficiales de Oreville (gratis) ")
        oficial.pack(fill="x", pady=(10, 0))
        ttk.Button(oficial, text="⤓ Plantilla oficial de Blockbench (.zip)",
                   command=lambda: self.bajar_oficial("plantilla")).pack(fill="x")
        ttk.Label(oficial, text="El .bbmodel para Blockbench + la hoja de estilos + el Read Me (63 KB).\n"
                               "Es la misma que usa este conversor por dentro.",
                  style="T2.TLabel", wraplength=300, justify="left").pack(fill="x", pady=(4, 6))
        ttk.Button(oficial, text="⤓ Pack oficial de skins (.mcpack)",
                   command=lambda: self.bajar_oficial("pack")).pack(fill="x")
        ttk.Label(oficial, text="33 skins de ejemplo con expresiones (47 KB), para probar en tu juego.",
                  style="T2.TLabel", wraplength=300, justify="left").pack(fill="x", pady=(4, 6))
        ttk.Button(oficial, text="↗ Abrir las páginas oficiales",
                   command=self.abrir_paginas).pack(fill="x")
        ttk.Label(oficial, text="El addon Actions & Stuff (el de las animaciones) es de PAGO: se compra en el "
                               "Marketplace de Minecraft desde el juego. Esto de aquí es sólo lo gratuito.",
                  style="T2.TLabel", wraplength=300, justify="left").pack(fill="x", pady=(4, 2))

        informe = ttk.Labelframe(der, text=" Informe ")
        informe.pack(fill="both", expand=True, pady=(10, 0))
        self.texto = tk.Text(informe, height=9, width=38, bg=FONDO2, fg=TEXTO, relief="flat",
                             font=(FUENTE[0], FUENTE[1] - 1), wrap="word")
        self.texto.pack(fill="both", expand=True)
        self.texto.configure(state="disabled")
        ttk.Button(der, text="Copiar informe", command=self.copiar_informe).pack(fill="x", pady=(6, 0))

    def elegir_color(self, clave):
        ini = self.color[clave]
        rgb, hexa = colorchooser.askcolor(color=ini, title="Color de " + clave)
        if hexa:
            self.color[clave] = hexa
            self.var_col[clave].set(True)
            self._repintar_botones_color()
            self.refrescar()

    def _repintar_botones_color(self):
        pila = [self.raiz]
        while pila:
            w = pila.pop()
            pila.extend(w.winfo_children())
            if isinstance(w, tk.Button) and hasattr(w, "clave"):
                w.configure(bg=self.color[w.clave])

    # ---------------------------------------------------------------- acciones
    def elegir(self):
        ruta = filedialog.askopenfilename(
            title="Elige tu skin (PNG de 64×64, 128×128 o 256×256)",
            filetypes=[("Imagen PNG", "*.png"), ("Todos los archivos", "*.*")])
        if ruta:
            self.abrir(ruta)

    def abrir(self, ruta, con_aviso=True):
        try:
            with open(ruta, "rb") as fh:
                self.datos = fh.read()
            self.nombre = os.path.basename(ruta)
        except Exception as exc:
            self.datos = None
            if con_aviso:
                messagebox.showerror("No he podido abrirla", "%s\n\n%s" % (exc, ruta))
        self.refrescar()

    def opciones(self):
        return dict(
            sorpresa=bool(self.var["sorpresa"].get()) if "sorpresa" in self.var else True,
            simple=bool(self.var["simple"].get()) if "simple" in self.var else False,
            sombrero=bool(self.var["sombrero"].get()) if "sombrero" in self.var else False,
            limpiar=bool(self.var["limpiar"].get()) if "limpiar" in self.var else True,
            ajustar=bool(self.var["ajustar"].get()) if "ajustar" in self.var else True,
            respetar=bool(self.var["respetar"].get()) if "respetar" in self.var else True,
            ojo=None if self.combo_ojo.current() == 0 else self.combo_ojo.get(),
            ceja=None if self.combo_ceja.current() == 0 else self.combo_ceja.get(),
            color_ojos=self.color["pupila"] if self.var_col["pupila"].get() else None,
            color_cejas=self.color["ceja"] if self.var_col["ceja"].get() else None,
            color_esclerotica=self.color["esclerotica"] if self.var_col["esclerotica"].get() else None,
            color_parpado=self.color["parpado"] if self.var_col["parpado"].get() else None,
            color_cubos=self.color["cubos"] if self.var_col["cubos"].get() else None,
        )

    def convertir(self):
        if not self.datos:
            self.det = self.res = self.png_out = None
            return
        op = self.opciones()
        ancho, alto, rgba = cas.leer_png(self.datos)
        if ancho != alto or ancho not in (64, 128, 256):
            if (ancho, alto) == (64, 32):
                raise ValueError("esta skin es 64×32 (formato antiguo): no tiene las zonas de A&S")
            raise ValueError("la skin mide %dx%d: tiene que ser cuadrada (64×64, 128×128 o 256×256)"
                             % (ancho, alto))
        self.escala = ancho // 64
        # En 128/256 la cara ocupa 16×16 o 32×32 px: se analiza la versión bajada a 64×64
        base = bytes(rgba) if self.escala == 1 else cas.bajar_a_64(rgba, ancho)
        self.det = cas.analizar_cara(cas.cara_de(base))
        if self.det is None:
            raise ValueError("no he reconocido los ojos de esta skin")
        self.face = cas.cara_de(base)
        self.rgba = rgba
        self.res = cas.generar_skin(base, self.det, surprised=op["sorpresa"],
                                    blinkStyle="simple" if op["simple"] else "oficial",
                                    combineHat=op["sombrero"], cleanSlots=op["limpiar"], snap=op["ajustar"],
                                    eyeStyle=op["ojo"], browStyle=op["ceja"],
                                    pupilColor=op["color_ojos"], browColor=op["color_cejas"],
                                    scleraColor=op["color_esclerotica"], lidColor=op["color_parpado"],
                                    slotColor=op["color_cubos"], respetar=op["respetar"],
                                    minSame=(0 if self.escala > 1 else None))
        self.data_out = self.res["data"]
        if self.escala > 1:
            # se devuelve a su tamaño; las capas que la skin ya traía se copian tal cual
            self.data_out = cas.subir_de_64(self.data_out, ancho)
            resp = self.res["stats"]["respetado"]
            if resp.get("blink"):
                cas.copiar_zona(rgba, ancho, 0, 0, 8, 8, self.data_out)
            if resp.get("back"):
                cas.copiar_zona(rgba, ancho, 24, 0, 8, 8, self.data_out)
        self.res["tamano"] = ancho
        self.png_out = cas.escribir_png(ancho, ancho, self.data_out)

    def refrescar(self):
        """Convierte (si hay skin) y repinta todo."""
        try:
            self.convertir()
            self.btn_guardar.configure(state="normal" if self.png_out else "disabled")
        except Exception as exc:
            self.png_out = None
            self.btn_guardar.configure(state="disabled")
            self.lbl_info.configure(text="⚠ " + str(exc))
            self._texto("No se ha podido convertir: %s" % exc)
            return
        if not self.png_out:
            self.lbl_info.configure(text="Abre una skin para empezar (PNG de 64×64, 128×128 o 256×256).")
            self._texto("Abre una skin para empezar.\n\nConsejo: puedes usar una de las 33 skins de "
                        "ejemplo del pack oficial de Oreville (enlace en la versión HTML) para probar.")
            self._borrar_lienzos()
            return
        self._pintar()
        self._informe()

    def _foto(self, clave, px, w, h, escala, lienzo):
        crudo = escalar(px, w, h, escala)
        b64 = base64.b64encode(cas.escribir_png(w * escala, h * escala, crudo)).decode("ascii")
        foto = tk.PhotoImage(data=b64)
        self.fotos[clave] = foto
        lienzo.delete("all")
        lienzo.create_image(0, 0, anchor="nw", image=foto)

    def _borrar_lienzos(self):
        for l in [self.lienzo_tex, self.lienzo_cara] + list(self.lienzos_capa.values()):
            l.delete("all")

    def _pintar(self):
        lado = self.res.get("tamano", 64)
        self.lbl_tex.configure(text="Tu skin convertida (%d×%d)" % (lado, lado))
        self._foto("tex", self.data_out, lado, lado, max(1, ESCALA_TEXTURA // (lado // 64)), self.lienzo_tex)
        cara = cara_simulada(self.face, self.det, self.res["palette"], self.estado.get())
        self._foto("cara", cara, 8, 8, ESCALA_CARA, self.lienzo_cara)
        self._foto("c0", self.face, 8, 8, ESCALA_CAPA, self.lienzos_capa["cara"])
        self._foto("c1", recorte(self.data_out, 24, 0, 8, 8), 8, 8, ESCALA_CAPA, self.lienzos_capa["back"])
        self._foto("c2", recorte(self.data_out, 0, 0, 8, 8), 8, 8, ESCALA_CAPA, self.lienzos_capa["blink"])

    def _texto(self, t):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", t)
        self.texto.configure(state="disabled")

    def _informe(self):
        r = self.res["stats"]
        d = self.det
        lineas = []
        lineas.append("archivo: %s" % self.nombre)
        lineas.append("detección: %s · ancla: %s · color de piel %s" % (d["confidence"], d["anchor"], cas.rgb_texto(d["skin"])))
        for t, nombre in (("R", "derecho"), ("L", "izquierdo")):
            e = d["eyes"][t]
            b = d["brows"][t]
            lineas.append("ojo (el suyo %s): %d píxel(es) de pupila · caja %s · ceja %s"
                          % (nombre, len(e["pupils"]), e["box"], ("fila %d" % b["y"]) if b else "—"))
        for t in ("R", "L"):
            lineas.append("cubos de ojo %s: %s" % (t, ", ".join(self.res["plan"]["eye"][0 if t == "R" else 1]["estilos"]) or "ninguno"))
        for it in self.res["plan"]["brow"]:
            lineas.append("cubos de ceja %s: %s" % (it["side"], ", ".join(it["estilos"]) or "ninguno"))
        lineas.append("escrito: %d píxeles en la cara trasera · %d en la de parpadeo · %d en los cubos%s"
                      % (r["back"], r["blink"], r["slots"], (" · %d borrados" % r["cleaned"]) if r["cleaned"] else ""))
        for n in d["notes"]:
            lineas.append("aviso: " + n)
        if r.get("snapped"):
            lineas.append("ajustado a la plantilla: " + " · ".join(r["snapped"]))
        if r.get("cleanedSkip"):
            lineas.append("aviso: no encaja ningún cubo, así que sus zonas se han dejado como estaban.")
        if r["unreachable"]:
            lineas.append("sin cubo: " + " · ".join(r["unreachable"]))
        if r["missing"]:
            lineas.append("píxeles sin cubo: " + ", ".join(r["missing"]))
        if r["hat"]["total"]:
            lineas.append("capa de sombrero: %d píxeles (%d sobre los ojos)" % (r["hat"]["total"], r["hat"]["enOjos"]))
        self.lbl_info.configure(text="%s · %s" % (self.nombre, (" · ".join(r["slotList"]) or "sin cubos")))
        self._texto("\n".join(lineas))

    # ------------------------------------------------- descargas oficiales
    def bajar_oficial(self, clave):
        url, nombre, descripcion = OFICIAL[clave]
        ruta = filedialog.asksaveasfilename(
            title="Guardar " + descripcion, defaultextension=os.path.splitext(nombre)[1],
            initialfile=nombre, initialdir=os.path.expanduser("~"),
            filetypes=[("Archivo", "*" + os.path.splitext(nombre)[1]), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        self.lbl_info.configure(text="Descargando %s…" % descripcion)

        def progreso(leido, total):
            if total:
                self.raiz.after(0, lambda p=leido * 100 // total: self.lbl_info.configure(
                    text="Descargando %s… %d%%" % (descripcion, p)))

        def trabajo():
            try:
                n = descargar_a(url, ruta, progreso)
                self.raiz.after(0, lambda: self.lbl_info.configure(
                    text="Descargado: %s (%d KB) — %s" % (ruta, n // 1024, descripcion)))
            except Exception as exc:
                detalle = str(exc) or type(exc).__name__   # algunas excepciones vienen sin texto

                def fallo():
                    self.lbl_info.configure(text="No he podido descargar (%s). Abro la página oficial…" % detalle)
                    self.abrir_paginas()
                self.raiz.after(0, fallo)

        threading.Thread(target=trabajo, daemon=True).start()

    def abrir_paginas(self):
        for u in (URL_PAGINA_OFICIAL, URL_GUIA):
            try:
                webbrowser.open(u)
            except Exception:
                pass

    def copiar_informe(self):
        t = self.texto.get("1.0", "end").strip()
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(t)
        self.lbl_info.configure(text="Informe copiado al portapapeles.")

    def guardar(self):
        if not self.png_out:
            return
        base = os.path.splitext(self.nombre or "skin")[0] + "_as.png"
        ruta = filedialog.asksaveasfilename(title="Guardar la skin convertida", defaultextension=".png",
                                            initialfile=base, filetypes=[("Imagen PNG", "*.png")])
        if not ruta:
            return
        try:
            with open(ruta, "wb") as fh:
                fh.write(self.png_out)
        except Exception as exc:
            messagebox.showerror("No he podido guardar", str(exc))
            return
        self.lbl_info.configure(text="Guardada: %s — súbela en Minecraft: Ajustes → Perfil → Skins → Subir skin." % ruta)

    # ------------------------------------------------------------------- pack
    def pack_add(self):
        if not self.png_out:
            messagebox.showinfo("Nada que añadir", "Abre y convierte una skin primero.")
            return
        modelo = "geometry.humanoid.customSlim" if self.modelo.current() == 1 else "geometry.humanoid.custom"
        base = os.path.splitext(self.nombre or "skin")[0]
        self.pack.append({"png": self.png_out, "slug": cas._slug(base), "display": base, "geometry": modelo})
        self.lista.insert("end", "%s  ·  %s" % (base, "delgado (Alex)" if self.modelo.current() == 1 else "clásico (Steve)"))
        self.lbl_info.configure(text="Añadida al pack (%d skins)." % len(self.pack))

    def pack_quitar(self):
        sel = list(self.lista.curselection())
        for i in reversed(sel):
            self.lista.delete(i)
            del self.pack[i]

    def pack_guardar(self):
        if not self.pack:
            messagebox.showinfo("Pack vacío", "Añade al menos una skin con «Añadir la convertida al pack».")
            return
        ruta = filedialog.asksaveasfilename(title="Guardar el pack de skins", defaultextension=".mcpack",
                                            initialfile="mis_skins_expresiones.mcpack",
                                            filetypes=[("Pack de skins de Minecraft", "*.mcpack")])
        if not ruta:
            return
        try:
            cas.pack_mcpack(self.pack, ruta, nombre_pack="Mis skins con expresiones",
                            nombre_fichero=os.path.splitext(os.path.basename(ruta))[0])
        except Exception as exc:
            messagebox.showerror("No he podido crear el pack", str(exc))
            return
        self.lbl_info.configure(text="Pack guardado: %s — ábrelo con Minecraft (doble clic)." % ruta)


# ============================================================================
#  Arranque (y modo de autoprueba sin ventana visible)
# ============================================================================

def autoprueba(rutas):
    """Comprueba que la ventana se construye, carga skins y genera los archivos."""
    raiz = tk.Tk()
    raiz.withdraw()
    app = App(raiz)
    salida = "/tmp/prueba_gui"
    os.makedirs(salida, exist_ok=True)
    ok = 0
    for ruta in rutas:
        app.abrir(ruta)
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        # todas las opciones y todos los estados de la simulación
        for ajuste in ("sorpresa", "simple", "sombrero", "limpiar", "ajustar"):
            app.var[ajuste].set(True)
            app.refrescar()
        for valor, _ in ESTADOS:
            app.estado.set(valor)
            app.refrescar()
        app.var["simple"].set(False)
        app.combo_ojo.current(3)      # un tipo de ojo forzado
        app.combo_ceja.current(2)
        app.var_col["pupila"].set(True)
        app.refrescar()
        if not app.png_out:                      # skin sin ojos/cejas detectables
            print("  %-24s sin detección (se salta)" % os.path.basename(ruta))
            continue
        with open(os.path.join(salida, nombre + "_gui.png"), "wb") as fh:
            fh.write(app.png_out)
        app.pack_add()
        print("  %-24s textura %5d bytes · informe %4d caracteres · cubos: %s"
              % (os.path.basename(ruta), len(app.png_out), len(app.texto.get("1.0", "end")),
                 " · ".join(app.res["stats"]["slotList"]) or "ninguno"))
        ok += 1
    if app.pack:
        ruta_pack = os.path.join(salida, "prueba_gui.mcpack")
        cas.pack_mcpack(app.pack, ruta_pack, "Prueba GUI")
        print("  pack: %s (%d skins, %d bytes)" % (ruta_pack, len(app.pack), os.path.getsize(ruta_pack)))
    raiz.destroy()
    return 0 if ok else 1


def main(argv):
    rutas = [a for a in argv[1:] if not a.startswith("-")]
    estado = None
    if "--estado" in argv:
        i = argv.index("--estado")
        if i + 1 < len(argv):
            estado = argv[i + 1]
            rutas = [r for r in rutas if r != estado]
    if "--autoprueba" in argv:
        return autoprueba(rutas or ["/home/user/ref/ex/10_cole.png"])
    raiz = tk.Tk()
    app = App(raiz, rutas[0] if rutas else None)
    if estado:
        app.estado.set(estado)
        app.refrescar()
    raiz.mainloop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
