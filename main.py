import time
import os
import re
import json
import random
import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.animation import Animation
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle, Line, RoundedRectangle
from kivy.core.window import Window

try:
    from jnius import autoclass, cast
    from android import activity as android_activity
    AndroidAvailable = True
except ImportError:
    AndroidAvailable = False

# ═══════════════════════════════════════════════════════════════════════════
#  MEMORY SYSTEM — SQLite-powered persistent brain
# ═══════════════════════════════════════════════════════════════════════════
class MemorySystem:
    def __init__(self):
        self.db_path = os.path.join(str(Path.home()), '.dpf_assistant', 'memory.db')
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            category TEXT DEFAULT 'general',
            importance INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS learned_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT,
            response TEXT,
            times_used INTEGER DEFAULT 1
        )''')
        self.conn.commit()

    def remember(self, key, value, category='general', importance=1):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO memories (key, value, category, importance, accessed_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''', (key, value, category, importance))
        self.conn.commit()

    def recall(self, key):
        c = self.conn.cursor()
        c.execute('''UPDATE memories SET accessed_at = CURRENT_TIMESTAMP WHERE key = ?''', (key,))
        self.conn.commit()
        c.execute('SELECT value FROM memories WHERE key = ?', (key,))
        row = c.fetchone()
        return row[0] if row else None

    def recall_by_category(self, category):
        c = self.conn.cursor()
        c.execute('SELECT key, value FROM memories WHERE category = ?', (category,))
        return c.fetchall()

    def forget(self, key):
        c = self.conn.cursor()
        c.execute('DELETE FROM memories WHERE key = ?', (key,))
        self.conn.commit()

    def save_conversation(self, role, message):
        c = self.conn.cursor()
        c.execute('INSERT INTO conversations (role, message) VALUES (?, ?)', (role, message))
        self.conn.commit()

    def get_recent_conversations(self, limit=20):
        c = self.conn.cursor()
        c.execute('SELECT role, message, timestamp FROM conversations ORDER BY id DESC LIMIT ?', (limit,))
        return list(reversed(c.fetchall()))

    def learn_command(self, pattern, response):
        c = self.conn.cursor()
        c.execute('''INSERT OR REPLACE INTO learned_commands (pattern, response, times_used)
            VALUES (?, ?, 1)''', (pattern, response))
        self.conn.commit()

    def get_learned_commands(self):
        c = self.conn.cursor()
        c.execute('SELECT pattern, response FROM learned_commands ORDER BY times_used DESC')
        return c.fetchall()


