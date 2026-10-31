from datetime import datetime, timedelta, timezone


def daily_totals(events, offset_minutes):
    if type(offset_minutes) is not int or not -720 <= offset_minutes <= 840:
        raise ValueError("offset out of range")
    tz = timezone(timedelta(minutes=offset_minutes))
    totals = {}
    for stamp, amount in events:
        if type(amount) is not int:
            raise ValueError("amount must be an integer")
        moment = datetime.fromisoformat(stamp)
        if moment.tzinfo is None:
            raise ValueError("timestamp needs an offset")
        day = moment.astimezone(tz).date().isoformat()
        totals[day] = totals.get(day, 0) + amount
    return totals
