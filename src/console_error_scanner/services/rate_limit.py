"""Rate-Limit fuer ausgehende Seitenaufrufe.

Warum das noetig ist: Die Parallelitaet (Semaphore) begrenzt nur, wie viele
Seiten GLEICHZEITIG geprueft werden - nicht, wie viele pro Minute rausgehen.
Antwortet der Server schnell, arbeitet der Scanner entsprechend schnell weiter.

Dieses Werkzeug wiegt dabei schwerer als ein reiner HTTP-Crawler: Jede Seite
laeuft zwingend durch einen echten Browser, laedt also auch Skripte, Schriften
und Bilder und geht an den Zwischenspeichern des Servers vorbei. Eine Seite
entspricht damit einem Vielfachen der Last eines einfachen Abrufs.

Der Limiter verteilt die Aufrufe gleichmaessig ueber die Zeit (kein Burst):
bei 60 Aufrufen/Minute geht genau einer pro Sekunde raus. Gewartet wird
ausserhalb des Locks, damit sich mehrere Aufrufer ihre Slots vorab holen und
parallel warten koennen, statt sich gegenseitig zu serialisieren.
"""

from __future__ import annotations

import asyncio


class RateLimiter:
    """Verteilt Aufrufe gleichmaessig ueber die Zeit.

    Ist die Rate 0 oder negativ, ist der Limiter abgeschaltet und `acquire()`
    kehrt sofort zurueck - so laesst sich das Objekt bedingungslos einhaengen,
    ohne an jeder Aufrufstelle auf None zu pruefen.
    """

    def __init__(self, per_minute: int) -> None:
        self._interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    @property
    def enabled(self) -> bool:
        """Gibt zurueck, ob tatsaechlich gedrosselt wird."""
        return self._interval > 0.0

    async def acquire(self) -> None:
        """Wartet, bis der naechste Zeitschlitz frei ist."""
        if self._interval <= 0.0:
            return

        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            # Liegt der letzte Slot in der Vergangenheit, startet die Kette neu
            # bei jetzt - sonst wuerde eine Pause spaeter zu einem Burst fuehren.
            slot = max(now, self._next_slot)
            self._next_slot = slot + self._interval

        delay = slot - now
        if delay > 0:
            await asyncio.sleep(delay)
