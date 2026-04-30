# Wenuke Design System

> Inspirado en WhatsApp. Asistente climático para pequeños agricultores de La Araucanía, Chile.
> Interfaz de chat mobile-first, tono cálido y cercano. Funcional antes que decorativo.

---

## 1. Visual Theme & Atmosphere

- **Mood:** Cálido, confiable, cercano. Como hablar con un vecino que sabe de clima.
- **Density:** Compacta pero respirable. Información densa sin abrumar.
- **Philosophy:** Chat-first. Todo pasa por la conversación. La UI desaparece, queda el diálogo.
- **Atmosphere:** Familiar — cualquiera que haya usado WhatsApp entiende la interfaz al instante.
- **Design DNA:** WhatsApp Web + agricultura. Burbujas de chat, verdes corporativos, iconografía del agro.

---

## 2. Color Palette & Roles

| Token | Hex | Rol |
|---|---|---|
| `wa-dark` | `#075e54` | Header, status bar, elementos primarios pesados |
| `wa-medium` | `#128c7e` | Avatar bg, botones secundarios, badges |
| `wa-light` | `#25d366` | Botón enviar, acciones primarias, acentos |
| `wa-bg` | `#e5ddd5` | Fondo global (fallback) |
| `wa-panel` | `#ededed` | Paneles, input area, footer |
| `wa-chatBg` | `#efeae2` | Fondo del área de chat (con patrón sutil) |
| `bubble-user` | `#d9fdd3` | Burbuja de mensaje del usuario (verde claro) |
| `bubble-bot` | `#ffffff` | Burbuja del bot (blanco con borde sutil) |
| `text-primary` | `#1f2937` (gray-800) | Texto principal de mensajes |
| `text-secondary` | `#4b5563` (gray-600) | Texto secundario, timestamps |
| `text-muted` | `#9ca3af` (gray-400) | Placeholders, texto inactivo |
| `border-light` | `#e5e7eb` (gray-200) | Bordes de tarjetas, inputs, separadores |
| `alert-helada` | `#3b82f6` (blue-500) | Borde de alerta de helada |
| `alert-lluvia` | `#06b6d4` (cyan-500) | Borde de alerta de lluvia intensa |
| `alert-viento` | `#f97316` (orange-500) | Borde de alerta de viento fuerte |
| `severity-high` | `#ef4444` (red-500) | Badge de severidad alta |
| `severity-mid` | `#f59e0b` (amber-500) | Badge de precaución |

**Reglas de uso:**
- `wa-dark` solo en header. Nunca en fondos grandes.
- `wa-light` solo en el botón de enviar y hover states. No abusar.
- Las burbujas de usuario siempre `#d9fdd3`, las del bot siempre `#ffffff`.
- Fondos de alerta siempre con opacidad 50 (`bg-blue-50`, `bg-cyan-50`, `bg-orange-50`).

---

## 3. Typography Rules

**Font Stack:** Sistema nativo (Tailwind `font-sans`). Sin fuentes externas — carga instantánea.

```
-font-family-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
  "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```

**Jerarquía:**

| Nivel | Clase Tailwind | Uso |
|---|---|---|
| H1 | `text-base font-semibold` | Título "Wenuke" en header |
| H2 | `text-sm font-medium` | Subtítulos en tarjetas, labels de alerta |
| Body | `text-sm` | Mensajes de chat (principal) |
| Caption | `text-xs` | Timestamps, status, coordenadas, botones de ejemplo |
| Fine print | `text-[10px]` | Badges de severidad, hora en burbujas |

**Reglas:**
- Nunca justificar texto. Siempre izquierda.
- `whitespace-pre-wrap` en mensajes para respetar saltos de línea.
- Bold solo con `<strong class="font-semibold">` (formateo markdown `**text**`).
- Sin cursiva decorativa. Solo en mensajes offline (`_texto_`).
- `select-none` en todo el body. Chat no es para seleccionar.

---

## 4. Component Stylings

### Buttons

**Primario (Enviar):**
```
w-10 h-10 bg-wa-light rounded-full shadow-md
hover:bg-wa-medium active:scale-95
```

**Cultivo (seleccionado):**
```
bg-wa-medium text-white rounded-full px-4 py-1.5 text-sm font-medium
```

