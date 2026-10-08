# Conversor de skins · Minecraft

### Expresiones para **Java** (ojos animados, Fresh Moves) y **Bedrock** (Actions & Stuff)

Una herramienta web que prepara tu skin de Minecraft para que **parpadee y mueva los ojos**
dentro del juego. No hay que instalar nada: se abre en el navegador, funciona con tu skin y
**tu skin no sale de tu ordenador** (no se sube a ningún sitio).

> La herramienta **no trae ninguna skin puesta**: la abres vacía y, en cuanto cargas la tuya,
> aparece tu propio muñeco en 3D con sus colores de verdad. Si solo quieres ver cómo funciona,
> en la lengüeta Bedrock tienes 4 skins de ejemplo oficiales para probar con un clic.

**Pruébala aquí:** https://isacrack.github.io/Skines-con-expresiones/

También puedes descargar el repositorio y abrir `index.html` con doble clic: funciona igual,
sin servidor y sin conexión a internet.

---

## Qué hace

| Lengüeta | Qué prepara en tu skin | Qué necesitas en el juego |
| --- | --- | --- |
| **Java · ojos animados** | Los píxeles extra que anima **Fresh Moves**: párpados y pupilas (parpadeo, miradas y cejas) | **Fabric o Forge** (el launcher normal no carga estos mods) · **EMF ≥ 2.0.2** y **ETF ≥ 6.0.1** · el pack **Fresh Moves** |
| **Bedrock · Actions & Stuff** | Las capas del addon **Actions & Stuff — Expresiones**: cara de parpadeo, cara trasera y los cubos de ojos y cejas de la plantilla oficial | **Enable Expressions** activado · **Vibrant Visuals desactivado** (son incompatibles) · **skin clásica** subida · A&S **1.5 o superior** |

La lengüeta **Java** y la lengüeta **Bedrock** van en la misma página (con la barra de lengüetas
arriba del todo), y además cada una tiene su propia carpeta por si la quieres suelta:

- `index.html` → las dos lengüetas juntas (empieza por aquí)
- `java/index.html` → solo Java
- `bedrock/index.html` → solo Bedrock

---

## Cómo se usa

1. **Carga tu skin** (64×64, 128×128 o 256×256): con el botón, arrastrándola o pegándola con
   `Ctrl`+`V`. Se analiza al momento y te dice lo que ha entendido: tamaño, si es de Steve o de
   Alex (brazos gruesos o delgados), dónde están los ojos y las cejas… En Bedrock, además,
   tienes una fila de skins de ejemplo para probar.
2. **Revisa el dibujo de la cara** y **ajusta** lo que haga falta (lo normal es dejarlo en
   automático).
   Si la herramienta se equivoca con algún píxel, puedes corregirlo a mano: se puede marcar y
   desmarcar cada píxel de la cara. El modo **«respetar lo que la skin ya trae»** no toca lo que
   tú ya hayas dibujado.
3. **Mira el jugador en 3D**: está justo debajo de la configuración, ya con tu skin y con los
   ajustes que acabas de poner.
4. **Descarga** el resultado (ver más abajo).

---

## El jugador en 3D

Está **debajo de la selección de skin y de la configuración**: aparece cuando cargas tu skin y
lo tienes ahí mismo mientras ajustas el parpadeo, las cejas o los colores. Mientras no haya
skin, en su sitio se ve un aviso que te lo recuerda.

- **En Java** queda entre «J4 Ajustes de Java y píxeles que se escriben» y «J5 Descarga».
- **En Bedrock**, entre «3 Ajustes de la conversión» y «4 Vista previa».

- **Arrastra** para girarlo. Subes el ratón y la cara mira hacia abajo; si prefieres el otro
  sentido, el botón **«Giro: subir el ratón = …»** le da la vuelta y **se acuerda** de tu elección.
- **Rueda del ratón** para acercar y alejar.
- Botones: **Volver de frente**, **Dejar girar / Que gire sola**, **Ver solo la cabeza**,
  **Brazos delgados**, **Pintar la 2ª capa** (chaleco, gorro, mangas y pantalones).
- Está dibujado **píxel a píxel con tu skin**, con las esquinas a escuadra y sin bordes
  redondeados, como en Minecraft. Sus botones están apagados hasta que haya una skin cargada.

---

## Descargas

Según la lengüeta, puedes descargar:

- **La skin completa** ya preparada (`.png`), lista para subir al juego.
- **Cada capa por separado** (`.png`), para mirarlas o montarlas tú en Blockbench.
- En Bedrock, además, **un pack `.mcpack`** con todas las capas, para importarlo de una vez.

---

## El animador de ojos (Java)

Un pequeño banco de pruebas para ver cómo se moverán los ojos antes de entrar al juego:

- Miradas (izquierda, derecha), **parpadeo**, **guiño** y cejas de sorpresa; también puedes
  **elegir** cerrar solo el ojo izquierdo o el derecho.
- **Guion por pasos**: monta una secuencia de movimientos y reprodúcela.
- **«Solo (vivo)»**: deja al muñeco con la mirada viva mientras trabajas.
- Puedes **exportar e importar el guion** (`guion_ojos.json`).

Es una aproximación con los mismos píxeles que prepara la herramienta, no el motor del juego:
sirve para ver que has dejado los ojos en el sitio correcto.

---

## Si algo no funciona

**En Bedrock no pestañea**
- Comprueba que el addon es **Actions & Stuff 1.5 o superior**.
- Que tienes **Enable Expressions** activado.
- Que **Vibrant Visuals** está desactivado.
- Que has subido la skin **clásica** (no una de 128×128 con capas raras) y que no llevas
  expresiones puestas en la consola.

**En Java los ojos se ven negros**
- Casi siempre es que falta activar **«Allow skin transparency»** (permitir transparencia)
  en Fresh Moves. La herramienta mantiene dentro del paso 5 el diagnóstico oficial.

**Veo una versión antigua de la herramienta**
- Pulsa **Ctrl+F5** (recarga sin caché). La versión actual lleva la etiqueta
  **«3D y piel: cuadrado y nítido · v5»** debajo del encabezado.

---

## Archivos del repositorio

```
index.html                                   la herramienta, con las dos lengüetas
java/index.html                              solo la lengüeta Java
bedrock/index.html                           solo la lengüeta Bedrock
bedrock/Pack_Oficial_AS_Expresiones.mcpack   el pack oficial, listo para importar
bedrock/Pack_Oficial_AS_Expresiones.zip      el mismo pack, en formato zip
bedrock/Plantilla_Oficial_AS_Expresiones.zip la plantilla oficial, para Blockbench
README.md                                    esto
```

Cada página es **un solo archivo**: lleva dentro el HTML, el CSS, el JavaScript y todo lo
necesario. No hace falta instalar Python ni nada parecido.

---

## Créditos

Hecho por **Isacrack**. Gracias por apoyar el proyecto: si lo usas, **dame créditos como
Isacrack**.

- **Actions & Stuff — Expresiones** y sus guías: **Oreville Studios** (guides.orevillestudios.com).
  El pack y la plantilla oficiales que van en `bedrock/` son suyos; están aquí solo para que
  te sea más fácil descargarlos.
- **Fresh Moves**, de **FreshLX** (la extensión de jugador de Fresh Animations).
- **EMF** y **ETF** (Entity Model Features y Entity Texture Features), que hacen posible la
  animación de ojos en Java.
- La idea del flujo de trabajo sigue el vídeo de **Lobo** sobre expresiones en skins.