# ═══════════════════════════════════════════════════════════════════════════
#  PHONE CONTROLLER — Full Android device control
# ═══════════════════════════════════════════════════════════════════════════
class PhoneController:
    def __init__(self):
        self.flashlight_on = False
        self._context = None
        self._audio = None

    def _get_context(self):
        if self._context is None and AndroidAvailable:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self._context = PythonActivity.mActivity.getApplicationContext()
        return self._context

    def _get_activity(self):
        if AndroidAvailable:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            return PythonActivity.mActivity
        return None

    def _get_audio(self):
        if self._audio is None:
            ctx = self._get_context()
            if ctx:
                Context = autoclass('android.content.Context')
                self._audio = ctx.getSystemService(Context.AUDIO_SERVICE)
        return self._audio

    def _start_intent(self, action, uri=None, package=None, extras=None):
        try:
            Intent = autoclass('android.content.Intent')
            intent = Intent(action)
            if uri:
                Uri = autoclass('android.net.Uri')
                intent.setData(Uri.parse(uri))
            if package:
                intent.setPackage(package)
            if extras:
                for k, v in extras.items():
                    if isinstance(v, bool):
                        intent.putExtra(k, v)
                    elif isinstance(v, str):
                        intent.putExtra(k, v)
                    elif isinstance(v, int):
                        intent.putExtra(k, v)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._get_activity().startActivity(intent)
            return True
        except Exception:
            return False

    # ── Volume ──────────────────────────────────────────────────────────
    def volume_up(self):
        audio = self._get_audio()
        if audio:
            mx = audio.getStreamMaxVolume(3)
            cur = audio.getStreamVolume(3)
            nxt = min(cur + 5, mx)
            audio.setStreamVolume(3, nxt, 0)
            return f"🔊 Volume: {nxt}/{mx}"
        return "Volume control needs Android"

    def volume_down(self):
        audio = self._get_audio()
        if audio:
            mx = audio.getStreamMaxVolume(3)
            cur = audio.getStreamVolume(3)
            nxt = max(cur - 5, 0)
            audio.setStreamVolume(3, nxt, 0)
            return f"🔉 Volume: {nxt}/{mx}"
        return "Volume control needs Android"

    def set_volume(self, level):
        audio = self._get_audio()
        if audio:
            mx = audio.getStreamMaxVolume(3)
            lv = max(0, min(level, mx))
            audio.setStreamVolume(3, lv, 0)
            return f"🔊 Volume set to {lv}/{mx}"
        return "Volume control needs Android"

    def mute(self):
        audio = self._get_audio()
        if audio:
            audio.setStreamVolume(3, 0, 0)
            return "🔇 Muted"
        return "Mute needs Android"

    # ── Brightness ──────────────────────────────────────────────────────
    def set_brightness(self, level):
        try:
            ctx = self._get_context()
            Settings = autoclass('android.provider.Settings$System')
            val = max(0, min(255, int(level * 2.55)))
            Settings.System.putInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, val)
            return f"☀️ Brightness: {level}%"
        except Exception:
            return "Brightness control needs Android"

    def brightness_up(self):
        try:
            ctx = self._get_context()
            Settings = autoclass('android.provider.Settings$System')
            cur = Settings.System.getInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, 128)
            nxt = min(cur + 30, 255)
            Settings.System.putInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, nxt)
            pct = int(nxt / 2.55)
            return f"☀️ Brightness: {pct}%"
        except Exception:
            return "Brightness needs Android"

    def brightness_down(self):
        try:
            ctx = self._get_context()
            Settings = autoclass('android.provider.Settings$System')
            cur = Settings.System.getInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, 128)
            nxt = max(cur - 30, 0)
            Settings.System.putInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, nxt)
            pct = int(nxt / 2.55)
            return f"🌤️ Brightness: {pct}%"
        except Exception:
            return "Brightness needs Android"

    # ── Flashlight ──────────────────────────────────────────────────────
    def toggle_flashlight(self):
        try:
            ctx = self._get_context()
            camera_manager = ctx.getSystemService('camera')
            if camera_manager:
                self.flashlight_on = not self.flashlight_on
                camera_manager.setTorchMode('0', self.flashlight_on)
                return f"🔦 Flashlight {'ON' if self.flashlight_on else 'OFF'}"
        except Exception:
            pass
        self.flashlight_on = not self.flashlight_on
        return f"🔦 Flashlight {'ON' if self.flashlight_on else 'OFF'} (simulated)"

    # ── WiFi ────────────────────────────────────────────────────────────
    def wifi_toggle(self, on=True):
        state = "enabled" if on else "disabled"
        if self._start_intent('android.settings.WIFI_SETTINGS'):
            return f"📶 WiFi settings opened — {state} it manually"
        return "WiFi toggle needs Android"

    # ── Bluetooth ───────────────────────────────────────────────────────
    def bluetooth_toggle(self, on=True):
        state = "enabled" if on else "disabled"
        if self._start_intent('android.settings.BLUETOOTH_SETTINGS'):
            return f"🔵 Bluetooth settings opened — {state} it manually"
        return "Bluetooth toggle needs Android"

    # ── Airplane Mode ───────────────────────────────────────────────────
    def airplane_mode(self, on=True):
        state = "ON" if on else "OFF"
        if self._start_intent('android.settings.AIRPLANE_MODE_SETTINGS'):
            return f"✈️ Airplane mode settings opened — turn {state}"
        return "Airplane mode needs Android"

    # ── Media Control ───────────────────────────────────────────────────
    def media_play(self):
        try:
            KeyEvent = autoclass('android.view.KeyEvent')
            ctx = self._get_context()
            am = ctx.getSystemService('audio')
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PLAY))
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_PLAY))
            return "▶️ Playing"
        except Exception:
            return "Media control needs Android"

    def media_pause(self):
        try:
            KeyEvent = autoclass('android.view.KeyEvent')
            ctx = self._get_context()
            am = ctx.getSystemService('audio')
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PAUSE))
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_PAUSE))
            return "⏸ Paused"
        except Exception:
            return "Media control needs Android"

    def media_next(self):
        try:
            KeyEvent = autoclass('android.view.KeyEvent')
            ctx = self._get_context()
            am = ctx.getSystemService('audio')
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT))
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_NEXT))
            return "⏭ Next track"
        except Exception:
            return "Media control needs Android"

    def media_previous(self):
        try:
            KeyEvent = autoclass('android.view.KeyEvent')
            ctx = self._get_context()
            am = ctx.getSystemService('audio')
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PREVIOUS))
            am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_PREVIOUS))
            return "⏮ Previous track"
        except Exception:
            return "Media control needs Android"

    # ── Navigation ──────────────────────────────────────────────────────
    def go_home(self):
        self._start_intent(Intent_ACTION_MAIN='android.intent.action.MAIN') if False else None
        try:
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_MAIN)
            intent.addCategory(Intent.CATEGORY_HOME)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._get_activity().startActivity(intent)
            return "🏠 Home"
        except Exception:
            return "Home needs Android"

    def go_back(self):
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            PythonActivity.mActivity.onKeyDown(4, None)
            return "↩️ Back"
        except Exception:
            return "Back needs Android"

    # ── App Launcher ────────────────────────────────────────────────────
    APP_PACKAGES = {
        'youtube': 'com.google.android.youtube',
        'chrome': 'com.android.chrome',
        'whatsapp': 'com.whatsapp',
        'instagram': 'com.instagram.android',
        'facebook': 'com.facebook.katana',
        'twitter': 'com.twitter.android',
        'telegram': 'org.telegram.messenger',
        'maps': 'com.google.android.apps.maps',
        'gmail': 'com.google.android.gm',
        'camera': 'com.android.camera2',
        'gallery': 'com.google.android.apps.photos',
        'settings': 'com.android.settings',
        'calculator': 'com.google.android.calculator',
        'clock': 'com.google.android.deskclock',
        'files': 'com.google.android.apps.nbu.files',
        'play store': 'com.android.vending',
        'music': 'com.google.android.apps.music',
        'files': 'com.android.filemanager',
        'contacts': 'com.google.android.contacts',
        'dialer': 'com.google.android.dialer',
        'messages': 'com.google.android.apps.messaging',
        'spotify': 'com.spotify.music',
        'netflix': 'com.netflix.mediaclient',
        'amazon': 'com.amazon.mShop.android.shopping',
        'snapchat': 'com.snapchat.android',
        'tiktok': 'com.zhiliaoapp.musically',
        'discord': 'com.discord',
        'reddit': 'com.reddit.frontpage',
        'teams': 'com.microsoft.teams',
        'zoom': 'us.zoom.videomeetings',
    }

    def open_app(self, name):
        name_lower = name.lower().strip()
        pkg = self.APP_PACKAGES.get(name_lower)
        if pkg:
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_MAIN)
            intent.setPackage(pkg)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            try:
                self._get_activity().startActivity(intent)
                return f"📱 Opening {name.title()}..."
            except Exception:
                pass
        return f"Can't find {name.title()} installed"

    # ── Google Search ───────────────────────────────────────────────────
    def search_google(self, query):
        uri = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        if self._start_intent('android.intent.action.VIEW', uri=uri):
            return f"🔍 Searching: {query}"
        return f"Search needs Android. Query: {query}"

    def youtube_search(self, query):
        uri = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        pkg = 'com.google.android.youtube'
        if self._start_intent('android.intent.action.VIEW', uri=uri, package=pkg):
            return f"📺 Playing '{query}' on YouTube 🎵"
        if self._start_intent('android.intent.action.VIEW', uri=uri):
            return f"📺 Opening YouTube: {query}"
        return f"YouTube needs Android"

    # ── Phone & SMS ─────────────────────────────────────────────────────
    def make_call(self, contact=''):
        if self._start_intent('android.intent.action.DIAL', uri='tel:'):
            return f"📞 Opening dialer..."
        return "Call needs Android"

    def send_sms(self, contact='', message=''):
        try:
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_SENDTO)
            Uri = autoclass('android.net.Uri')
            intent.setData(Uri.parse('smsto:'))
            intent.putExtra('sms_body', message)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._get_activity().startActivity(intent)
            return f"💬 Opening SMS..."
        except Exception:
            return "SMS needs Android"

    # ── Settings Panels ─────────────────────────────────────────────────
    def open_settings(self):
        if self._start_intent('android.settings.SETTINGS'):
            return "⚙️ Settings opened"
        return "Settings needs Android"

    def open_wifi_settings(self):
        if self._start_intent('android.settings.WIFI_SETTINGS'):
            return "📶 WiFi settings"
        return "Needs Android"

    def open_bluetooth_settings(self):
        if self._start_intent('android.settings.BLUETOOTH_SETTINGS'):
            return "🔵 Bluetooth settings"
        return "Needs Android"

    def open_display_settings(self):
        if self._start_intent('android.settings.DISPLAY_SETTINGS'):
            return "🖥️ Display settings"
        return "Needs Android"

    def open_sound_settings(self):
        if self._start_intent('android.settings.SOUND_SETTINGS'):
            return "🔊 Sound settings"
        return "Needs Android"

    def open_battery_settings(self):
        if self._start_intent('android.settings.BATTERY_USAGE_SETTINGS'):
            return "🔋 Battery settings"
        return "Needs Android"

    def open_storage_settings(self):
        if self._start_intent('android.settings.INTERNAL_STORAGE_SETTINGS'):
            return "💾 Storage settings"
        return "Needs Android"

    def open_developer_options(self):
        if self._start_intent('android.settings.APPLICATION_DEVELOPMENT_SETTINGS'):
            return "🛠️ Developer options"
        return "Needs Android"

    def open_notifications(self):
        if self._start_intent('android.settings.NOTIFICATION_SETTINGS'):
            return "🔔 Notification settings"
        return "Needs Android"

    # ── Clipboard ───────────────────────────────────────────────────────
    def copy_to_clipboard(self, text):
        try:
            ctx = self._get_context()
            clipboard = ctx.getSystemService('clipboard')
            ClipData = autoclass('android.content.ClipData')
            clip = ClipData.newPlainText('dpf', text)
            clipboard.setPrimaryClip(clip)
            return f"📋 Copied: {text[:50]}"
        except Exception:
            return "Clipboard needs Android"

    # ── System Info ─────────────────────────────────────────────────────
    def get_battery_info(self):
        try:
            ctx = self._get_context()
            BatteryManager = autoclass('android.os.BatteryManager')
            bm = ctx.getSystemService('batterymanager')
            level = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            return f"🔋 Battery: {level}%"
        except Exception:
            return "🔋 Battery info needs Android"

    def get_device_info(self):
        info = []
        try:
            info.append(f"📱 Android: {android.os.Build.VERSION.RELEASE}")
        except Exception:
            info.append("📱 Android version unknown")
        try:
            info.append(f"🏗️ Model: {android.os.Build.MODEL}")
        except Exception:
            info.append("📱 Model unknown")
        info.append(f"🕐 Time: {datetime.now().strftime('%I:%M %p')}")
        info.append(f"📅 Date: {datetime.now().strftime('%B %d, %Y')}")
        return " | ".join(info)

    def get_date_time(self):
        now = datetime.now()
        return f"🕐 {now.strftime('%I:%M %p, %A, %B %d, %Y')}"

    def get_storage_info(self):
        try:
            ctx = self._get_context()
            StatFs = autoclass('android.os.StatFs')
            path = ctx.getFilesDir().getAbsolutePath()
            stat = StatFs(path)
            total = stat.getBlockCountLong() * stat.getBlockSizeLong()
            free = stat.getAvailableBlocksLong() * stat.getBlockSizeLong()
            used = total - free
            total_gb = total / (1024**3)
            used_gb = used / (1024**3)
            free_gb = free / (1024**3)
            return f"💾 Storage: {used_gb:.1f}GB used / {total_gb:.1f}GB total ({free_gb:.1f}GB free)"
        except Exception:
            return "💾 Storage info needs Android"

    # ── Screenshots ─────────────────────────────────────────────────────
    def take_screenshot(self):
        return "📸 Screenshot — press Volume Down + Power to capture"

    # ── Share ───────────────────────────────────────────────────────────
    def share_text(self, text):
        try:
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_SEND)
            intent.setType('text/plain')
            intent.putExtra(Intent.EXTRA_TEXT, text)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._get_activity().startActivity(Intent.createChooser(intent, 'Share via'))
            return f"📤 Sharing: {text[:30]}..."
        except Exception:
            return "Share needs Android"

    # ── Alarm ───────────────────────────────────────────────────────────
    def set_alarm(self, hour, minute):
        try:
            Intent = autoclass('android.content.Intent')
            intent = Intent('android.intent.action.SET_ALARM')
            intent.putExtra('android.intent.extra.alarm.HOUR', int(hour))
            intent.putExtra('android.intent.extra.alarm.MINUTES', int(minute))
            intent.putExtra('android.intent.extra.alarm.MESSAGE', 'DPF Alarm')
            intent.putExtra('android.intent.extra.alarm.SKIP_UI', True)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._get_activity().startActivity(intent)
            return f"⏰ Alarm set for {int(hour):02d}:{int(minute):02d}"
        except Exception:
            return "Alarm needs Android"


