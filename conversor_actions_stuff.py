#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor de skins  ->  Actions & Stuff Expresiones   ·   versión Python (script único)
=========================================================================================

Convierte una skin de Minecraft (PNG 64x64, modelo clásico o delgado) en una skin
compatible con el addon **Actions & Stuff — Expresiones** (Oreville Studios, 1.5 / 1.10 / 1.11).

Es el MISMO motor que el HTML (mismas reglas, mismos datos de la plantilla oficial),
pero en un solo archivo de Python y sin dependencias: sólo la biblioteca estándar
(lee y escribe PNG a mano con zlib, y arma el .mcpack con zipfile).

QUÉ ESCRIBE EN LA SKIN
----------------------
  · backFace  (x24-31, y0-7) : la cara sin pupila (rellena de esclerótica) y sin cejas.
  · blinkFace (x0-7,   y0-7) : la cara con la ceja bajada 1 píxel y el ojo cerrado.
  · cubos de ojos y cejas    : los cubos de la plantilla que coinciden con el dibujo.

USO RÁPIDO
----------
    python conversor_actions_stuff.py mi_skin.png
        -> mi_skin_as.png   (esa es la que se sube a Minecraft)

    python conversor_actions_stuff.py mi_skin.png --info
        -> además, el informe completo (qué ha detectado y qué ha pintado)

    python conversor_actions_stuff.py *.png -d salida/ --pack mis_skins.mcpack
        -> convierte varias y arma un pack de skins (.mcpack) listo para abrir con Minecraft

OPCIONES
--------
    --ojo ESTILO / --ceja ESTILO   fuerza un tipo (mira `--estilos` para la lista)
    --sin-sorpresa                 no añade la fila de esclerótica sobre el ojo en la cara trasera
    --simple                       parpadeo sencillo (todo el ojo con el color del párpado)
    --sombrero                     copia la cara tal como se ve en Minecraft (cara + capa de sombrero)
    --no-limpiar                   no borra el arte anterior de las zonas de los cubos
    --no-ajustar                   no ajusta a la plantilla si el ojo no encaja en ninguna variante
    --color-ojos HEX --color-cejas HEX --color-esclerotica HEX --color-parpado HEX
    --color-cubos HEX              pinta los cubos con un color fijo (si tu skin no tiene dibujados los ojos)
    --info / --json                informe legible / informe en JSON
    --pack ARCHIVO.mcpack          empaqueta todo lo convertido como pack de skins de Bedrock
    --estilos                      lista los tipos de ojo y ceja de la plantilla oficial

Se puede usar como módulo:

    import conversor_actions_stuff as cas
    png_salida, informe = cas.convertir_bytes(png_entrada, sorpresa=True)

Después, en Minecraft: Ajustes -> Perfil -> Skins -> Subir skin.
Y en el addon: Create Character -> Modelo clásico -> Owned Skins (PC / Bedrock 1.21.90+).
Si en el juego no pestañea: A&S 1.5+, y en Ajustes -> Recursos -> Actions & Stuff -> ⚙️
«Enable Expressions» activado, con Vibrant Visuals desactivado.

Autor: hecho a partir de la plantilla oficial «Actions & Stuff Expressions Template.geo.bbmodel».
Este script no está afiliado a Oreville Studios ni a Mojang.
Licencia: úsalo y modifícalo como quieras.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys
import unicodedata
import uuid as _uuid
import zipfile
import zlib

__version__ = "1.0"
VERSION_HTML = "final (compatible con A&S 1.5 / 1.10 / 1.11)"

# ============================================================================
#  1. Leer y escribir PNG (sólo biblioteca estándar)
# ============================================================================

_PNG_FIRMA = b"\x89PNG\r\n\x1a\n"


