"""
Everest v8.0 — Market Hours Utility
===================================
Unified source of truth for XAUUSD market status.
Synchronized with exact broker schedules (US/Eastern anchor).
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def is_market_open():
    """
    Determines if the XAUUSD market is currently OPEN based on the exact broker schedule:
    Broker Time:    Monday-Thursday 01:00-23:59 | Friday 01:00-23:57 | Sunday Closed (Opens Mon 01:00)
    New York Time:  Sunday 18:00 -> Friday 16:57
    
    Returns: bool (True if market is open/quotes running, False if closed/weekend).
    """
    try:
        ny_time = datetime.now(ZoneInfo("US/Eastern"))
    except Exception:
        # Fallback to loose UTC if zoneinfo fails
        now_utc = datetime.now(timezone.utc)
        if now_utc.weekday() == 5: return False
        return True

    wd = ny_time.weekday() # Monday=0, Sunday=6
    hr = ny_time.hour
    mn = ny_time.minute

    # Saturday = 5 (Closed all day)
    if wd == 5:
        return False
        
    # Friday = 4 (Quotes halt exactly at 16:57 NY Time)
    if wd == 4:
        if hr >= 17 or (hr == 16 and mn >= 57):
            return False
            
    # Sunday = 6 (Market opens at exactly 18:00 NY Time)
    if wd == 6:
        if hr < 18:
            return False
            
    # Mon-Thu = 0, 1, 2, 3
    # No mid-week breaks enforced in v8.0 (24/5 lockout)
    
    return True

if __name__ == "__main__":
    # Test script
    status = "OPEN" if is_market_open() else "CLOSED"
    print(f"Current Market Status: {status}")

