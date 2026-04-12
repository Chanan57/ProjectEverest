import tkinter as tk
import time
from datetime import datetime, timezone
import threading
import sys
import os

# Import the psychology logic purely for the UI display
import psychology
from market_hours import is_market_open

class EverestKiosk:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Everest Absolute Lockout")
        
        # Enforce fullscreen and absolute topmost rendering
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg='black')

        # Disable Alt+F4 closure
        self.root.protocol("WM_DELETE_WINDOW", self._disable_event)

        # UI Setup
        self.title_label = tk.Label(
            self.root, 
            text="🚨 Everest v8.0 IN CONTROL 🚨", 
            fg='red', bg='black', font=("Helvetica", 36, "bold")
        )
        self.title_label.pack(pady=100)

        self.quote_label = tk.Label(
            self.root, 
            text=self._get_wrapped_quote(), 
            fg='green', bg='black', font=("Courier", 24),
            justify='center'
        )
        self.quote_label.pack(expand=True)

        self.status_label = tk.Label(
            self.root, 
            text="Market Open | Mouse and Keyboard Locked", 
            fg='white', bg='black', font=("Arial", 16)
        )
        self.status_label.pack(side='bottom', pady=50)

        # Terminal is impenetrable
        self.root.unbind("<Key>")

        # Start background check loop for market hours and quote cycling
        self._check_market_status()
        self._cycle_quotes()

    def _update_ui_times(self):
        """Calculates the dynamically shifting Sydney time maintenance window based on NY close."""
        try:
            from zoneinfo import ZoneInfo
            from datetime import timedelta
            ny_tz = ZoneInfo("US/Eastern")
            syd_tz = ZoneInfo("Australia/Sydney")
            
            now_ny = datetime.now(ny_tz)
            
            # Target the 16:59 NY Time break
            next_break_start = now_ny.replace(hour=16, minute=59, second=0, microsecond=0)
            if now_ny > next_break_start:
                next_break_start += timedelta(days=1)
                
            next_break_end = next_break_start.replace(hour=18, minute=0, second=0, microsecond=0)
            
            syd_start = next_break_start.astimezone(syd_tz).strftime("%I:%M %p")
            syd_end = next_break_end.astimezone(syd_tz).strftime("%I:%M %p")
            
            msg = f"STATUS: OPERATIONAL & SECURED\nSystem is fully black-boxed until Friday Close."
            self.status_label.config(text=msg)
        except Exception:
            # Fallback if zoneinfo isn't working
            self.status_label.config(text="STATUS: OPERATIONAL & SECURED\nSystem is fully black-boxed until Friday Close.")

    def _disable_event(self):
        """Prevents Alt+F4 or window red-x closure."""
        pass

    def _get_wrapped_quote(self):
        import textwrap
        raw_quote = psychology.get_conditioning_quote()
        return textwrap.fill(raw_quote, width=50)

    # Removed local override key bindings to ensure unbreakable lock

    def _is_market_open(self):
        """Standardized market-status detection."""
        return is_market_open()

    def _is_bot_crashed(self):
        """Checks if the main.py heartbeat has stalled for more than 60 seconds."""
        import os
        import time as timer_lib
        try:
            if not os.path.exists("kiosk_heartbeat.tmp"):
                return True
            with open("kiosk_heartbeat.tmp", "r") as f:
                last_ping = float(f.read().strip())
            if (timer_lib.time() - last_ping) > 60.0:
                return True
            return False
        except Exception:
            return True # If it can't read the file, assume crash to be safe

    def _check_market_status(self):
        """Checks if the market is closed or bot has crashed to unlock the screen."""
        if not self._is_market_open() or self._is_bot_crashed():
            # Market is closed or bot died! Hide the Kiosk so user can repair/manage OS.
            self.root.withdraw()
            
            # Check less frequently when hidden
            self.root.after(5000, self._check_market_status)
            return
            
        # Market is OPEN. Show Kiosk and lock the screen aggressively.
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        
        # Loop every second to constantly enforce topmost
        self.root.after(1000, self._check_market_status)

    def _cycle_quotes(self):
        """Change the psychology quote every 30 seconds and update UI times."""
        self.quote_label.config(text=self._get_wrapped_quote())
        self._update_ui_times()
        self.root.after(30000, self._cycle_quotes)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    kiosk = EverestKiosk()
    kiosk.run()

