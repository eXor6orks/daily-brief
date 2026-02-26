from typing import List, Optional, Tuple
from datetime import datetime, date, time, timedelta, timezone
from Salva.models import UserPreferences

class TimeSlot:
    def __init__(self, start_day, end_day):
        self.start_day = start_day
        self.end_day = end_day

    def calcul_time_unable(self, events) -> list[dict]:
        """Calcule les créneaux libres entre `start_day` et `end_day` en fonction
        de la liste `events` (chaque event doit avoir les clés 'Début' et 'Fin'
        au format 'H[:MM]' ou 'Hh').

        Retourne une liste de dicts: [{'Début': '09:00', 'Fin': '13:30'}, ...]
        """

        def parse_time_str(s: str) -> int:
            """Retourne minutes depuis minuit."""
            if s is None:
                raise ValueError("time string is None")
            s = str(s).strip()
            # accepter formats "HH:MM", "H:MM", "9", "9h", "9h30"
            if ":" in s:
                parts = s.split(":")
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
            elif "h" in s:
                parts = s.split("h")
                h = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
            else:
                h = int(s)
                m = 0
            return h * 60 + m

        def minutes_to_hhmm(m: int) -> str:
            h = m // 60
            mm = m % 60
            return f"{h:02d}:{mm:02d}"

        # bornes de la journée
        try:
            day_start_min = parse_time_str(self.start_day)
        except Exception:
            day_start_min = 0

        try:
            day_end_min = parse_time_str(self.end_day)
        except Exception:
            day_end_min = 24 * 60

        intervals: List[Tuple[int, int]] = []
        for ev in events or []:
            try:
                s = parse_time_str(ev.get("Debut") or ev.get("Debut".lower()) or ev.get("start") or ev.get("Start"))
                e = parse_time_str(ev.get("Fin") or ev.get("Fin".lower()) or ev.get("end") or ev.get("End"))
            except Exception:
                # ignorer events mal formattés
                continue

            # clipper dans la journée
            s = max(s, day_start_min)
            e = min(e, day_end_min)
            if e <= s:
                continue
            intervals.append((s, e))

        # fusionner les intervalles qui se chevauchent
        intervals.sort(key=lambda x: x[0])
        merged: List[Tuple[int, int]] = []
        for iv in intervals:
            if not merged:
                merged.append(iv)
            else:
                last_s, last_e = merged[-1]
                if iv[0] <= last_e:  # chevauchement ou contigu
                    merged[-1] = (last_s, max(last_e, iv[1]))
                else:
                    merged.append(iv)

        # trouver les créneaux libres
        free_slots: List[dict] = []
        cursor = day_start_min
        for s, e in merged:
            if s > cursor:
                free_slots.append({"Début": minutes_to_hhmm(cursor), "Fin": minutes_to_hhmm(s)})
            cursor = max(cursor, e)

        if cursor < day_end_min:
            free_slots.append({"Début": minutes_to_hhmm(cursor), "Fin": minutes_to_hhmm(day_end_min)})

        # stocker sur l'objet pour réutilisation éventuelle
        self.available_slots = free_slots
        return free_slots
