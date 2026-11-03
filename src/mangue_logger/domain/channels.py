"""Registry de canais: identidade estável (`id`) separada do rótulo exibido (`label`).

Toda lógica interna usa `id`; os rótulos existem só para UI/relatórios. As constantes
``KEY_*`` mantêm os rótulos históricos (v6) por compatibilidade com exports e workspaces.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True)
class Channel:
    id: str
    label: str
    unit: str
    kind: str   # "time" | "raw" | "derived"
    group: str  # "velocity" | "rotation" | "dynamics" | "time"


class ChannelRegistry:
    def __init__(self, channels: Iterable[Channel]):
        self._by_id = {c.id: c for c in channels}
        self._by_label = {c.label: c for c in self._by_id.values()}
        if len(self._by_id) != len(self._by_label):
            raise ValidationError("ids/rótulos de canal duplicados")

    def get(self, id_or_label: str) -> Channel:
        ch = self.find(id_or_label)
        if ch is None:
            raise KeyError(id_or_label)
        return ch

    def find(self, id_or_label: str) -> Channel | None:
        return self._by_id.get(id_or_label) or self._by_label.get(id_or_label)

    def ids(self) -> list[str]:
        return list(self._by_id)

    def labels(self) -> list[str]:
        return [c.label for c in self._by_id.values()]

    def __iter__(self) -> Iterator[Channel]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


TIME, RPM, RPM_RAW, VEL, VEL_RAW, ACEL, DIST = (
    "time", "rpm", "rpm_raw", "vel", "vel_raw", "acel", "dist",
)

# Ordem = ordem de exibição na UI (idêntica à v6).
DEFAULT_CHANNELS = ChannelRegistry([
    Channel(TIME, "Tempo (s)", "s", "time", "time"),
    Channel(RPM, "RPM (Filtrado)", "RPM", "derived", "rotation"),
    Channel(VEL, "Velocidade (Km/h - Filtrado)", "km/h", "derived", "velocity"),
    Channel(ACEL, "Aceleração (m/s² - Filtrado)", "m/s²", "derived", "dynamics"),
    Channel(DIST, "Distância (m)", "m", "derived", "dynamics"),
    Channel(RPM_RAW, "RPM (Bruto)", "RPM", "raw", "rotation"),
    Channel(VEL_RAW, "Velocidade (Km/h - Bruto)", "km/h", "raw", "velocity"),
])

# Rótulos históricos (compatibilidade com v6)
KEY_TEMPO_S = DEFAULT_CHANNELS.get(TIME).label
KEY_RPM_FILT = DEFAULT_CHANNELS.get(RPM).label
KEY_RPM_RAW = DEFAULT_CHANNELS.get(RPM_RAW).label
KEY_VEL_KMH_FILT = DEFAULT_CHANNELS.get(VEL).label
KEY_VEL_KMH_RAW = DEFAULT_CHANNELS.get(VEL_RAW).label
KEY_ACEL_MS2_FILT = DEFAULT_CHANNELS.get(ACEL).label
KEY_DIST_M = DEFAULT_CHANNELS.get(DIST).label
