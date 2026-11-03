"""Constantes de apresentação derivadas do registry de canais."""

from __future__ import annotations

from ..domain import channels as ch

CHANNELS = ch.DEFAULT_CHANNELS.labels()

# Unidades por rótulo (v6) e por id estável.
CHANNEL_UNITS = {c.label: c.unit for c in ch.DEFAULT_CHANNELS} | {c.id: c.unit for c in ch.DEFAULT_CHANNELS}

_GROUP_TITLES = {"velocity": "⚡  Velocidade", "rotation": "🔄  Rotação", "dynamics": "📐  Dinâmica",
                 "time": "⏱  Temporal"}
_ORDER = {"velocity": [ch.VEL, ch.VEL_RAW], "rotation": [ch.RPM, ch.RPM_RAW],
          "dynamics": [ch.ACEL, ch.DIST], "time": [ch.TIME]}
CHANNEL_GROUPS = {_GROUP_TITLES[g]: [ch.DEFAULT_CHANNELS.get(i).label for i in ids] for g, ids in _ORDER.items()}

_K = ch.DEFAULT_CHANNELS
SCATTER_PAIRS = [
    (_K.get(ch.VEL).label, _K.get(ch.RPM).label, "Vel × RPM"),
    (_K.get(ch.VEL).label, _K.get(ch.ACEL).label, "Vel × Aceleração"),
    (_K.get(ch.RPM).label, _K.get(ch.ACEL).label, "RPM × Aceleração"),
    (_K.get(ch.TIME).label, _K.get(ch.VEL).label, "Tempo × Vel"),
    (_K.get(ch.TIME).label, _K.get(ch.RPM).label, "Tempo × RPM"),
    (_K.get(ch.DIST).label, _K.get(ch.VEL).label, "Dist × Vel"),
]
