from __future__ import annotations
import time
from gpiozero import Buzzer

class BuzzerController:
    def __init__(self, pin: int):
        self.bz = Buzzer(pin)
        self._on = False
    
    def on(self):
        self.bz.on()
        self._on = True
    
    def off(self):
        self.bz.off()
        self._on = False
    
    def beep_pattern_3_short(self):
        for _ in range(3):
            self.on()
            time.sleep(0.12)
            self.off()
            time.sleep(0.10)
        
    @property
    def is_on(self) -> bool:
        return self._on
    
    def close(self):
        self.off()
        self.bz.close()