**Cultivo (no seleccionado):**
```
bg-white text-gray-600 border border-gray-200 rounded-full px-4 py-1.5 text-sm
hover:border-wa-light hover:text-wa-medium
```

**Ejemplo / Quick-action:**
```
bg-white text-gray-600 rounded-full px-3 py-1.5 text-xs border border-gray-200
hover:bg-wa-light hover:text-white hover:border-wa-light
```

**Icono (header):**
```
w-9 h-9 rounded-full text-white/80 hover:bg-white/10
```

### Cards (Alertas)

```html
<div class="bg-white border-l-4 [color-de-alerta] [bg-de-alerta-50] rounded-r-lg px-4 py-3 shadow-sm">
  <!-- header con ícono + label + badge severidad + fecha -->
  <!-- cuerpo con mensaje -->
</div>
```

Borde izquierdo de 4px como indicador de severidad. El resto del borde redondeado a la derecha.

### Input (Textarea)

```
resize-none rounded-2xl border border-gray-200 px-4 py-2.5 text-sm
focus:outline-none focus:ring-2 focus:ring-wa-light focus:border-transparent
placeholder-gray-400 bg-white shadow-sm
```

- `min-height: 2.75rem; max-height: 6rem`
- Auto-grow con JS (no CSS).
- `rounded-2xl` (16px). Más redondo que un input normal — estilo chat.

### Chat Bubbles

**Usuario:**
```
bg-[#d9fdd3] rounded-lg rounded-br-none px-4 py-2.5 max-w-[80%] shadow-sm
```

**Bot:**
```
bg-white rounded-lg rounded-bl-none px-4 py-2.5 max-w-[80%] shadow-sm border border-gray-100
```

- Esquina inferior sin redondear del lado del remitente (br para user, bl para bot).
- `max-w-[80%]` — nunca full width.
- Avatar del bot: `w-7 h-7 bg-wa-medium rounded-full`.

### Navigation

No hay nav tradicional. La interfaz es un chat. El header superior hace de barra de navegación fija.

### Map Overlay

```
bg-white border-b-4 border-wa-light shadow-inner
```

- Mapa Leaflet: 280px altura, sin atribución.
- Overlay de coordenadas: `bg-white rounded-lg shadow-md px-3 py-1.5 text-xs font-mono`.
- Panel de inputs de coordenadas: fondo `bg-gray-50`, inputs con borde `focus:ring-2 focus:ring-wa-light`.

---

## 5. Layout Principles

**Spacing scale (Tailwind):**

| Token | Valor | Uso |
|---|---|---|
| `gap-1` | 4px | Entre botones de quick-actions |
| `gap-2` | 8px | Entre avatar y burbuja, entre elementos internos |
| `gap-3` | 12px | Header: avatar + texto |
| `px-3 py-2` | 12px 8px | Padding de quick-actions bar |
| `px-4 py-2.5` | 16px 10px | Padding de input area, crop selector |
| `px-4 py-3` | 16px 12px | Padding de header, chat area |

**Grid:** No hay grid. Layout de columna única con anclajes:
- `max-w-2xl mx-auto` en el contenedor de mensajes (672px máximo).
- `max-w-[80%]` en burbujas individuales.

**Whitespace philosophy:**
- El chat respira. Padding generoso en mensajes, pero sin separación excesiva entre burbujas (`mb-2` o `mb-3`).
- Quick-actions bar compacta para minimizar scroll horizontal (pero permite overflow-x-auto).
- Sin márgenes laterales desperdiciados en mobile.

**Sticky elements:**
1. Header (top-0, flex-shrink-0, z-20)
2. Map overlay (flex-shrink-0)
3. Crop selector (flex-shrink-0)
4. Chat area (flex-1, overflow-y-auto) ← único que scrollea
5. Quick actions (flex-shrink-0)
6. Input area (flex-shrink-0, shadow top)

---

## 6. Depth & Elevation

Sistema de sombras sutil. Sin exagerar — es chat, no dashboard.

| Nivel | Clase | Uso |
|---|---|---|
| 0 | (sin shadow) | Fondo de chat |
| 1 | `shadow-sm` | Burbujas de chat, tarjetas de alerta |
| 2 | `shadow-md` | Header, botón de enviar, overlay de coordenadas |
| 3 | `shadow-inner` | Map overlay (hundido) |
| 4 | `shadow-[0_-1px_3px_rgba(0,0,0,0.05)]` | Input area (elevación inversa hacia arriba) |

