from Salva.database import get_session
from Salva.Calendars import Calendars
from Salva.CalendarSync import CalendarSync
from Salva.Repository.Users import UserRepository

from datetime import datetime, timezone
from Salva.Services.ScheduleEvent import ScheduleEvent
from Salva.models import User

import argparse

import os
from dotenv import load_dotenv

load_dotenv()

session = get_session(os.getenv("ENV"))

def main(opt):
    userRep = UserRepository(session)

    user : User = userRep.get_user_by_email(opt.user)

    cal_client = Calendars()
    sync = CalendarSync(session, cal_client)
    SE = ScheduleEvent(session)

    sync.sync(user.id, "Travail", datetime(2026, 2, 23, 0, 0, tzinfo=timezone.utc), datetime(2026, 3, 3, 23, 0, tzinfo=timezone.utc))
    SE.calcul_new_week()  
    sync.sync(user.id, "Travail", datetime(2026, 2, 23, 0, 0, tzinfo=timezone.utc), datetime(2026, 3, 3, 23, 0, tzinfo=timezone.utc))

if __name__ == "__main__" :
    opt = argparse.ArgumentParser(
        description="Salva est un moteur de management d'emploie du temps sur Iphone."
    )

    opt.add_argument(
        "--user", default="batmoon19@gmail.com", type=str, help="Adresse mail du compte que vous voulez connecter", required=True
    )

    args = opt.parse_args()

    main(args)