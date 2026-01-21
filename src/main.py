#!/usr/bin/env python3
"""
TCDD E-Bilet Checker - Ana giriş noktası

Kullanım:
    python -m src.main

veya:
    python src/main.py
"""
import sys
import os

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interfaces.telegram import TelegramBot


def main():
    """Ana giriş noktası"""
    bot = TelegramBot()
    bot.run()


if __name__ == "__main__":
    main()