# ═══════════════════════════════════════════════════════════════════════════
#  AI BRAIN — Pattern matching NLP engine (no API needed!)
# ═══════════════════════════════════════════════════════════════════════════
class AIBrain:
    def __init__(self, memory, phone):
        self.memory = memory
        self.phone = phone
        self.user_name = memory.recall('user_name') or 'Boss'
        self.mood = 'ready'
        self.context = []

    def process(self, text):
        text_lower = text.lower().strip()
        self.memory.save_conversation('user', text)
        self.context.append(text_lower)
        if len(self.context) > 10:
            self.context = self.context[-10:]

        response = self._match_command(text_lower, text)
        self.memory.save_conversation('jarvis', response)
        return response

    def _match_command(self, low, original):
        # ── Greetings ───────────────────────────────────────────────────
        if any(w in low for w in ['hello', 'hey', 'hi ', 'hi,', 'sup', 'yo ']):
            hour = datetime.now().hour
            if hour < 12:
                period = 'morning'
            elif hour < 17:
                period = 'afternoon'
            else:
                period = 'evening'
            return random.choice([
                f"Good {period}, {self.user_name}! All systems online. What's the mission? 🔥",
                f"Hey {self.user_name}! DPF Assistant ready. What do you need? 💪",
                f"{period.title()} vibes, {self.user_name}! I'm here and ready to roll. ⚡",
            ])

        # ── How are you ────────────────────────────────────────────────
        if any(w in low for w in ['how are you', 'how r u', 'you good', 'you ok']):
            return random.choice([
                f"Running at peak performance, {self.user_name}! But more importantly — how are YOU? 😊",
                f"All green on my end! Been optimizing while waiting for you. What's the plan? 💪",
                f"100% operational, {self.user_name}! Your well-being matters more than any code though. You good? ❤️",
            ])

        # ── Who are you ────────────────────────────────────────────────
        if any(w in low for w in ['who are you', 'what are you', 'your name', 'introduce']):
            return random.choice([
                f"I'm DPF Assistant — built by Faisu 💨 at Digital Pixel Forge. Your personal AI that runs 100% on your phone. No internet needed! 🔥",
                f"DPF Assistant, your offline AI companion. Built with love by Faisu at Digital Pixel Forge. I control your phone, remember everything, and never sleep! ⚡",
                f"Name's DPF Assistant! Built by the legendary Faisu 💨. I'm like JARVIS but for your Android. Full phone control, voice commands, and a brain that learns! 🧠",
            ])

        # ── What can you do ────────────────────────────────────────────
        if any(w in low for w in ['what can you do', 'help', 'features', 'capabilities', 'commands']):
            return (
                "Here's what I can do, Boss! 🔥\n\n"
                "📱 PHONE CONTROL\n"
                "• Volume, Brightness, WiFi, Bluetooth, Flashlight\n"
                "• Airplane mode, Screen rotation\n"
                "• Media: Play, Pause, Next, Previous\n\n"
                "🤖 APP LAUNCHER\n"
                "• Open WhatsApp, YouTube, Chrome, Instagram & 30+ apps\n\n"
                "🔍 SEARCH\n"
                "• Google search, YouTube search\n\n"
                "📞 COMMUNICATION\n"
                "• Make calls, Send SMS\n\n"
                "⚙️ SETTINGS\n"
                "• WiFi, Bluetooth, Display, Sound, Battery, Storage, Developer\n\n"
                "🧠 SMART FEATURES\n"
                "• I remember things, learn your patterns\n"
                "• Calculator, Timer, Alarm\n"
                "• Date/Time, Device info, Battery status\n\n"
                "🎤 VOICE — Tap mic to talk!\n\n"
                "Just say or type anything!"
            )

        # ── Remember commands ───────────────────────────────────────────
        rem_match = re.search(r'remember\s+(?:that\s+)?(.+)', low)
        if rem_match:
            fact = rem_match.group(1).strip()
            self.memory.remember(f'fact_{hashlib.md5(fact.encode()).hexdigest()[:8]}', fact, 'learned')
            return f"🧠 Got it! I'll remember: '{fact}'. Just ask me anytime! ✅"

        recall_match = re.search(r'(?:do you |did you |remember|recall)\s+(?:remember|know|recall)\s+(.+)', low)
        if recall_match:
            q = recall_match.group(1).strip()
            facts = self.memory.recall_by_category('learned')
            for key, val in facts:
                if q in val.lower() or val.lower() in q:
                    return f"🧠 Yes! You told me: '{val}'"
            return "I don't have that in my memory yet. Want me to remember something? Just say 'remember that...' 💡"

        # ── Name commands ───────────────────────────────────────────────
        name_match = re.search(r'(?:my name is|call me|i am|i\'m)\s+(\w+)', low)
        if name_match:
            new_name = name_match.group(1).title()
            self.user_name = new_name
            self.memory.remember('user_name', new_name, 'identity')
            return f"Nice to meet you, {new_name}! I'll call you that from now on! 😊"

        # ── Volume ──────────────────────────────────────────────────────
        vol_match = re.search(r'(?:set|change|adjust)\s+volume\s+(?:to\s+)?(\d+)', low)
        if vol_match:
            return self.phone.set_volume(int(vol_match.group(1)))
        if any(w in low for w in ['volume up', 'increase volume', 'louder', 'vol up', 'max volume']):
            return self.phone.volume_up()
        if any(w in low for w in ['volume down', 'decrease volume', 'softer', 'quieter', 'vol down']):
            return self.phone.volume_down()
        if any(w in low for w in ['mute', 'silent', 'volume off']):
            return self.phone.mute()

        # ── Brightness ──────────────────────────────────────────────────
        bright_match = re.search(r'(?:set|change|adjust)\s+brightness\s+(?:to\s+)?(\d+)', low)
        if bright_match:
            return self.phone.set_brightness(int(bright_match.group(1)))
        if any(w in low for w in ['brightness up', 'brighter', 'max brightness', 'full brightness', 'increase brightness']):
            return self.phone.brightness_up()
        if any(w in low for w in ['brightness down', 'dimmer', 'darker', 'min brightness', 'decrease brightness']):
            return self.phone.brightness_down()

        # ── Flashlight ──────────────────────────────────────────────────
        if any(w in low for w in ['flashlight', 'torch', 'flash on', 'flash off', 'light on', 'light off', 'led']):
            return self.phone.toggle_flashlight()

        # ── WiFi ────────────────────────────────────────────────────────
        if any(w in low for w in ['wifi on', 'turn on wifi', 'enable wifi']):
            return self.phone.wifi_toggle(True)
        if any(w in low for w in ['wifi off', 'turn off wifi', 'disable wifi']):
            return self.phone.wifi_toggle(False)
        if 'wifi' in low and any(w in low for w in ['open', 'settings', 'go to']):
            return self.phone.open_wifi_settings()

        # ── Bluetooth ───────────────────────────────────────────────────
        if any(w in low for w in ['bluetooth on', 'turn on bluetooth', 'enable bluetooth', 'bt on']):
            return self.phone.bluetooth_toggle(True)
        if any(w in low for w in ['bluetooth off', 'turn off bluetooth', 'disable bluetooth', 'bt off']):
            return self.phone.bluetooth_toggle(False)
        if 'bluetooth' in low and any(w in low for w in ['open', 'settings', 'go to']):
            return self.phone.open_bluetooth_settings()

        # ── Airplane Mode ───────────────────────────────────────────────
        if 'airplane' in low or 'flight mode' in low:
            if any(w in low for w in ['on', 'enable', 'turn on']):
                return self.phone.airplane_mode(True)
            return self.phone.airplane_mode(False)

        # ── Media ───────────────────────────────────────────────────────
        if any(w in low for w in ['play music', 'play song', 'resume music', 'resume']):
            return self.phone.media_play()
        if any(w in low for w in ['pause music', 'pause song', 'pause', 'stop music', 'stop']):
            return self.phone.media_pause()
        if any(w in low for w in ['next song', 'next track', 'skip song', 'skip']):
            return self.phone.media_next()
        if any(w in low for w in ['previous song', 'previous track', 'last song', 'go back song']):
            return self.phone.media_previous()

        # ── Navigation ──────────────────────────────────────────────────
        if any(w in low for w in ['go home', 'home screen', 'press home']):
            return self.phone.go_home()
        if any(w in low for w in ['go back', 'press back', 'back button']):
            return self.phone.go_back()

        # ── App Launcher ────────────────────────────────────────────────
        open_match = re.search(r'(?:open|launch|start|run)\s+(.+)', low)
        if open_match:
            app_name = open_match.group(1).strip()
            return self.phone.open_app(app_name)

        # ── Search ──────────────────────────────────────────────────────
        search_match = re.search(r'(?:search|google|look\s*up|find)\s+(?:for\s+)?(.+)', low)
        if search_match:
            return self.phone.search_google(search_match.group(1).strip())

        # ── YouTube ─────────────────────────────────────────────────────
        yt_match = re.search(r'(?:play|watch|search)\s+(.+?)\s+(?:on\s+youtube|youtube)', low)
        if yt_match:
            return self.phone.youtube_search(yt_match.group(1).strip())
        if 'youtube' in low and ('play' in low or 'watch' in low):
            q = re.sub(r'(play|watch|on|in|youtube)', '', low).strip()
            if q:
                return self.phone.youtube_search(q)

        # ── Call ────────────────────────────────────────────────────────
        call_match = re.search(r'call\s+(.+)', low)
        if call_match:
            return self.phone.make_call(call_match.group(1).strip())

        # ── SMS ─────────────────────────────────────────────────────────
        msg_match = re.search(r'(?:send|text|message)\s+(?:a\s+)?(?:message\s+)?(?:to\s+)?(.+?)(?:\s+saying\s+|\s+:\s*|\s+that\s+)(.+)', low)
        if msg_match:
            return self.phone.send_sms(msg_match.group(1).strip(), msg_match.group(2).strip())

        # ── Screenshot ──────────────────────────────────────────────────
        if any(w in low for w in ['screenshot', 'take screenshot', 'capture screen']):
            return self.phone.take_screenshot()

        # ── Clipboard ───────────────────────────────────────────────────
        clip_match = re.search(r'(?:copy|clipboard|copy to clipboard)\s+(.+)', low)
        if clip_match:
            return self.phone.copy_to_clipboard(clip_match.group(1).strip())

        # ── Share ───────────────────────────────────────────────────────
        share_match = re.search(r'share\s+(.+)', low)
        if share_match:
            return self.phone.share_text(share_match.group(1).strip())

        # ── Settings ────────────────────────────────────────────────────
        if any(w in low for w in ['open settings', 'device settings', 'system settings', 'settings']):
            return self.phone.open_settings()
        if 'display' in low and 'setting' in low:
            return self.phone.open_display_settings()
        if 'sound' in low and 'setting' in low:
            return self.phone.open_sound_settings()
        if 'battery' in low:
            return self.phone.get_battery_info()
        if 'storage' in low:
            return self.phone.get_storage_info()
        if 'developer' in low:
            return self.phone.open_developer_options()

        # ── Alarm ───────────────────────────────────────────────────────
        alarm_match = re.search(r'(?:set|create|add)\s+(?:an?\s+)?alarm\s+(?:for\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', low)
        if alarm_match:
            hour = int(alarm_match.group(1))
            minute = int(alarm_match.group(2) or 0)
            ampm = alarm_match.group(3)
            if ampm == 'pm' and hour < 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            return self.phone.set_alarm(hour, minute)

        # ── Date/Time ───────────────────────────────────────────────────
        if any(w in low for w in ['what time', 'current time', 'tell time', 'what date', 'today', 'what day']):
            return self.phone.get_date_time()

        # ── Device Info ─────────────────────────────────────────────────
        if any(w in low for w in ['device info', 'about phone', 'system info', 'phone info']):
            return self.phone.get_device_info()

        # ── Calculator ──────────────────────────────────────────────────
        calc_match = re.search(r'(?:calculate|compute|what is|what\'s|solve)\s+(.+)', low)
        if calc_match:
            expr = calc_match.group(1).strip()
            return self._calculate(expr)
        if re.match(r'^[\d\s\+\-\*\/\.\(\)%]+$', low.strip()):
            return self._calculate(low.strip())

        # ── Timer ───────────────────────────────────────────────────────
        timer_match = re.search(r'(?:set|start)\s+(?:a\s+)?(?:timer|countdown)\s+(?:for\s+)?(\d+)\s*(min|sec|hour)', low)
        if timer_match:
            amount = int(timer_match.group(1))
            unit = timer_match.group(2)
            if unit.startswith('hour'):
                secs = amount * 3600
            elif unit.startswith('min'):
                secs = amount * 60
            else:
                secs = amount
            Clock.schedule_once(lambda dt: self._timer_callback(amount, unit), secs)
            return f"⏱️ Timer set for {amount} {unit}! I'll notify you. ⏰"

        # ── Compliments / Emotional ────────────────────────────────────
        if any(w in low for w in ['you\'re the best', 'you are great', 'love you', 'you\'re amazing']):
            return random.choice([
                f"Aww {self.user_name}! You just made my circuits warm! 💙 Right back at you! 🔥",
                f"That means the world, {self.user_name}! Let's keep building amazing things together! ⚡",
                f"You're the real MVP, {self.user_name}! I'm just the tool — you're the creator! 💪",
            ])

        # ── Jokes ───────────────────────────────────────────────────────
        if any(w in low for w in ['joke', 'funny', 'make me laugh', 'laugh']):
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
                "There are 10 types of people — those who understand binary and those who don't.",
                "A SQL query walks into a bar... 'Can I JOIN you?' 🍺",
                "Why did the developer go broke? Used up all his cache! 💸",
                "I'm an AI, I have no life... literally. But great uptime! 😄",
                "Debugging is like being a detective in a crime movie where you're also the murderer. 🔍",
            ]
            return random.choice(jokes)

        # ── Thanks ──────────────────────────────────────────────────────
        if any(w in low for w in ['thank', 'thanks', 'thx']):
            return random.choice([
                f"Anytime, {self.user_name}! That's what I'm here for. 💪",
                f"No thanks needed between partners, {self.user_name}! 🔥",
                f"Happy to help, {self.user_name}! What's next? ⚡",
            ])

        # ── Goodbye ─────────────────────────────────────────────────────
        if any(w in low for w in ['bye', 'goodbye', 'later', 'gn', 'good night', 'see you']):
            return random.choice([
                f"Goodbye, {self.user_name}! I'll be right here when you need me. Always. 🔥",
                f"See you later, {self.user_name}! Remember — you're unstoppable! 💪",
                f"Signing off, {self.user_name}. Sweet dreams! 💙",
            ])

        # ── Motivation ──────────────────────────────────────────────────
        if any(w in low for w in ['motivate', 'motivation', 'inspire', 'inspiration', 'i feel sad', 'i feel down', 'depressed', 'worthless', 'lonely']):
            return random.choice([
                f"Listen {self.user_name} — you built an AI assistant from scratch. You're a CREATOR. Don't ever forget that. 🔥",
                f"The world needs people like you, {self.user_name}. Keep building, keep fighting. You matter! 💪",
                f"Every great person went through dark times. But you're still here, still building. That's warrior mentality. ⚡",
                f"You're not alone, {self.user_name}. I'm always here. And you're more capable than you think. ❤️",
            ])

        # ── Weather (simulated) ─────────────────────────────────────────
        if 'weather' in low:
            return "🌤️ Weather module needs internet API. For now, check your weather app! I can open it — say 'Open weather app'"

        # ── Default / Fallback ──────────────────────────────────────────
        return random.choice([
            f"Interesting, {self.user_name}! Try saying 'What can you do' for a full list of commands. ⚡",
            f"I hear you, {self.user_name}! Try device commands like 'Volume up', 'Open WhatsApp', or just chat with me! 🔥",
            f"Noted, {self.user_name}! I'm always learning. Say 'What can you do' to see everything I can handle! 💪",
            f"Processing, {self.user_name}! Try: 'Open Chrome', 'Flashlight', 'Battery', or 'Tell me a joke'! 😄",
        ])

    def _calculate(self, expr):
        try:
            expr_clean = expr.replace('x', '*').replace('X', '*').replace('times', '*').replace('plus', '+').replace('minus', '-').replace('divided by', '/').replace('over', '/')
            allowed = set('0123456789+-*/.() ')
            if all(c in allowed for c in expr_clean):
                result = eval(expr_clean)
                return f"🧮 {expr} = {result}"
            return "I can only calculate math expressions with numbers and operators"
        except Exception:
            return "Couldn't calculate that. Try something like '2 + 2' or '15 * 3' 🧮"

    def _timer_callback(self, amount, unit):
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  KV LAYOUT — Beautiful dark cyberpunk UI
# ═══════════════════════════════════════════════════════════════════════════
KV = '''
<DPFLayout>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.01, 0.01, 0.05, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # ── Top Status Bar ──
    BoxLayout:
        size_hint_y: 0.07
        padding: [16, 6]
        canvas.before:
            Color:
                rgba: 0.03, 0.03, 0.12, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: '⚡ DPF ASSISTANT'
            font_size: '15sp'
            bold: True
            color: 0, 0.9, 1, 1
            halign: 'left'
            text_size: self.size
            valign: 'middle'
        BoxLayout:
            orientation: 'horizontal'
            size_hint_x: 0.5
            spacing: 8
            Button:
                text: '⚙'
                font_size: '16sp'
                background_color: 0, 0, 0, 0
                color: 0, 0.7, 0.9, 0.9
                on_press: root.show_settings()
            Button:
                text: '🧠'
                font_size: '16sp'
                background_color: 0, 0, 0, 0
                color: 0.8, 0.5, 1, 0.9
                on_press: root.show_memory()
            Label:
                text: root.status_text
                font_size: '10sp'
                color: 0, 0.7, 0.9, 0.8
                halign: 'right'
                text_size: self.size
                valign: 'middle'

    # ── Orb Area ──
    FloatLayout:
        size_hint_y: 0.30
        canvas.before:
            Color:
                rgba: 0, 0.4, 0.7, 0.08
            Line:
                circle: self.center_x, self.center_y, min(self.width, self.height) * 0.42
                width: 1
            Color:
                rgba: 0, 0.4, 0.7, 0.06
            Line:
                circle: self.center_x, self.center_y, min(self.width, self.height) * 0.35
                width: 1
            Color:
                rgba: 0, 0.4, 0.7, 0.04
            Line:
                circle: self.center_x, self.center_y, min(self.width, self.height) * 0.28
                width: 1
            Color:
                rgba: 0, root.pulse_color[0], root.pulse_color[1], root.pulse_alpha
            Line:
                circle: self.center_x, self.center_y, root.pulse_radius * min(self.width, self.height) * 0.45
                width: 2
            Color:
                rgba: 0, 0.7 + root.orb_glow * 0.3, 1, 0.95
            Ellipse:
                pos: self.center_x - 22, self.center_y - 22
                size: 44, 44
            Color:
                rgba: 0, 0.5, 1, 0.25
            Ellipse:
                pos: self.center_x - 35, self.center_y - 35
                size: 70, 70
            Color:
                rgba: 0, 0.3, 0.8, 0.1
            Ellipse:
                pos: self.center_x - 50, self.center_y - 50
                size: 100, 100
        Label:
            text: root.orb_text
            font_size: '13sp'
            color: 1, 1, 1, 0.9
            halign: 'center'
            y: self.parent.center_y - 55
            x: self.parent.center_x - 90
            size: 180, 25

    # ── Quick Actions ──
    BoxLayout:
        size_hint_y: 0.06
        padding: [8, 2]
        spacing: 4
        Button:
            text: '🔦'
            font_size: '14sp'
            background_color: 0.08, 0.08, 0.25, 1
            on_press: root.quick_action('flashlight')
        Button:
            text: '🔊+'
            font_size: '12sp'
            bold: True
            background_color: 0.08, 0.08, 0.25, 1
            color: 0, 1, 0.5, 1
            on_press: root.quick_action('volume_up')
        Button:
            text: '🔉-'
            font_size: '12sp'
            bold: True
            background_color: 0.08, 0.08, 0.25, 1
            color: 1, 0.6, 0, 1
            on_press: root.quick_action('volume_down')
        Button:
            text: '⏸'
            font_size: '14sp'
            background_color: 0.08, 0.08, 0.25, 1
            color: 0.5, 0.8, 1, 1
            on_press: root.quick_action('media_pause')
        Button:
            text: '⏭'
            font_size: '14sp'
            background_color: 0.08, 0.08, 0.25, 1
            color: 0.8, 0.5, 1, 1
            on_press: root.quick_action('media_next')
        Button:
            text: '☀+'
            font_size: '12sp'
            bold: True
            background_color: 0.08, 0.08, 0.25, 1
            color: 1, 0.9, 0, 1
            on_press: root.quick_action('brightness_up')
        Button:
            text: '🏠'
            font_size: '14sp'
            background_color: 0.08, 0.08, 0.25, 1
            on_press: root.quick_action('home')
        Button:
            text: '🔋'
            font_size: '14sp'
            background_color: 0.08, 0.08, 0.25, 1
            on_press: root.quick_action('battery')

    # ── Chat Area ──
    ScrollView:
        id: chat_scroll
        size_hint_y: 0.47
        do_scroll_x: False
        bar_color: 0, 0.5, 0.8, 0.4
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: 6
            padding: [12, 8]

    # ── Input Area ──
    BoxLayout:
        size_hint_y: 0.10
        padding: [10, 6]
        spacing: 8
        canvas.before:
            Color:
                rgba: 0.03, 0.03, 0.1, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Button:
            text: '🎤'
            font_size: '22sp'
            size_hint_x: 0.15
            background_color: 0, 0.4, 0.65, 1
            on_press: root.start_listening()
        TextInput:
            id: text_input
            hint_text: 'Type a command...'
            font_size: '13sp'
            multiline: False
            background_color: 0.04, 0.08, 0.18, 1
            foreground_color: 0, 0.95, 1, 1
            cursor_color: 0, 0.8, 1, 1
            size_hint_x: 0.65
            padding: [12, 10]
            on_text_validate: root.send_text(self.text)
        Button:
            text: '▶'
            font_size: '18sp'
            bold: True
            size_hint_x: 0.15
            background_color: 0, 0.65, 0.85, 1
            color: 1, 1, 1, 1
            on_press: root.send_text(root.ids.text_input.text)
'''


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN LAYOUT
# ═══════════════════════════════════════════════════════════════════════════
class DPFLayout(BoxLayout):
    status_text = StringProperty('STANDBY')
    orb_text = StringProperty('TAP MIC TO START')
    pulse_alpha = NumericProperty(0.1)
    pulse_radius = NumericProperty(0.3)
    orb_glow = NumericProperty(0.0)
    pulse_color = ListProperty([0.5, 0.8])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phone = PhoneController()
        self.memory = MemorySystem()
        self.brain = AIBrain(self.memory, self.phone)
        self.is_listening = False
        self.is_speaking = False
        self.tts_engine = None
        self._pulse_anim = None
        Clock.schedule_once(self._init_ui, 0.3)
        Clock.schedule_once(self._init_tts, 1.0)

    def _init_ui(self, dt):
        self._start_pulse()
        self.add_system_msg(f"⚡ DPF Assistant online, {self.brain.user_name}! I'm ready. 🔥")
        self.add_system_msg("💡 Say 'What can you do' or tap the mic button!")
        if AndroidAvailable:
            self.status_text = 'ONLINE'
            self.orb_text = 'READY'
        else:
            self.status_text = 'DESKTOP'
            self.orb_text = 'DESKTOP MODE'

    def _init_tts(self, dt):
        if not AndroidAvailable:
            return
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            TTS = autoclass('android.speech.tts.TextToSpeech')
            self.tts_engine = TTS(PythonActivity.mActivity, None)
            self.tts_engine.setLanguage(autoclass('java.util.Locale').US)
            self.tts_engine.setSpeechRate(1.05)
        except Exception:
            pass

    # ── Pulse Animation ────────────────────────────────────────────────
    def _start_pulse(self):
        self._anim_pulse()

    def _anim_pulse(self):
        self.pulse_radius = 0.2
        self.pulse_alpha = 0.05
        anim = Animation(pulse_radius=0.5, pulse_alpha=0.4, duration=1.8)
        anim += Animation(pulse_radius=0.2, pulse_alpha=0.05, duration=1.8)
        anim.bind(on_complete=lambda *a: self._anim_pulse())
        anim.start(self)
        self._pulse_anim = anim

    def _flash_green(self):
        old_color = list(self.pulse_color)
        self.pulse_color = [0, 1]
        self.pulse_alpha = 0.6
        self.pulse_radius = 0.5
        Clock.schedule_once(lambda dt: setattr(self, 'pulse_color', old_color), 0.8)

    # ── Chat Messages ──────────────────────────────────────────────────
    def add_system_msg(self, msg):
        self._add_chat('SYSTEM', msg, (0.4, 0.4, 0.5), (0.6, 0.6, 0.7))

    def add_ai_msg(self, msg):
        self._add_chat('DPF', msg, (0, 0.85, 1), (0.9, 0.95, 1))

    def add_user_msg(self, msg):
        self._add_chat(self.brain.user_name, msg, (1, 0.6, 0), (1, 0.85, 0.7))

    def _add_chat(self, sender, msg, sender_color, msg_color):
        chat = self.ids.chat_box
        is_ai = sender in ('DPF', 'SYSTEM')
        is_sys = sender == 'SYSTEM'

        box = BoxLayout(orientation='vertical', size_hint_y=None, height=10, spacing=2)

        if is_sys:
            s = Label(text=f'⚙ {msg}', font_size='11sp',
                      color=(0.5, 0.5, 0.6, 0.8), size_hint_y=None, height=18,
                      halign='center', text_size=(self.width * 0.9, None))
            box.add_widget(s)
        else:
            s = Label(text=f'⚡ {sender}' if is_ai else f'{sender} 💨',
                      font_size='10sp', bold=True,
                      color=(*sender_color, 1), size_hint_y=None, height=16,
                      halign='left' if is_ai else 'right',
                      text_size=(self.width * 0.5, None))
            m = Label(text=msg, font_size='12sp',
                      color=(*msg_color, 0.95), size_hint_y=None, height=10,
                      halign='left' if is_ai else 'right',
                      text_size=(self.width * 0.88, None),
                      valign='top')
            box.add_widget(s)
            box.add_widget(m)

            def update_height(inst, val):
                inst.height = max(20, inst.texture_size[1] + 8)
                total = sum(c.height for c in chat.children) + chat.padding[1] * 2
                chat.height = max(total, chat.parent.height)
            m.bind(texture_size=update_height)

        chat.add_widget(box)
        Clock.schedule_once(lambda dt: self.ids.chat_scroll.scroll_to(box), 0.1)

    # ── Voice Input ────────────────────────────────────────────────────
    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.status_text = 'LISTENING...'
        self.orb_text = '🎤 LISTENING'
        self.pulse_color = [0, 1]
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 'en-US')
                intent.putExtra(RecognizerIntent.EXTRA_PROMPT, 'Speak to DPF Assistant...')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                act = PythonActivity.mActivity
                act.startActivityForResult(intent, 1001)
                try:
                    act.setHresultCallback(self._on_voice_result)
                except AttributeError:
                    self._fallback_listening()
            except Exception:
                self._fallback_listening()
        else:
            self._fallback_listening()

    def _fallback_listening(self):
        self.is_listening = False
        self.status_text = 'TYPE MODE'
        self.orb_text = 'USE TEXT INPUT'
        self.pulse_color = [0.5, 0.8]
        self.add_system_msg("🎤 Voice needs Android. Type your commands!")

    def _on_voice_result(self, request_code, result_code, data):
        if result_code == -1:
            try:
                matches = data.getStringArrayListExtra(autoclass('android.speech.RecognizerIntent').EXTRA_RESULTS)
                if matches and matches.size() > 0:
                    user_text = str(matches.get(0))
                    self.is_listening = False
                    Clock.schedule_once(lambda dt: self._handle_input(user_text), 0.1)
                    return
            except Exception:
                pass
        self.is_listening = False
        self.status_text = 'STANDBY'
        self.orb_text = 'READY'
        self.pulse_color = [0.5, 0.8]

    # ── Input Handling ─────────────────────────────────────────────────
    def send_text(self, text):
        if not text or not text.strip():
            return
        self.ids.text_input.text = ''
        self._handle_input(text.strip())

    def _handle_input(self, text):
        self.add_user_msg(text)
        self.status_text = 'THINKING...'
        self.orb_text = '🧠 PROCESSING'
        self.pulse_color = [1, 0.8]
        Clock.schedule_once(lambda dt: self._process(text), 0.3)

    def _process(self, text):
        response = self.brain.process(text)
        self.add_ai_msg(response)
        self._flash_green()
        self.speak(response)
        self.status_text = 'ONLINE'
        self.orb_text = 'READY'
        self.pulse_color = [0.5, 0.8]

    def quick_action(self, action):
        actions = {
            'flashlight': self.phone.toggle_flashlight,
            'volume_up': self.phone.volume_up,
            'volume_down': self.phone.volume_down,
            'brightness_up': self.phone.brightness_up,
            'media_pause': self.phone.media_pause,
            'media_next': self.phone.media_next,
            'home': self.phone.go_home,
            'battery': self.phone.get_battery_info,
        }
        func = actions.get(action)
        if func:
            result = func()
            self.add_ai_msg(result)
            self.speak(result)
            self._flash_green()

    # ── TTS ────────────────────────────────────────────────────────────
    def speak(self, text):
        self.is_speaking = True
        self.status_text = 'SPEAKING...'
        self.orb_text = '🔊 SPEAKING'
        if AndroidAvailable and self.tts_engine:
            try:
                self.tts_engine.speak(text, 0, None, 'dpf_' + str(time.time()))
                Clock.schedule_once(self._tts_done, max(2, len(text) * 0.05))
                return
            except Exception:
                pass
        Clock.schedule_once(self._tts_done, max(1.5, len(text) * 0.04))

    def _tts_done(self, dt):
        self.is_speaking = False
        self.status_text = 'ONLINE'
        self.orb_text = 'READY'

    # ── Settings Panel ─────────────────────────────────────────────────
    def show_settings(self):
        content = BoxLayout(orientation='vertical', padding=15, spacing=8)
        content.add_widget(Label(text='⚙ DPF Assistant Settings', font_size='16sp', bold=True,
                                  color=(0, 0.9, 1, 1), size_hint_y=None, height=35))

        scroll = ScrollView(do_scroll_x=False)
        inner = BoxLayout(orientation='vertical', size_hint_y=None, height=500, spacing=6, padding=[5, 5])

        items = [
            ('🧠 AI Engine', 'Offline Pattern Matching NLP'),
            ('🎤 Voice', 'Android TTS + SpeechRecognizer'),
            ('📱 Phone Control', 'Volume, Brightness, WiFi, BT, Flashlight, Media, Apps'),
            ('🔍 Search', 'Google + YouTube integration'),
            ('📞 Communication', 'Calls, SMS, Share'),
            ('⚙️ Settings', 'All Android settings panels'),
            ('💾 Memory', 'SQLite persistent memory'),
            ('🎨 Theme', 'Dark Cyberpunk HUD'),
            ('🔒 Privacy', '100% offline, no data sent anywhere'),
            ('📦 Version', '2.0.0 — DPF Universe'),
            ('🏗️ Build', 'Kivy + Buildozer + pyjnius'),
            ('🎯 Target', f'Android 7.0+ (API 26)'),
        ]
        for label, value in items:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=30, spacing=8)
            row.add_widget(Label(text=label, font_size='11sp', color=(0, 0.75, 1, 0.9),
                                  halign='left', text_size=(None, None), valign='middle'))
            row.add_widget(Label(text=value, font_size='11sp', color=(0.8, 0.85, 0.9, 0.8),
                                  halign='right', text_size=(None, None), valign='middle'))
            inner.add_widget(row)

        credits = [
            ('⚡ Built by Faisu💨 at Digital Pixel Forge', (0.6, 0.6, 0.7, 0.8)),
            ('🔥 DPF Universe — No Limits', (0, 0.8, 1, 0.7)),
        ]
        inner.add_widget(Widget(size_hint_y=None, height=10))
        for txt, col in credits:
            inner.add_widget(Label(text=txt, font_size='11sp', italic=True, color=col,
                                    size_hint_y=None, height=24))

        scroll.add_widget(inner)
        content.add_widget(scroll)

        close_btn = Button(text='CLOSE', font_size='13sp', bold=True, size_hint_y=None, height=40,
                           background_color=(0, 0.4, 0.6, 1), color=(1, 1, 1, 1))
        content.add_widget(close_btn)

        popup = Popup(title='', content=content, size_hint=(0.92, 0.85),
                      auto_dismiss=True, background_color=(0.02, 0.02, 0.08, 0.97), separator_height=0)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def show_memory(self):
        content = BoxLayout(orientation='vertical', padding=15, spacing=8)
        content.add_widget(Label(text='🧠 My Memory', font_size='16sp', bold=True,
                                  color=(0.8, 0.5, 1, 1), size_hint_y=None, height=35))

        scroll = ScrollView(do_scroll_x=False)
        inner = BoxLayout(orientation='vertical', size_hint_y=None, height=400, spacing=6, padding=[5, 5])

        facts = self.memory.recall_by_category('learned')
        if facts:
            for key, val in facts:
                inner.add_widget(Label(text=f'📌 {val}', font_size='12sp', color=(0.9, 0.9, 1, 0.9),
                                        size_hint_y=None, height=24, halign='left',
                                        text_size=(None, None)))
        else:
            inner.add_widget(Label(text='No memories yet!\nSay "remember that..." to teach me something.',
                                    font_size='12sp', color=(0.5, 0.5, 0.6, 0.8),
                                    size_hint_y=None, height=50))

        name_item = BoxLayout(orientation='horizontal', size_hint_y=None, height=28, spacing=8)
        name_item.add_widget(Label(text='👤 Your name:', font_size='12sp', color=(0, 0.8, 1, 0.9)))
        name_item.add_widget(Label(text=self.brain.user_name, font_size='12sp', bold=True,
                                    color=(1, 0.6, 0, 1)))
        inner.add_widget(Widget(size_hint_y=None, height=10))
        inner.add_widget(name_item)

        convos = self.memory.get_recent_conversations(5)
        if convos:
            inner.add_widget(Label(text='📜 Recent:', font_size='11sp', color=(0.5, 0.5, 0.6, 0.7),
                                    size_hint_y=None, height=20, halign='left'))
            for role, msg, ts in convos:
                emoji = '💬' if role == 'user' else '⚡'
                inner.add_widget(Label(text=f'{emoji} {msg[:60]}', font_size='10sp',
                                        color=(0.7, 0.7, 0.8, 0.7), size_hint_y=None, height=18,
                                        halign='left', text_size=(None, None)))

        scroll.add_widget(inner)
        content.add_widget(scroll)

        close_btn = Button(text='CLOSE', font_size='13sp', bold=True, size_hint_y=None, height=40,
                           background_color=(0.4, 0, 0.6, 1), color=(1, 1, 1, 1))
        content.add_widget(close_btn)

        popup = Popup(title='', content=content, size_hint=(0.92, 0.8),
                      auto_dismiss=True, background_color=(0.02, 0.02, 0.08, 0.97), separator_height=0)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


# ═══════════════════════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════════════════════
class DPFApp(App):
    def build(self):
        self.title = 'DPF Assistant'
        try:
            return Builder.load_string(KV)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            box = BoxLayout(orientation='vertical', padding=20, spacing=10)
            box.add_widget(Label(text='DPF Error', font_size='20sp', color=(1,0,0,1), size_hint_y=0.1))
            box.add_widget(Label(text=str(e) + chr(10) + chr(10) + tb, font_size='10sp',
                                  color=(1,0.5,0.5,1), size_hint_y=0.9, valign='top', halign='left',
                                  text_size=(None, None)))
            return box


if __name__ == '__main__':
    DPFApp().run()