def _desfiltrar(bruto: bytes, alto: int, ancho: int, bpp: int) -> bytearray:
    """Deshace los filtros por fila del PNG (tipos 0-4)."""
    fila_bytes = ancho * bpp
    salida = bytearray(alto * fila_bytes)
    pos = 0
    for y in range(alto):
        if pos >= len(bruto):
            raise ValueError("PNG incompleto")
        ft = bruto[pos]
        pos += 1
        fila = bytearray(bruto[pos:pos + fila_bytes])
        if len(fila) < fila_bytes:
            raise ValueError("PNG incompleto")
        pos += fila_bytes
        off = y * fila_bytes
        previa = salida[off - fila_bytes:off] if y else bytearray(fila_bytes)
        if ft == 0:
            pass
        elif ft == 1:
            for i in range(bpp, fila_bytes):
                fila[i] = (fila[i] + fila[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(fila_bytes):
                fila[i] = (fila[i] + previa[i]) & 0xFF
        elif ft == 3:
            for i in range(fila_bytes):
                izq = fila[i - bpp] if i >= bpp else 0
                fila[i] = (fila[i] + ((izq + previa[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(fila_bytes):
                a = fila[i - bpp] if i >= bpp else 0
                b = previa[i]
                c = previa[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                fila[i] = (fila[i] + pr) & 0xFF
        else:
            raise ValueError("filtro PNG desconocido: %d" % ft)
        salida[off:off + fila_bytes] = fila
    return salida


def leer_png(datos: bytes):
    """Devuelve (ancho, alto, bytearray RGBA). Soporta los PNG habituales de skins."""
    if datos[:8] != _PNG_FIRMA:
        raise ValueError("esto no es un PNG")
    pos = 8
    ancho = alto = profundidad = tipo = None
    paleta = b""
    trns = b""
    trozos = []
    while pos + 8 <= len(datos):
        largo, clase = struct.unpack(">I4s", datos[pos:pos + 8])
        cuerpo = datos[pos + 8:pos + 8 + largo]
        pos += 12 + largo
        if clase == b"IHDR":
            ancho, alto, profundidad, tipo, comp, filtro, entrelazado = struct.unpack(">IIBBBBB", cuerpo)
            if profundidad == 16:
                profundidad = 16
            if entrelazado:
                raise ValueError("PNG entrelazado (Adam7): no soportado, guárdalo sin entrelazar")
        elif clase == b"PLTE":
            paleta = cuerpo
        elif clase == b"tRNS":
            trns = cuerpo
        elif clase == b"IDAT":
            trozos.append(cuerpo)
        elif clase == b"IEND":
            break
    if ancho is None:
        raise ValueError("PNG sin cabecera IHDR")

    bruto = zlib.decompress(b"".join(trozos))

    def canales(t):
        return {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[t]

    if tipo not in (0, 2, 3, 4, 6):
        raise ValueError("tipo de color PNG %d no soportado" % tipo)
    if tipo == 3 and profundidad in (1, 2, 4):
        bpp_bits = profundidad
    elif tipo in (0, 3) and profundidad in (1, 2, 4):
        bpp_bits = profundidad
    else:
        bpp_bits = profundidad * canales(tipo)
    bpp = max(1, bpp_bits // 8)
    filas = _desfiltrar(bruto, alto, ancho, bpp)

    # ---- a RGBA de 8 bits
    rgba = bytearray(ancho * alto * 4)
    if tipo in (0, 4):
        paso = 2 if profundidad == 16 else 1
        ch = canales(tipo)
        for y in range(alto):
            base = y * ancho * ch * paso
            for x in range(ancho):
                i = base + x * ch * paso
                if profundidad == 16:
                    g = filas[i]
                else:
                    g = filas[i]
                o = (y * ancho + x) * 4
                rgba[o] = rgba[o + 1] = rgba[o + 2] = g
                rgba[o + 3] = filas[i + paso] if ch == 2 else 255
        return ancho, alto, rgba
    if tipo in (2, 6):
        ch = canales(tipo)
        paso = 2 if profundidad == 16 else 1
        for y in range(alto):
            base = y * ancho * ch * paso
            for x in range(ancho):
                i = base + x * ch * paso
                o = (y * ancho + x) * 4
                rgba[o] = filas[i]
                rgba[o + 1] = filas[i + paso]
                rgba[o + 2] = filas[i + 2 * paso]
                rgba[o + 3] = filas[i + 3 * paso] if ch == 4 else 255
        return ancho, alto, rgba

    # índice de paleta (con o sin transparencia); profundidades 1/2/4/8
    colores = [(paleta[i], paleta[i + 1], paleta[i + 2],
                (trns[i] if i < len(trns) else 255)) for i in range(0, len(paleta), 3)]
    mascara = (1 << profundidad) - 1
    por_fila = (ancho * profundidad + 7) // 8
    for y in range(alto):
        base = y * por_fila
        for x in range(ancho):
            if profundidad == 8:
                idx = filas[base + x]
            else:
                bit = x * profundidad
                byte = filas[base + (bit >> 3)]
                des = 8 - profundidad - (bit & 7)
                idx = (byte >> des) & mascara
            r, g, b, a = colores[idx] if idx < len(colores) else (0, 0, 0, 0)
            o = (y * ancho + x) * 4
            rgba[o], rgba[o + 1], rgba[o + 2], rgba[o + 3] = r, g, b, a
    return ancho, alto, rgba


def escribir_png(ancho: int, alto: int, rgba) -> bytes:
    """PNG RGBA de 8 bits, sin entrelazar (compatible con Minecraft y con todo)."""
    filas = bytearray()
    for y in range(alto):
        filas.append(0)
        off = y * ancho * 4
        filas += rgba[off:off + ancho * 4]

    def trozo(clase: bytes, datos: bytes) -> bytes:
        return (struct.pack(">I", len(datos)) + clase + datos
                + struct.pack(">I", zlib.crc32(clase + datos) & 0xFFFFFFFF))

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    return (_PNG_FIRMA + trozo(b"IHDR", cabecera)
            + trozo(b"IDAT", zlib.compress(bytes(filas), 9)) + trozo(b"IEND", b""))


# ============================================================================
#  2. Datos de la plantilla oficial (los 74 cubos del .bbmodel)
# ============================================================================

_DATOS = json.loads(r"""{"CUBES":{"eye":[{"style":"1x1","side":"L","rect":[43,16,44,17],"cells":[[5,4]]},{"style":"1x1","side":"L","rect":[43,17,44,18],"cells":[[5,5]]},{"style":"1x1","side":"L","rect":[43,18,44,19],"cells":[[6,4]]},{"style":"1x1","side":"L","rect":[43,19,44,20],"cells":[[6,5]]},{"style":"1x2","side":"L","rect":[3,18,4,20],"cells":[[6,3],[6,4]]},{"style":"1x2","side":"L","rect":[53,16,54,18],"cells":[[6,4],[6,5]]},{"style":"1x2","side":"L","rect":[55,16,56,18],"cells":[[6,5],[6,6]]},{"style":"2x1","side":"L","rect":[19,32,20,33],"cells":[[5,2]]},{"style":"2x1","side":"L","rect":[19,33,20,34],"cells":[[5,3]]},{"style":"2x1","side":"L","rect":[17,35,18,36],"cells":[[5,4]]},{"style":"2x1","side":"L","rect":[19,35,20,36],"cells":[[5,5]]},{"style":"2x1","side":"L","rect":[41,32,42,33],"cells":[[5,6]]},{"style":"2x3","side":"L","rect":[1,16,2,18],"cells":[[5,3],[5,4]]},{"style":"2x3","side":"L","rect":[1,18,2,20],"cells":[[5,4],[5,5]]},{"style":"2x3","side":"L","rect":[3,16,4,18],"cells":[[5,5],[5,6]]},{"style":"3x1","side":"L","rect":[19,16,20,17],"cells":[[5,4]]},{"style":"3x1","side":"L","rect":[19,17,20,18],"cells":[[5,5]]},{"style":"3x2","side":"L","rect":[2,32,4,34],"cells":[[5,3],[6,3],[5,4],[6,4]]},{"style":"3x2","side":"L","rect":[2,34,4,36],"cells":[[5,4],[6,4],[5,5],[6,5]]},{"style":"3x2","side":"L","rect":[38,32,40,34],"cells":[[5,5],[6,5],[5,6],[6,6]]},{"style":"Middle 3x1","side":"L","rect":[19,18,20,19],"cells":[[6,4]]},{"style":"Middle 3x1","side":"L","rect":[19,19,20,20],"cells":[[6,5]]},{"style":"1x1","side":"R","rect":[42,16,43,17],"cells":[[2,4]]},{"style":"1x1","side":"R","rect":[42,17,43,18],"cells":[[2,5]]},{"style":"1x1","side":"R","rect":[42,18,43,19],"cells":[[1,4]]},{"style":"1x1","side":"R","rect":[42,19,43,20],"cells":[[1,5]]},{"style":"1x2","side":"R","rect":[2,18,3,20],"cells":[[1,3],[1,4]]},{"style":"1x2","side":"R","rect":[52,16,53,18],"cells":[[1,4],[1,5]]},{"style":"1x2","side":"R","rect":[54,16,55,18],"cells":[[1,5],[1,6]]},{"style":"2x1","side":"R","rect":[18,32,19,33],"cells":[[2,2]]},{"style":"2x1","side":"R","rect":[18,33,19,34],"cells":[[2,3]]},{"style":"2x1","side":"R","rect":[16,35,17,36],"cells":[[2,4]]},{"style":"2x1","side":"R","rect":[18,35,19,36],"cells":[[2,5]]},{"style":"2x1","side":"R","rect":[40,32,41,33],"cells":[[2,6]]},{"style":"2x3","side":"R","rect":[0,16,1,18],"cells":[[2,3],[2,4]]},{"style":"2x3","side":"R","rect":[0,18,1,20],"cells":[[2,4],[2,5]]},{"style":"2x3","side":"R","rect":[2,16,3,18],"cells":[[2,5],[2,6]]},{"style":"3x1","side":"R","rect":[18,16,19,17],"cells":[[2,4]]},{"style":"3x1","side":"R","rect":[18,17,19,18],"cells":[[2,5]]},{"style":"3x2","side":"R","rect":[0,32,2,34],"cells":[[1,3],[2,3],[1,4],[2,4]]},{"style":"3x2","side":"R","rect":[0,34,2,36],"cells":[[1,4],[2,4],[1,5],[2,5]]},{"style":"3x2","side":"R","rect":[36,32,38,34],"cells":[[1,5],[2,5],[1,6],[2,6]]},{"style":"Middle 3x1","side":"R","rect":[18,18,19,19],"cells":[[1,4]]},{"style":"Middle 3x1","side":"R","rect":[18,19,19,20],"cells":[[1,5]]}],"brow":[{"style":"2x1 1","side":"L","rect":[52,18,54,19],"cells":[[1,1],[2,1]]},{"style":"2x1 2","side":"L","rect":[52,19,54,20],"cells":[[1,2],[2,2]]},{"style":"2x1 3","side":"L","rect":[12,34,14,35],"cells":[[1,3],[2,3]]},{"style":"2x1 4","side":"L","rect":[12,35,14,36],"cells":[[1,4],[2,4]]},{"style":"2x1 5","side":"L","rect":[16,34,18,35],"cells":[[1,5],[2,5]]},{"style":"3x1 1","side":"L","rect":[36,17,39,18],"cells":[[0,1],[1,1],[2,1]]},{"style":"3x1 2","side":"L","rect":[36,18,39,19],"cells":[[0,2],[1,2],[2,2]]},{"style":"3x1 3","side":"L","rect":[36,19,39,20],"cells":[[0,3],[1,3],[2,3]]},{"style":"3x1 4","side":"L","rect":[12,32,15,33],"cells":[[0,4],[1,4],[2,4]]},{"style":"3x1 5","side":"L","rect":[12,33,15,34],"cells":[[0,5],[1,5],[2,5]]},{"style":"2x1 1","side":"R","rect":[54,18,56,19],"cells":[[5,1],[6,1]]},{"style":"2x1 2","side":"R","rect":[54,19,56,20],"cells":[[5,2],[6,2]]},{"style":"2x1 3","side":"R","rect":[14,34,16,35],"cells":[[5,3],[6,3]]},{"style":"2x1 4","side":"R","rect":[14,35,16,36],"cells":[[5,4],[6,4]]},{"style":"2x1 5","side":"R","rect":[18,34,20,35],"cells":[[5,5],[6,5]]},{"style":"3x1 1","side":"R","rect":[39,17,42,18],"cells":[[5,1],[6,1],[7,1]]},{"style":"3x1 2","side":"R","rect":[39,18,42,19],"cells":[[5,2],[6,2],[7,2]]},{"style":"3x1 3","side":"R","rect":[39,19,42,20],"cells":[[5,3],[6,3],[7,3]]},{"style":"3x1 4","side":"R","rect":[15,32,18,33],"cells":[[5,4],[6,4],[7,4]]},{"style":"3x1 5","side":"R","rect":[15,33,18,34],"cells":[[5,5],[6,5],[7,5]]},{"style":"Monobrow","side":"L","rect":[12,16,15,17],"cells":[[1,1],[2,1],[3,1]]},{"style":"Monobrow","side":"L","rect":[12,17,15,18],"cells":[[1,2],[2,2],[3,2]]},{"style":"Monobrow","side":"L","rect":[12,18,15,19],"cells":[[1,3],[2,3],[3,3]]},{"style":"Monobrow","side":"L","rect":[12,19,15,20],"cells":[[1,4],[2,4],[3,4]]},{"style":"Monobrow","side":"L","rect":[36,16,39,17],"cells":[[1,5],[2,5],[3,5]]},{"style":"Monobrow","side":"R","rect":[15,16,18,17],"cells":[[4,1],[5,1],[6,1]]},{"style":"Monobrow","side":"R","rect":[15,17,18,18],"cells":[[4,2],[5,2],[6,2]]},{"style":"Monobrow","side":"R","rect":[15,18,18,19],"cells":[[4,3],[5,3],[6,3]]},{"style":"Monobrow","side":"R","rect":[15,19,18,20],"cells":[[4,4],[5,4],[6,4]]},{"style":"Monobrow","side":"R","rect":[39,16,42,17],"cells":[[4,5],[5,5],[6,5]]}]},"eyeStyles":["1x1","1x2","2x1","Middle 3x1","2x3","3x1","3x2"],"browStyles":["Monobrow","2x1","3x1"]}""")

CUBES = _DATOS["CUBES"]
EYE_STYLES = _DATOS["eyeStyles"]
BROW_STYLES = _DATOS["browStyles"]


# ============================================================================
#  3. Utilidades (mismas cuentas que la versión del navegador)
# ============================================================================

def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def sat(c):
    mx, mn = max(c[0], c[1], c[2]), min(c[0], c[1], c[2])
    return 0 if mx == 0 else (mx - mn) / mx


def dist(a, b):
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt(dr * dr + dg * dg + db * db)


def rgb_texto(c):
    return "#%02x%02x%02x" % (int(c[0]), int(c[1]), int(c[2]))


def hex2rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


def modo(lista):
    """Color más repetido (en empate, el primero que apareció, como en el HTML)."""
    cuenta, mejor, n_mejor = {}, None, 0
    for c in lista:
        k = (c[0], c[1], c[2])
        n = cuenta.get(k, 0) + 1
        cuenta[k] = n
        if n > n_mejor:
            n_mejor, mejor = n, [c[0], c[1], c[2]]
    return mejor if mejor is not None else [0, 0, 0]


def oscurecer(c, f):
    return [int(round(c[0] * f)), int(round(c[1] * f)), int(round(c[2] * f))]


def _clave(x, y):
    return y * 8 + x


def uniq(lista):
    fuera = []
    for v in lista:
        if v not in fuera:
            fuera.append(v)
    return fuera


# ============================================================================
#  4. Detector de ojos y cejas (analyzeFace)
# ============================================================================

def analizar_cara(face, expandir=True, solo_deteccion=False):
    """face: 8x8 RGBA (bytearray/list de 256). Devuelve el dict de detección o None.

    Se prueba primero con el color de piel de siempre (el más repetido en el centro
    bajo de la cara).  Si así no hay ojos, se reintenta con otros colores candidatos:
    hay skins (por ejemplo, caras de lobo con morro claro, u ojos negros con pupila
    de color) en las que ese primer color es el morro y no el pelaje, y entonces todo
    lo demás se clasificaba mal y la skin se rechazaba.
    """
    def px(x, y):
        i = (y * 8 + x) * 4
        return [face[i], face[i + 1], face[i + 2], face[i + 3]]

    def modo_en(r0, r1, c0, c1):
        l = []
        for y in range(r0, r1):
            for x in range(c0, c1):
                c = px(x, y)
                if c[3] > 0:
                    l.append(c)
        return modo(l) if l else None

    candidatos = []

    def prueba(color, fuente=None, n=0):
        r = _analizar_con_piel(face, color, expandir=expandir, px=px, modo_en=modo_en,
                               solo_deteccion=solo_deteccion, estricto=(n > 0))
        if r is not None and fuente:
            r["notes"].append("El color de piel se ha tomado de %s: el centro de la cara lo ocupaba otro "
                              "color (un morro u otro detalle)." % fuente)
        return r

    base = modo_en(4, 7, 2, 6) or modo_en(5, 8, 1, 7) or modo_en(0, 8, 0, 8)
    if not base:
        return None
    candidatos.append(base)
    # candidatos de reserva: la fila de arriba (pelo/pelaje) y los colores más usados
    for c in [modo_en(0, 1, 0, 8), modo_en(0, 2, 0, 8)] + modo_en_lista(0, 8, 0, 8, px):
        if c and c not in candidatos:
            candidatos.append(c)
    resultado = None
    for n, color in enumerate(candidatos):
        r = prueba(color, None if n == 0 else ("la zona de arriba" if n <= 2 else "el color dominante de la cara"), n)
        if r is not None:
            resultado = r
            break
    return resultado


def modo_en_lista(r0, r1, c0, c1, px):
    """Colores de una zona, de más a menos usados (para probar candidatos de piel)."""
    from collections import Counter
    cuenta = Counter()
    for y in range(r0, r1):
        for x in range(c0, c1):
            c = px(x, y)
            if c[3] > 0:
                cuenta[(c[0], c[1], c[2], c[3])] += 1
    return [list(c) for c, _ in cuenta.most_common(6)]


def _analizar_con_piel(face, skin, expandir=True, px=None, modo_en=None, solo_deteccion=False,
                       estricto=False):
    """El detector de siempre, con un color de piel ya decidido.

    «estricto» se usa en los reintentos: sólo se aceptan pares de ojos pequeños y
    exactamente simétricos (2 a 6 píxeles cada uno, de 3x3 como mucho) y no se
    amplía la caja.  Así una skin que antes se rechazaba no se acepta a medias.
    """
    sl, ss = lum(skin), sat(skin)

    def tinta(c):
        return c[3] == 0 or dist(c, skin) > 85 or (dist(c, skin) > 32 and lum(c) < sl - 25)

    def tinta_ceja(c):
        return c[3] == 0 or dist(c, skin) > 85 or (dist(c, skin) > 45 and lum(c) < sl - 55)

    def esclerotica(c):
        return c[3] > 0 and lum(c) > 185 and dist(c, skin) > 60

    def pupila(c):
        return c[3] > 0 and not esclerotica(c) and tinta(c) and (lum(c) < 115 or sat(c) > ss + 0.12)

    def componentes(pred):
        pts = {}
        for y in range(1, 7):
            for x in range(0, 8):
                if pred(px(x, y)):
                    pts[_clave(x, y)] = (x, y)
        fuera = []
        for k in list(pts.keys()):
            if pts.get(k) is None:
                continue
            semilla = pts[k]
            comp, pila = [semilla], [semilla]
            pts[k] = None
            while pila:
                q = pila.pop()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = q[0] + dx, q[1] + dy
                        kk = _clave(nx, ny)
                        if 0 <= nx <= 7 and 0 <= ny <= 7 and pts.get(kk):
                            n = pts[kk]
                            pts[kk] = None
                            pila.append(n)
                            comp.append(n)
            xs = [c[0] for c in comp]
            ys = [c[1] for c in comp]
            fuera.append({"cells": comp, "box": [min(xs), min(ys), max(xs), max(ys)], "n": len(comp)})
        return fuera

    def mitad(cells):
        return "R" if (sum(c[0] for c in cells) / len(cells)) < 3.5 else "L"

    def nota_pareja(A, B):
        mir = [7 - B["box"][2], 7 - B["box"][0]]
        pen = (abs(mir[0] - A["box"][0]) + abs(mir[1] - A["box"][2])
               + abs(A["box"][1] - B["box"][1]) + abs(A["box"][3] - B["box"][3]))
        pen_fila = min(abs(A["box"][1] - 4), abs(A["box"][1] - 3)) * 4
        ancho = (A["box"][2] - A["box"][0] + 1) + (B["box"][2] - B["box"][0] + 1)
        return pen * 6 + abs(A["n"] - B["n"]) * 2 + pen_fila + max(0, ancho - 4) * 6

    ancla, fuente = None, None
    for grupo, tope, nombre in ((componentes(esclerotica), 16, "esclerótica"),
                                (componentes(pupila), 20, "pupila")):
        if ancla:
            break
        mejor = None
        for A in grupo:
            for B in grupo:
                if A is B or mitad(A["cells"]) == mitad(B["cells"]):
                    continue
                s = nota_pareja(A, B)
                if mejor is None or s < mejor[0]:
                    mejor = [s, A, B]
        if mejor and mejor[0] <= tope:
            ancla, fuente = [mejor[1], mejor[2]], nombre
    if not ancla:
        return None
    if estricto:
        A, B = ancla
        if not (2 <= A["n"] <= 6 and A["n"] == B["n"]):
            return None
        for C in (A, B):
            bx = C["box"]
            if bx[2] - bx[0] > 2 or bx[3] - bx[1] > 2:
                return None
        # los dos ojos tienen que ser exactamente simétricos
        espejo = set((7 - c[0], c[1]) for c in A["cells"])
        if espejo != set(tuple(c) for c in B["cells"]):
            return None

    ojos = {}
    for A in ancla:
        ojos[mitad(A["cells"])] = A
    if "R" not in ojos or "L" not in ojos:
        return None

    salida = {"skin": skin, "eyes": {}, "brows": {}, "notes": [], "anchor": fuente}
    fallo = False
    for tag in ("R", "L"):
        A = ojos[tag]
        axs = [list(c) for c in A["cells"]]
        x0, y0, x1, y1 = A["box"]
        alo, ahi = (1, 3) if tag == "R" else (4, 6)
        for _ in range(2):
            if x0 > alo and pupila(px(x0 - 1, min(y1, 5))) and (x1 - x0) < 3:
                x0 -= 1
            if x1 < ahi and pupila(px(x1 + 1, min(y1, 5))) and (x1 - x0) < 3:
                x1 += 1
        cols = list(range(x0, x1 + 1))
        filas_ojo = [c[1] for c in axs]
        pupilas = {}
        for c in axs:
            if pupila(px(c[0], c[1])):
                pupilas[_clave(c[0], c[1])] = c
        for yy in filas_ojo:
            for xx in cols:
                if pupila(px(xx, yy)):
                    pupilas[_clave(xx, yy)] = [xx, yy]
        lista = [pupilas[k] for k in pupilas]
        for dir_ in (-1, 1):
            if not lista:
                continue
            filas = [c[1] for c in lista]
            nr = (max(filas) if dir_ > 0 else min(filas)) + dir_
            if nr < 0 or nr > 7:
                continue
            ext = [xx for xx in cols if pupila(px(xx, nr))]
            if not ext:
                continue
            interior = len([xx for xx in cols if pupila(px(xx, nr - dir_))])
            if len(ext) > interior:
                continue
            if (x0 > 0 and pupila(px(x0 - 1, nr))) or (x1 < 7 and pupila(px(x1 + 1, nr))):
                continue
            for xx in ext:
                lista.append([xx, nr])
        lista = [c for c in lista if c[0] not in (0, 3, 4, 7)]
        if not lista:
            fallo = True
            continue
        xs = [c[0] for c in axs + lista]
        ys = [c[1] for c in axs + lista]
        salida["eyes"][tag] = {"box": [min(xs), min(ys), max(xs), max(ys)],
                               "pupils": lista, "sclera": axs}
    if fallo or "R" not in salida["eyes"] or "L" not in salida["eyes"]:
        return None

    # --- ampliar la caja del ojo sobre píxeles claros contiguos (ojos tipo "bloque")
    if expandir and not estricto:
        for tag in ("R", "L"):
            e = salida["eyes"][tag]
            lo, hi = (0, 3) if tag == "R" else (4, 7)
            lim = sl + 25
            for _ in range(3):
                b = e["box"]
                crecio = False
                for y in range(max(0, b[1] - 1), min(7, b[3] + 1) + 1):
                    for x in range(max(lo, b[0] - 1), min(hi, b[2] + 1) + 1):
                        if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                            continue
                        c = px(x, y)
                        if c[3] > 0 and lum(c) > lim and not any(p[0] == x and p[1] == y for p in e["pupils"]):
                            e["box"] = [min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)]
                            b = e["box"]
                            crecio = True
                if not crecio:
                    break

    # --- cejas: primera fila con tinta encima de la caja del ojo
    for tag in ("R", "L"):
        e = salida["eyes"][tag]
        b = e["box"]
        lo, hi = (0, 3) if tag == "R" else (4, 7)
        scol = px(e["sclera"][0][0], e["sclera"][0][1]) if e["sclera"] else None
        encontrado = None
        for dy in range(1, 4):
            if encontrado:
                break
            yy = b[1] - dy
            if yy < 0:
                break
            xs = []
            for x in range(max(lo, b[0] - 1), min(hi, b[2] + 1) + 1):
                c = px(x, yy)
                if tinta_ceja(c) and not esclerotica(c):
                    xs.append(x)
            if not xs:
                continue
            semilla = modo([px(x, yy) for x in xs])
            xs = [x for x in xs if dist(px(x, yy), semilla) < 45]
            if not xs:
                continue

            def igual(x):
                return (tinta_ceja(px(x, yy)) and not esclerotica(px(x, yy))
                        and dist(px(x, yy), semilla) < 45)

            while min(xs) > lo and igual(min(xs) - 1) and (max(xs) - min(xs)) < 3:
                xs.append(min(xs) - 1)
            while max(xs) < hi and igual(max(xs) + 1) and (max(xs) - min(xs)) < 3:
                xs.append(max(xs) + 1)
            banda = len([bx for bx in range(8) if dist(px(bx, yy), semilla) < 20])
            if banda >= 7:
                break
            if scol and dist(px(min(xs), yy), scol) < 30:
                break
            encontrado = {"y": yy, "xs": xs}
        salida["brows"][tag] = ({"cells": [[x, encontrado["y"]] for x in encontrado["xs"]],
                                 "y": encontrado["y"]} if encontrado else None)

    notas = salida["notes"]
    conf = "alta"
    if not salida["brows"]["R"] and not salida["brows"]["L"]:
        conf = "media"
        notas.append("No se han detectado cejas (puedes marcarlas a mano).")
    if salida["eyes"]["R"]["box"][1] < 1 or salida["eyes"]["R"]["box"][3] > 6:
        conf = "media"
        notas.append("Los ojos están en una posición poco habitual.")
    if not salida["eyes"]["R"]["sclera"] and not salida["eyes"]["L"]["sclera"]:
        conf = "media"
        notas.append("El ojo no tiene zona clara: el relleno usará el color del contorno del ojo o el de la piel.")
    if salida["anchor"] == "pupila":
        notas.append("Ojos localizados por el color de la pupila (no había zona clara).")
    salida["confidence"] = conf
    return salida


# ============================================================================
#  5. Cara, sombrero y paleta
# ============================================================================

def cara_de(src):
    """Saca la cara (x8-15, y8-15) como 8x8 RGBA."""
    f = bytearray(8 * 8 * 4)
    for y in range(8):
        for x in range(8):
            si = ((y + 8) * 64 + (x + 8)) * 4
            di = (y * 8 + x) * 4
            f[di:di + 4] = src[si:si + 4]
    return f


def sombrero_de(src):
    """Capa de sombrero (x40-47, y8-15) como 8x8 RGBA."""
    f = bytearray(8 * 8 * 4)
    for y in range(8):
        for x in range(8):
            si = ((y + 8) * 64 + (x + 40)) * 4
            di = (y * 8 + x) * 4
            f[di:di + 4] = src[si:si + 4]
    return f


def sombrero_stats(sombrero):
    total = en_ojos = 0
    for y in range(8):
        for x in range(8):
            if not sombrero[(y * 8 + x) * 4 + 3]:
                continue
            total += 1
            if 3 <= y <= 6:
                en_ojos += 1
    return {"total": total, "enOjos": en_ojos}


def paleta_para(face, det):
    def px(x, y):
        i = (y * 8 + x) * 4
        return [face[i], face[i + 1], face[i + 2], face[i + 3]]

    p = {"skin": list(det["skin"]), "perEye": {}}
    for t in ("R", "L"):
        e, b = det["eyes"].get(t), det["brows"].get(t)
        if not e or not e["box"]:
            continue
        pupilas = e["pupils"]
        fondo = []
        for y in range(e["box"][1], e["box"][3] + 1):
            for x in range(e["box"][0], e["box"][2] + 1):
                if not any(c[0] == x and c[1] == y for c in pupilas):
                    fondo.append(px(x, y))
        filas = {}
        for yy in range(e["box"][1], e["box"][3] + 1):
            col = []
            for xx in range(e["box"][0], e["box"][2] + 1):
                if any(c[0] == xx and c[1] == yy for c in pupilas):
                    continue
                c = px(xx, yy)
                if c[3] > 0:
                    col.append(c)
            filas[yy] = modo(col) if col else None
        p["perEye"][t] = {
            "pupil": modo([px(c[0], c[1]) for c in pupilas]) if pupilas else oscurecer(det["skin"], 0.2),
            "sclera": modo(fondo) if fondo else list(det["skin"]),
            "scleraRows": filas,
            "brow": modo([px(c[0], c[1]) for c in b["cells"]]) if (b and b["cells"]) else None,
        }
    fila_baja = []
    for x in range(1, 7):
        c = px(x, 7)
        if c[3] > 0:
            fila_baja.append(c)
    barbilla = modo(fila_baja) if fila_baja else None
    mas_oscuro = sorted(fila_baja, key=lum)[0] if fila_baja else None
    if mas_oscuro and lum(mas_oscuro) < lum(det["skin"]) - 15:
        p["lid"] = list(mas_oscuro)
    elif barbilla and lum(barbilla) < lum(det["skin"]) - 15:
        p["lid"] = list(barbilla)
    else:
        p["lid"] = oscurecer(det["skin"], 0.62)
    return p


# ============================================================================
#  6. Encajar el dibujo en los cubos de la plantilla
# ============================================================================

def plan_celdas(cells, kind, solo_estilo=None):
    """Primero los cubos grandes que quepan enteros en el dibujo, después los pequeños."""
    want = {_clave(c[0], c[1]): 0 for c in cells}
    pool = [cu for cu in CUBES[kind]
            if (not solo_estilo or cu["style"] == solo_estilo
                or cu["style"].startswith(solo_estilo + " "))
            and all(_clave(c[0], c[1]) in want for c in cu["cells"])]
    pool = sorted(pool, key=lambda cu: -len(cu["cells"]))  # estable, como en el HTML
    cubos = []
    for cu in pool:
        if not all(want[_clave(c[0], c[1])] == 0 for c in cu["cells"]):
            continue
        for c in cu["cells"]:
            want[_clave(c[0], c[1])] = 1
        cubos.append(cu)
    faltan = [c for c in cells if not want[_clave(c[0], c[1])]]
    return {"cubes": cubos, "missing": faltan, "style": cubos[0]["style"] if cubos else None}


def cubo_mas_parecido(kind, cells, side, solo_estilo=None):
    """El cubo de la familia más parecida (tamaño y centro), para cuando no encaja ninguno."""
    lista = [cu for cu in CUBES[kind] if cu["side"] == side
             and (not solo_estilo or cu["style"] == solo_estilo
                  or cu["style"].startswith(solo_estilo + " "))]

    def centro(cs):
        return (sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs))

    a = centro(cells)
    mejor = None
    for cu in lista:
        b = centro(cu["cells"])
        d = abs(len(cu["cells"]) - len(cells)) * 10 + math.hypot(a[0] - b[0], a[1] - b[1])
        if mejor is None or d < mejor["d"]:
            mejor = {"cu": cu, "style": cu["style"], "d": d}
    return mejor


def plan_estilos(det, ojo=None, ceja=None, ajustar=True):
    plan = {"eye": [], "brow": []}
    for side in ("R", "L"):
        e = det["eyes"].get(side) or {"pupils": [], "box": None}
        pe = plan_celdas(e["pupils"], "eye", ojo)
        item = {"side": side, "cells": e["pupils"], "cubes": pe["cubes"],
                "missing": pe["missing"], "style": pe["style"]}
        if ajustar and not pe["cubes"] and e["pupils"]:
            m = cubo_mas_parecido("eye", e["pupils"], side, ojo)
            if m:
                item.update(cubes=[m["cu"]], style=m["style"], snapped=True, missing=[])
        plan["eye"].append(item)
        b = det["brows"].get(side)
        if b and b["cells"]:
            pb = plan_celdas(b["cells"], "brow", ceja)
            itb = {"side": side, "cells": b["cells"], "cubes": pb["cubes"],
                   "missing": pb["missing"], "style": pb["style"]}
            if ajustar and not pb["cubes"]:
                m = cubo_mas_parecido("brow", b["cells"], side, ceja)
                if m:
                    itb.update(cubes=[m["cu"]], style=m["style"], snapped=True, missing=[])
            plan["brow"].append(itb)
    return plan


# ============================================================================
#  7. Generador: escribe las capas en la skin
# ============================================================================

# ¿La zona (x0,y0) ya trae una cara de A&S dibujada?  Se considera que sí cuando
# está pintada (>= 56 de 64 píxeles opacos) Y se parece a la cara de la skin
# (>= 40 de 64 píxeles idénticos).  Con las 31 skins oficiales: parecidos de 46 a 62
# y todas pintadas; una zona vacía da 0.  (bufferfish trae el backFace sin pintar.)
def bajar_a_64(px, w):
    """Baja una imagen w×w (128 o 256) a 64×64 promediando bloques.

    El color se promedia ponderado por el alfa (un píxel transparente no arrastra a
    negro) y el alfa es la media simple.  Mismas cuentas que la versión del navegador,
    redondeando al par más cercano igual que un Uint8ClampedArray de JavaScript.
    """
    k = w // 64
    salida = bytearray(64 * 64 * 4)
    for y in range(64):
        for x in range(64):
            r = g = b = a = peso = 0
            for dy in range(k):
                for dx in range(k):
                    i = (((y * k + dy) * w) + (x * k + dx)) * 4
                    al = px[i + 3]
                    r += px[i] * al
                    g += px[i + 1] * al
                    b += px[i + 2] * al
                    peso += al
                    a += al
            j = (y * 64 + x) * 4
            if peso:
                salida[j] = round(r / peso)
                salida[j + 1] = round(g / peso)
                salida[j + 2] = round(b / peso)
            salida[j + 3] = round(a / (k * k))
    return bytes(salida)


def subir_de_64(bajo, w):
    """Amplía un 64×64 a w×w repitiendo cada píxel en bloques k×k."""
    k = w // 64
    if k == 1:
        return bytearray(bajo)
    salida = bytearray(w * w * 4)
    for y in range(64):
        for x in range(64):
            si = (y * 64 + x) * 4
            for dy in range(k):
                for dx in range(k):
                    di = (((y * k + dy) * w) + (x * k + dx)) * 4
                    salida[di:di + 4] = bajo[si:si + 4]
    return salida


def copiar_zona(hi, w, tx, ty, tw, th, destino):
    """Copia una zona (en texeles de 8×8) de la imagen original al resultado."""
    k = w // 64
    for y in range(th * k):
        for x in range(tw * k):
            i = (((ty * k) + y) * w) + (tx * k) + x
            j = i * 4
            destino[j:j + 4] = hi[j:j + 4]


def ya_tiene_capa(src, face, x0, y0, minimo=40):
    pintados = iguales = 0
    for y in range(8):
        for x in range(8):
            i = ((y0 + y) * 64 + (x0 + x)) * 4
            j = (y * 8 + x) * 4
            if src[i + 3] > 0:
                pintados += 1
            if src[i:i + 4] == face[j:j + 4]:
                iguales += 1
    return pintados >= 56 and iguales >= minimo, iguales


def generar_skin(src, det, **op):
    opt = {
        "surprised": True, "blinkStyle": "oficial", "combineHat": False,
        "cleanSlots": True, "snap": True, "slotColor": None,
        "scleraColor": None, "browColor": None, "pupilColor": None, "lidColor": None,
        "eyeStyle": None, "browStyle": None, "plan": None, "respetar": True, "minSame": None,
    }
    opt.update({k: v for k, v in op.items() if v is not None or k in ("slotColor", "scleraColor",
                                                                     "browColor", "pupilColor", "lidColor",
                                                                     "eyeStyle", "browStyle", "plan")})
    out = bytearray(src)
    face0 = cara_de(src)
    sombrero = sombrero_de(src)
    hat_info = sombrero_stats(sombrero)
    face = face0
    if opt["combineHat"]:
        face = bytearray(face0)
        for y in range(8):
            for x in range(8):
                i = (y * 8 + x) * 4
                if sombrero[i + 3]:
                    face[i:i + 4] = bytes(sombrero[i:i + 3]) + b"\xff"

    def px(x, y):
        i = (y * 8 + x) * 4
        return [face[i], face[i + 1], face[i + 2], face[i + 3]]

    pal = paleta_para(face, det)
    if opt["pupilColor"]:
        for t in ("R", "L"):
            if t in pal["perEye"]:
                pal["perEye"][t]["pupil"] = hex2rgb(opt["pupilColor"])
    if opt["browColor"]:
        for t in ("R", "L"):
            if t in pal["perEye"]:
                pal["perEye"][t]["brow"] = hex2rgb(opt["browColor"])
    if opt["scleraColor"]:
        sc = hex2rgb(opt["scleraColor"])
        for t in ("R", "L"):
            if t in pal["perEye"]:
                pal["perEye"][t]["sclera"] = sc
                pal["perEye"][t]["scleraRows"] = {}
    if opt["lidColor"]:
        pal["lid"] = hex2rgb(opt["lidColor"])

    log = []
    stats = {"back": 0, "blink": 0, "slots": 0, "cleaned": 0, "slotList": [], "missing": [],
             "unreachable": [], "hat": hat_info, "combineHat": bool(opt["combineHat"]),
             "blinkStyle": "simple" if opt["blinkStyle"] == "simple" else "oficial",
             "respetado": {"back": None, "blink": None}}

    def put(x, y, c):
        i = (y * 64 + x) * 4
        out[i], out[i + 1], out[i + 2], out[i + 3] = int(c[0]), int(c[1]), int(c[2]), 255

    def copiar_cara(ox, oy):
        for y in range(8):
            for x in range(8):
                put(ox + x, oy + y, px(x, y))

    # ---- 1. backFace (x24-31, y0-7)
    minimo = 40 if opt["minSame"] is None else opt["minSame"]
    cara_trasera_ok, parecido_back = ya_tiene_capa(src, face0, 24, 0, minimo)
    respetar_back = opt["respetar"] and cara_trasera_ok
    stats["respetado"]["back"] = bool(respetar_back)
    if not respetar_back:
        copiar_cara(24, 0)
        for t in ("R", "L"):
            e, pe = det["eyes"].get(t), pal["perEye"].get(t)
            if not e or not e["box"] or not pe:
                continue
            x0, x1 = e["box"][0], e["box"][2]
            top, bot = e["box"][1], e["box"][3]
            y_desde = top if opt["surprised"] is False else max(0, top - 1)
            relleno = {}
            for y in range(bot, y_desde - 1, -1):
                relleno[y] = pe["scleraRows"].get(y) or relleno.get(y + 1) or pe["sclera"]
            for yy in range(y_desde, bot + 1):
                for xx in range(x0, x1 + 1):
                    put(24 + xx, yy, relleno[yy])
                    stats["back"] += 1
            b = det["brows"].get(t)
            if b:
                for c in b["cells"]:
                    if c[1] < y_desde or c[1] > bot:
                        put(24 + c[0], c[1], det["skin"])


    log.append({"k": "backFace",
                "txt": ("Cara base (x24-31, y0-7): RESPETADA, la skin ya traía una cara parecida "
                        "(%d/64 píxeles iguales)" % parecido_back) if respetar_back else
                       "Cara base (x24-31, y0-7): el ojo se rellena de esclerótica y la ceja desaparece",
                "px": stats["back"]})

    # ---- 2. blinkFace (x0-7, y0-7)
    cara_parpadeo_ok, parecido_blink = ya_tiene_capa(src, face0, 0, 0, minimo)
    respetar_blink = bool(opt["respetar"] and cara_parpadeo_ok and opt["blinkStyle"] != "simple")
    stats["respetado"]["blink"] = respetar_blink
    if not respetar_blink:
        copiar_cara(0, 0)
        for t in ("R", "L"):
            e, pe, b = det["eyes"].get(t), pal["perEye"].get(t), det["brows"].get(t)
            if not e or not e["box"] or not pe:
                continue
            x0, x1 = e["box"][0], e["box"][2]
            top, bot = e["box"][1], e["box"][3]
            if b:
                for c in b["cells"]:
                    arriba = px(c[0], c[1] - 1) if c[1] > 0 else None
                    es_ojo = top <= c[1] <= bot
                    if not es_ojo:
                        put(c[0], c[1], arriba if (arriba and arriba[3] > 0) else det["skin"])
                    stats["blink"] += 1
            hay_ceja = bool(b and b["cells"] and pe["brow"])
            for yy in range(top, bot + 1):
                col = pal["lid"] if opt["blinkStyle"] == "simple" else (
                    pal["lid"] if (yy == bot or not hay_ceja) else pe["brow"])
                for xx in range(x0, x1 + 1):
                    put(xx, yy, col)
                    stats["blink"] += 1
    if respetar_blink:
        texto_blink = ("Cara de parpadeo (x0-7, y0-7): RESPETADA, la skin ya traía una cara parecida "
                       "(%d/64 píxeles iguales)" % parecido_blink)
    elif cara_parpadeo_ok and opt["blinkStyle"] == "simple":
        texto_blink = ("Cara de parpadeo (x0-7, y0-7): regenerada con parpadeo sencillo, como pediste, "
                       "aunque la skin ya traía una")
    else:
        texto_blink = "Cara de parpadeo (x0-7, y0-7): la ceja baja 1 píxel y el ojo se cierra"
    log.append({"k": "blinkFace", "txt": texto_blink, "px": stats["blink"]})

    # ---- 3. cubos de los huesos
    plan = opt["plan"] or plan_estilos(det, opt["eyeStyle"], opt["browStyle"], opt["snap"])
    if opt["cleanSlots"]:
        for kind in ("eye", "brow"):
            pinta = any(it["cubes"] for it in plan[kind])
            tiene = any(it["cells"] for it in plan[kind])
            if not pinta:
                if tiene:
                    stats["cleanedSkip"] = True
                continue
            for cu in CUBES[kind]:
                for cy in range(cu["rect"][1], cu["rect"][3]):
                    for cx in range(cu["rect"][0], cu["rect"][2]):
                        ci = (cy * 64 + cx) * 4
                        if out[ci + 3]:
                            stats["cleaned"] += 1
                        out[ci:ci + 4] = b"\x00\x00\x00\x00"
        if stats["cleaned"]:
            log.append({"k": "limpio", "txt": "Arte anterior borrado de las zonas de los cubos",
                        "px": stats["cleaned"]})

    forzado = hex2rgb(opt["slotColor"]) if opt["slotColor"] else None
    for kind in ("eye", "brow"):
        etiqueta = "ojo" if kind == "eye" else "ceja"
        for it in plan[kind]:
            for cu in it["cubes"]:
                rx, ry = cu["rect"][0], cu["rect"][1]
                w = cu["rect"][2] - rx
                for i, c in enumerate(cu["cells"]):
                    src_c = it["cells"][i % len(it["cells"])] if it.get("snapped") else c
                    put(rx + (i % w), ry + (i // w), forzado or px(src_c[0], src_c[1]))
                    stats["slots"] += 1
            if it["cells"] and not it["cubes"]:
                stats["unreachable"].append(
                    "%s %s (ningún cubo encaja con %d píxel%s)"
                    % (etiqueta, it["side"], len(it["cells"]), "" if len(it["cells"]) == 1 else "es"))
            for c in it["missing"]:
                stats["missing"].append("%s %s (%d,%d)" % (etiqueta, it["side"], c[0], c[1]))
            est = it["style"] or "—"
            it["estilos"] = uniq([
                re.sub(r"^(2x1|3x1) (\d)$", r"\1 (fila \2)", cu["style"]) for cu in it["cubes"]])
            if it["cubes"]:
                stats["slotList"].append("%s %s · %s (%d cubo%s)" % (
                    etiqueta, it["side"], re.sub(r"^(2x1|3x1) (\d)$", r"\1 (fila \2)", est),
                    len(it["cubes"]), "s" if len(it["cubes"]) > 1 else ""))
            if it.get("snapped"):
                stats.setdefault("snapped", []).append(
                    "%s %s → %s" % (etiqueta, it["side"], re.sub(r"^(2x1|3x1) (\d)$", r"\1 (fila \2)", est)))
    log.append({"k": "slots", "txt": "Cubos de los huesos de ojos y cejas", "px": stats["slots"]})

    return {"data": out, "palette": pal, "plan": plan, "log": log, "stats": stats}


# ============================================================================
#  8. Conversión completa + informe
# ============================================================================

def convertir_bytes(datos_png: bytes, sorpresa=True, simple=False, sombrero=False,
                    limpiar=True, ajustar=True, ojo=None, ceja=None, color_ojos=None,
                    color_cejas=None, color_esclerotica=None, color_parpado=None,
                    color_cubos=None, informe=False, respetar=True):
    """Convierte un PNG de skin. Devuelve (bytes del PNG nuevo, informe dict).

    Vale cualquier skin cuadrada de 64×64, 128×128 o 256×256.  En las grandes la cara
    (8×8) ocupa 16×16 o 32×32 píxeles: se analiza bajando a 64×64 y el resultado se
    devuelve a su tamaño, respetando tal cual (con su detalle) las capas que la skin ya
    trajera dibujadas.
    """
    ancho, alto, rgba = leer_png(datos_png)
    if ancho != alto or ancho not in (64, 128, 256):
        if (ancho, alto) == (64, 32):
            raise ValueError("la skin es 64x32 (formato antiguo): no tiene las zonas de A&S")
        raise ValueError("la skin mide %dx%d; tiene que ser cuadrada: 64x64, 128x128 o 256x256"
                         % (ancho, alto))
    k = ancho // 64
    base = bytes(rgba) if k == 1 else bajar_a_64(rgba, ancho)
    face = cara_de(base)
    det = analizar_cara(face)
    if det is None:
        raise ValueError("no he reconocido los ojos de esta skin")
    res = generar_skin(base, det, surprised=sorpresa, blinkStyle="simple" if simple else "oficial",
                       combineHat=sombrero, cleanSlots=limpiar, snap=ajustar,
                       eyeStyle=ojo, browStyle=ceja, pupilColor=color_ojos, browColor=color_cejas,
                       scleraColor=color_esclerotica, lidColor=color_parpado, slotColor=color_cubos,
                       respetar=respetar, minSame=(0 if k > 1 else None))
    data = res["data"]
    if k > 1:
        # subir el resultado y devolver las zonas respetadas tal como venían
        data = subir_de_64(data, ancho)
        resp = res["stats"]["respetado"]
        if resp.get("blink"):
            copiar_zona(rgba, ancho, 0, 0, 8, 8, data)
        if resp.get("back"):
            copiar_zona(rgba, ancho, 24, 0, 8, 8, data)
    png = escribir_png(ancho, ancho, data)
    info = {
        "version": __version__,
        "tamano": ancho, "escala": k,
        "deteccion": {"confianza": det["confidence"], "notas": det["notes"],
                      "ancla": det["anchor"], "piel": rgb_texto(det["skin"])},
        "ojos": {t: {"caja": det["eyes"][t]["box"], "pupilas": len(det["eyes"][t]["pupils"])} for t in ("R", "L")},
        "cejas": {t: (det["brows"][t]["y"] if det["brows"][t] else None) for t in ("R", "L")},
        "plan": {"ojo": {t: res["plan"]["eye"][i] for i, t in enumerate(("R", "L"))},
                 "ceja": {t: res["plan"]["brow"][i] for i, t in enumerate(("R", "L"))
                          if i < len(res["plan"]["brow"])}},
        "escrito": {k: res["stats"][k] for k in ("back", "blink", "slots", "cleaned")
                    if k in res["stats"]},
        "cubos": res["stats"]["slotList"],
        "sobrantes": res["stats"]["missing"],
        "sin_cubo": res["stats"]["unreachable"],
        "ajustados": res["stats"].get("snapped", []),
        "limpieza_saltada": bool(res["stats"].get("cleanedSkip")),
        "respetado": res["stats"]["respetado"],
        "sombrero": res["stats"]["hat"],
        "log": res["log"],
    }
    return png, info


# ============================================================================
#  9. Pack .mcpack (misma estructura que el pack oficial)
# ============================================================================

def _slug(texto):
    s = unicodedata.normalize("NFD", str(texto or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    if not s:
        s = "skin"
    if re.match(r"^[0-9]", s):
        s = "s_" + s
    return s[:30]


def pack_mcpack(skins, archivo, nombre_pack="Mis skins con expresiones", nombre_fichero=None):
    """skins: lista de dicts {png: bytes, display: str, geometry: str}."""
    pname = _slug(nombre_fichero or nombre_pack)
    if re.match(r"^[0-9]", pname):
        pname = "p_" + pname
    manifest = {
        "format_version": 1,
        "header": {"name": nombre_pack, "version": [1, 0, 0], "uuid": str(_uuid.uuid4())},
        "modules": [{"version": [1, 0, 0], "type": "skin_pack", "uuid": str(_uuid.uuid4())}],
    }
    lista = []
    for s in skins:
        lista.append({"localization_name": s["slug"], "geometry": s["geometry"],
                      "texture": s["slug"] + ".png", "type": "free"})
    skins_json = {"serialize_name": pname, "localization_name": pname, "skins": lista}
    lang = "\n".join(["skinpack.%s=%s" % (pname, nombre_pack)]
                     + ["skin.%s.%s=%s" % (pname, s["slug"], s["display"]) for s in skins]) + "\n"
    with zipfile.ZipFile(archivo, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        z.writestr("skins.json", json.dumps(skins_json, indent=2, ensure_ascii=False))
        z.writestr("texts/en_US.lang", lang)
        z.writestr("texts/es_ES.lang", lang)
        z.writestr("texts/languages.json", '["en_US","es_ES"]')
        for s in skins:
            z.writestr(s["slug"] + ".png", s["png"])
    return archivo


# ============================================================================
#  10. Línea de órdenes
# ============================================================================

def _informe_texto(ruta, info, salida):
    l = []
    l.append("── %s ─────────────────────────────────────────────" % ruta)
    lado = info.get("tamano", 64)
    l.append("  salida: %s (%dx%d)%s" % (salida, lado, lado,
             "  ·  analizada en 64x64" if info.get("escala", 1) > 1 else ""))
    l.append("  detección: %s%s" % (info["deteccion"]["confianza"],
                                   " · ancla: " + info["deteccion"]["ancla"]))
    for t, nombre in (("R", "derecho"), ("L", "izquierdo")):
        o = info["ojos"][t]
        cy = info["cejas"][t]
        l.append("  ojo (el suyo %s): %d píxel(es) de pupila · caja %s · ceja %s"
                 % (nombre, o["pupilas"], o["caja"], ("fila %d" % cy) if cy is not None else "—"))
    for t in ("R", "L"):
        it = info["plan"]["ojo"].get(t)
        if it:
            l.append("  cubos de ojo %s: %s" % (t, ", ".join(it["estilos"]) or "ninguno"))
    for t in ("R", "L"):
        it = info["plan"]["ceja"].get(t)
        if it:
            l.append("  cubos de ceja %s: %s" % (t, ", ".join(it["estilos"]) or "ninguno"))
    r = info.get("respetado") or {}
    if r.get("back") or r.get("blink"):
        nombres = [n for n, k in (("cara trasera", "back"), ("cara de parpadeo", "blink")) if r.get(k)]
        l.append("  respetado: %s (la skin ya traía esa capa dibujada; se deja tal cual)"
                 % " y ".join(nombres))
    e = info["escrito"]
    l.append("  píxeles escritos: %d cara trasera · %d parpadeo · %d cubos%s"
             % (e.get("back", 0), e.get("blink", 0), e.get("slots", 0),
                (" · %d borrados" % e["cleaned"]) if e.get("cleaned") else ""))
    for n in info["deteccion"]["notas"]:
        l.append("  aviso: %s" % n)
    if info["ajustados"]:
        l.append("  ajustados a la plantilla: %s" % " · ".join(info["ajustados"]))
    if info["limpieza_saltada"]:
        l.append("  aviso: no encaja ningún cubo, así que sus zonas se han dejado como estaban (no se ha borrado nada)")
    if info["sin_cubo"]:
        l.append("  sin cubo: %s" % " · ".join(info["sin_cubo"]))
    if info["sobrantes"]:
        l.append("  píxeles sin cubo: %s" % ", ".join(info["sobrantes"]))
    if info["sombrero"]["total"]:
        l.append("  capa de sombrero: %d píxeles (%d sobre los ojos)"
                 % (info["sombrero"]["total"], info["sombrero"]["enOjos"]))
    return "\n".join(l)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="conversor_actions_stuff.py",
        description="Convierte skins de Minecraft a skins compatibles con Actions & Stuff Expresiones "
                    "(v%s · misma lógica que el HTML %s)." % (__version__, VERSION_HTML),
        epilog="Ejemplo: python conversor_actions_stuff.py mi_skin.png --info",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entradas", nargs="*", help="PNG de 64x64 (una o varias skins)")
    ap.add_argument("-o", "--salida", help="nombre del PNG de salida (sólo con una entrada)")
    ap.add_argument("-d", "--dir", dest="carpeta", help="carpeta donde dejar las skins convertidas")
    ap.add_argument("--ojo", help="forzar tipo de ojo (%s)" % ", ".join(EYE_STYLES))
    ap.add_argument("--ceja", help="forzar tipo de ceja (%s)" % ", ".join(BROW_STYLES))
    ap.add_argument("--sin-sorpresa", action="store_true", help="sin la fila de esclerótica sobre el ojo")
    ap.add_argument("--simple", action="store_true", help="parpadeo sencillo (todo el ojo con el color del párpado)")
    ap.add_argument("--sombrero", action="store_true", help="copiar la cara tal como se ve (cara + sombrero)")
    ap.add_argument("--no-limpiar", action="store_true", help="no borrar el arte anterior de las zonas de cubos")
    ap.add_argument("--no-ajustar", action="store_true", help="no ajustar a la plantilla cuando el ojo no encaja")
    ap.add_argument("--no-respetar", action="store_true",
                    help="rehacer las capas aunque la skin ya las traiga dibujadas (por defecto se respetan)")
    ap.add_argument("--color-ojos", help="color de la pupila, p. ej. 3b2a1a")
    ap.add_argument("--color-cejas", help="color de la ceja")
    ap.add_argument("--color-esclerotica", help="color de la esclerótica (fondo del ojo)")
    ap.add_argument("--color-parpado", help="color del párpado")
    ap.add_argument("--color-cubos", help="pintar los cubos con un color fijo")
    ap.add_argument("--pack", help="crear además un pack de skins .mcpack con todo lo convertido")
    ap.add_argument("--pack-nombre", default="Mis skins con expresiones", help="nombre del pack")
    ap.add_argument("--pack-fichero", help="nombre interno del pack (por defecto, del nombre)")
    ap.add_argument("--modelo", choices=["clasico", "delgado"], default="clasico",
                    help="modelo para el pack: clasico (Steve) o delgado (Alex)")
    ap.add_argument("--info", action="store_true", help="informe completo de cada skin")
    ap.add_argument("--json", action="store_true", help="informe en JSON")
    ap.add_argument("--estilos", action="store_true", help="listar los tipos de la plantilla y salir")
    ap.add_argument("--enlaces", action="store_true",
                    help="mostrar los enlaces de descarga oficiales (pack de skins, plantilla y guía) y salir")
    ap.add_argument("-v", "--version", action="version", version="conversor_actions_stuff %s" % __version__)
    args = ap.parse_args(argv)

    if args.enlaces:
        print("Descargas OFICIALES de Oreville Studios (gratis):")
        print("  Pack de skins con expresiones (.mcpack, 33 skins de ejemplo):")
        print("    https://orevillestudios.com/api/downloads/actions-and-stuff-expressions-skins-1-0-0")
        print("  Plantilla del creador (.zip: .bbmodel de Blockbench + hoja de estilos + Read Me):")
        print("    https://orevillestudios.com/api/downloads/actions-stuff-expressions-template")
        print("  Paginas oficiales de descarga:")
        print("    https://orevillestudios.com/actions-&-stuff/expressions/download")
        print("    https://orevillestudios.com/actions-&-stuff/expressions-template/download")
        print("  Guia oficial (como se hacen las skins con expresiones):")
        print("    https://guides.orevillestudios.com/actions-and-stuff-expressions")
        print()
        print("  El addon Actions & Stuff (el de las animaciones) es de PAGO: se compra en el")
        print("  Marketplace de Minecraft desde el propio juego. Este script no lo incluye.")
        return 0

    if args.estilos:
        print("Tipos de ojo (%d):  %s" % (len(EYE_STYLES), ", ".join(EYE_STYLES)))
        print("Tipos de ceja (%d): %s" % (len(BROW_STYLES), ", ".join(BROW_STYLES)))
        print("\nCubos de la plantilla: %d de ojos y %d de cejas" % (len(CUBES["eye"]), len(CUBES["brow"])))
        for est in EYE_STYLES:
            n = len([c for c in CUBES["eye"] if c["style"] == est])
            print("  ojos %-12s %d variantes" % (est, n))
        for est in BROW_STYLES:
            n = len([c for c in CUBES["brow"] if c["style"].startswith(est)])
            print("  cejas %-11s %d variantes" % (est, n))
        return 0

    if not args.entradas:
        ap.print_help()
        return 2

    if args.ojo and args.ojo not in EYE_STYLES:
        print("Tipo de ojo desconocido: %s (mira --estilos)" % args.ojo, file=sys.stderr)
        return 2
    if args.ceja and args.ceja not in BROW_STYLES:
        print("Tipo de ceja desconocido: %s (mira --estilos)" % args.ceja, file=sys.stderr)
        return 2

    if args.carpeta:
        os.makedirs(args.carpeta, exist_ok=True)
    pack_skins, fallos = [], 0
    for ruta in args.entradas:
        if not os.path.isfile(ruta):
            print("no encuentro el archivo: %s" % ruta, file=sys.stderr)
            fallos += 1
            continue
        base = os.path.splitext(os.path.basename(ruta))[0]
        destino = args.salida if (args.salida and len(args.entradas) == 1) else (base + "_as.png")
        if args.carpeta:
            destino = os.path.join(args.carpeta, os.path.basename(destino))
        try:
            with open(ruta, "rb") as fh:
                datos = fh.read()
            png, info = convertir_bytes(
                datos, sorpresa=not args.sin_sorpresa, simple=args.simple, sombrero=args.sombrero,
                limpiar=not args.no_limpiar, ajustar=not args.no_ajustar, ojo=args.ojo, ceja=args.ceja,
                color_ojos=args.color_ojos, color_cejas=args.color_cejas,
                color_esclerotica=args.color_esclerotica, color_parpado=args.color_parpado,
                color_cubos=args.color_cubos, respetar=not args.no_respetar)
            with open(destino, "wb") as fh:
                fh.write(png)
        except Exception as exc:                       # noqa: BLE001 (mensaje claro y a seguir)
            print("✘ %s: %s" % (ruta, exc), file=sys.stderr)
            fallos += 1
            continue
        if args.json:
            print(json.dumps({"archivo": ruta, "salida": destino, "informe": info},
                             ensure_ascii=False, indent=2))
        elif args.info:
            print(_informe_texto(ruta, info, destino))
        else:
            print("✔ %s → %s · %s" % (ruta, destino, " · ".join(info["cubos"]) or "sin cubos"))
        if args.pack:
            pack_skins.append({
                "png": png, "slug": _slug(base), "display": base,
                "geometry": ("geometry.humanoid.customSlim" if args.modelo == "delgado"
                             else "geometry.humanoid.custom")})

    if args.pack:
        if not pack_skins:
            print("no hay ninguna skin convertida para el pack", file=sys.stderr)
            return 1
        pack_mcpack(pack_skins, args.pack, args.pack_nombre, args.pack_fichero)
        print("✔ pack: %s (%d skins)" % (args.pack, len(pack_skins)))
        print("  ábrelo con Minecraft (doble clic) y aparecerá en Ajustes → Perfil → Skins → pack.")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