**Reglas:**
- Burbujas siempre `shadow-sm`. Da sensación de papel.
- Botón enviar `shadow-md` para destacar como acción primaria.
- Header `shadow-md` para separar del contenido.
- Sin sombras de color. Solo `rgba(0,0,0,0.05)` a `0.10`.

---

## 7. Do's and Don'ts

### ✅ Do

- Usar la paleta `wa-*` para todos los elementos de la marca.
- Burbujas de chat: usuario a la derecha (`justify-end`), bot a la izquierda (`gap-2`).
- Redondear botones y pills (`rounded-full`). Es chat, no form.
- Mantener el mapa oculto por defecto. Solo aparece bajo demanda.
- Usar `msg-enter` para animar mensajes nuevos (fade-in + slide-up sutil).
- Timestamps en cada mensaje (`text-[10px] text-gray-400`).
- Alertas siempre con ícono + border-left de color + fondo pastel.
- Input siempre sticky abajo. Chat scrollea entre header e input.

### ❌ Don't

- No usar otros verdes que no sean los de la paleta `wa-*`.
- No justificar texto a la derecha en burbujas del bot.
- No mostrar más de 4 quick-actions. Si no entran, scrollean.
- No usar modales. Todo es inline en el chat o overlay tipo panel.
- No agregar borders gruesos a las burbujas. `border-gray-100` máximo.
- No quitar el `select-none` del body.
- No usar shadows de Tailwind grandes (`shadow-lg`, `shadow-xl`) — rompen la estética chat.
- No poner avatar en burbujas de usuario.
- No usar `rounded-full` en burbujas de chat — solo `rounded-lg`.

---

## 8. Responsive Behavior

**Mobile-first.** La app está pensada para usarse en el campo, con una mano, con poca señal.

**Breakpoints implícitos (Tailwind defaults):**

| Breakpoint | Comportamiento |
|---|---|
| Default (mobile) | Layout completo. Header compacto, chat full-width. |
| `sm` (640px) | Sin cambios. El `max-w-2xl` ya contiene. |
| `md` (768px) | Chat area centrada con margen lateral. |
| `lg`+ | El `max-w-2xl` (672px) limita el ancho de lectura. |

**Touch targets:**
- Botones mínimo 36px (w-9/h-9 o w-10/h-10).
- Pills de cultivo: `py-1.5` (12px vertical) + `px-4` (16px horizontal).
- `active:scale-95` en todos los botones para feedback táctil inmediato.
- `-webkit-tap-highlight-color: transparent` en todo.

**Collapsing strategy:**
- Quick-actions bar: `overflow-x-auto` (scroll horizontal, sin scrollbar visible).
- Crop selector: `overflow-x-auto` (mismo comportamiento).
- Mapa: oculto por defecto (`hidden`), toggle con botón de ubicación.

**Viewport:**
- `h-dvh` en body (dynamic viewport height, maneja barras de navegación mobile).
- `maximum-scale=1.0, user-scalable=no, viewport-fit=cover` — previene zoom accidental en inputs.

---

## 9. Agent Prompt Guide

### Quick Reference — Colores

```
wa-dark:    #075e54  (header)
wa-medium:  #128c7e  (avatars, badges)
wa-light:   #25d366  (send button, accents)
wa-chatBg:  #efeae2  (chat background, with subtle SVG pattern)
user-msg:   #d9fdd3  (user bubble)
bot-msg:    #FFFFFF  (bot bubble)
```

### Prompts listos para usar

**"Creá un nuevo componente de alerta para [tipo] siguiendo el DESIGN.md"**

**"Aplicá el design system de Wenuke a esta nueva pantalla de [funcionalidad]"**

**"Revisá que este componente use la paleta wa-* y no introduzca colores nuevos"**

**"Convertí este diseño a mobile-first con los touch targets del DESIGN.md"**

**"Agregá animaciones de entrada msg-enter a los nuevos elementos del chat"**

**"Este componente no sigue el design system: [describir problema]. Corregilo."**

### Stack tecnológico relevante

- Tailwind CSS (CDN, config inline con colores `wa-*`)
- Leaflet (mapas)
- Vanilla JS (sin framework)
- Mobile-first, offline-capable
