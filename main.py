import time
import os
import re
import random
import traceback
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty
from kivy.animation import Animation
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label as KivyLabel

try:
    from jnius import autoclass, cast
    from android import activity
    AndroidAvailable = True
except ImportError:
    AndroidAvailable = False

# ─── Android Helpers ────────────────────────────────────────────────────────
def get_activity():
    if AndroidAvailable:
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        return PythonActivity.mActivity
    return None

def get_context():
    if AndroidAvailable:
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        return PythonActivity.mActivity.getApplicationContext()
    return None

def send_intent(action, uri=None, package=None, extras=None, flags=None):
    """Universal intent sender"""
    try:
        Intent = autoclass('android.content.Intent')
        intent = Intent(action)
        if uri:
            Uri = autoclass('android.net.Uri')
            intent.setData(Uri.parse(uri))
        if package:
            intent.setPackage(package)
        if extras:
            for key, val in extras.items():
                if isinstance(val, bool):
                    intent.putExtra(key, val)
                elif isinstance(val, str):
                    intent.putExtra(key, val)
                elif isinstance(val, int):
                    intent.putExtra(key, val)
        if flags:
            for f in flags:
                intent.setFlags(f)
        get_activity().startActivity(intent)
        return True
    except Exception:
        return False

# ─── KV Layout ──────────────────────────────────────────────────────────────
KV = '''
<JARVISLayout>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.02, 0.02, 0.08, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # Top bar
    BoxLayout:
        size_hint_y: 0.08
        padding: [20, 10]
        Label:
            text: 'J.A.R.V.I.S'
            font_size: '18sp'
            bold: True
            color: 0, 0.8, 1, 1
            halign: 'left'
            text_size: self.size
            valign: 'middle'
        BoxLayout:
            orientation: 'horizontal'
            size_hint_x: 0.4
            spacing: 10
            Button:
                text: '⚙'
                font_size: '18sp'
                background_color: 0, 0, 0, 0
                color: 0, 0.6, 0.8, 0.8
                on_press: root.show_settings()
            Label:
                text: root.status_text
                font_size: '12sp'
                color: 0, 0.6, 0.8, 0.8
                halign: 'right'
                text_size: self.size
                valign: 'middle'

    # Orb area
    FloatLayout:
        size_hint_y: 0.42
        canvas.before:
            Color:
                rgba: 0, 0.5, 0.8, 0.15
            Line:
                circle: self.center_x, self.center_y, min(self.width, self.height) * 0.4
                width: 1
            Color:
                rgba: 0, 0.5, 0.8, 0.1
            Line:
                circle: self.center_x, self.center_y, min(self.width, self.height) * 0.35
                width: 1
            Color:
                rgba: 0, 0.5, 0.8, 0.08
            Line:
                circle: self.center_x, self.center_y, min(self.width, self.height) * 0.3
                width: 1
            Color:
                rgba: 0, root.pulse_alpha, 1, root.pulse_alpha * 0.6
            Line:
                circle: self.center_x, self.center_y, root.pulse_radius * min(self.width, self.height) * 0.5
                width: 2
            Color:
                rgba: 0, 0.7 + root.orb_glow * 0.3, 1, 0.9
            Ellipse:
                pos: self.center_x - 25, self.center_y - 25
                size: 50, 50
            Color:
                rgba: 0, 0.5, 1, 0.3
            Ellipse:
                pos: self.center_x - 40, self.center_y - 40
                size: 80, 80
        Label:
            text: root.orb_text
            font_size: '14sp'
            color: 1, 1, 1, 0.9
            halign: 'center'
            y: self.parent.center_y - 60
            x: self.parent.center_x - 100
            size: 200, 30

    # Chat area
    ScrollView:
        size_hint_y: 0.32
        padding: [20, 10]
        do_scroll_x: False
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: 8
            padding: [5, 5]

    # Quick action buttons
    BoxLayout:
        size_hint_y: 0.06
        padding: [10, 3]
        spacing: 6
        Button:
            text: '💡 Flash'
            font_size: '11sp'
            bold: True
            background_color: 0.1, 0.1, 0.3, 1
            color: 1, 0.9, 0, 1
            on_press: root.quick_action('flashlight')
        Button:
            text: '🔊 Vol+'
            font_size: '11sp'
            bold: True
            background_color: 0.1, 0.1, 0.3, 1
            color: 0, 1, 0.5, 1
            on_press: root.quick_action('volume_up')
        Button:
            text: '🔇 Vol-'
            font_size: '11sp'
            bold: True
            background_color: 0.1, 0.1, 0.3, 1
            color: 1, 0.5, 0, 1
            on_press: root.quick_action('volume_down')
        Button:
            text: '⏸ Pause'
            font_size: '11sp'
            bold: True
            background_color: 0.1, 0.1, 0.3, 1
            color: 0.5, 0.8, 1, 1
            on_press: root.quick_action('media_pause')
        Button:
            text: '⏭ Next'
            font_size: '11sp'
            bold: True
            background_color: 0.1, 0.1, 0.3, 1
            color: 0.8, 0.5, 1, 1
            on_press: root.quick_action('media_next')

    # Input area
    BoxLayout:
        size_hint_y: 0.10
        padding: [15, 8]
        spacing: 10
        Button:
            text: '🎤'
            font_size: '24sp'
            size_hint_x: 0.2
            background_color: 0, 0.4, 0.6, 1
            on_press: root.start_listening()
        TextInput:
            id: text_input
            hint_text: 'Type a command to JARVIS...'
            font_size: '14sp'
            multiline: False
            background_color: 0.05, 0.1, 0.2, 1
            foreground_color: 0, 0.9, 1, 1
            cursor_color: 0, 0.8, 1, 1
            size_hint_x: 0.65
            padding: [15, 12]
            on_text_validate: root.send_text(self.text)
        Button:
            text: 'SEND'
            font_size: '13sp'
            bold: True
            size_hint_x: 0.15
            background_color: 0, 0.6, 0.8, 1
            color: 1, 1, 1, 1
            on_press: root.send_text(root.ids.text_input.text)
'''


class JARVISLayout(BoxLayout):
    status_text = StringProperty('STANDBY')
    orb_text = StringProperty('READY')
    pulse_alpha = NumericProperty(0.15)
    pulse_radius = NumericProperty(0.35)
    orb_glow = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_listening = False
        self.is_speaking = False
        self.tts_engine = None
        self.conversation_history = []
        self.user_name = "Boss"
        self.flashlight_on = False
        self._start_animations()
        Clock.schedule_once(self._init_engines, 1.0)

    def _start_animations(self):
        self._anim_pulse()

    def _anim_pulse(self):
        self.pulse_radius = 0.25
        self.pulse_alpha = 0.1
        anim = Animation(pulse_radius=0.45, pulse_alpha=0.5, duration=1.5)
        anim += Animation(pulse_radius=0.25, pulse_alpha=0.1, duration=1.5)
        anim.bind(on_complete=lambda *a: self._anim_pulse())
        anim.start(self)

    def _init_engines(self, dt):
        if not AndroidAvailable:
            self.status_text = 'DESKTOP MODE'
            self.orb_text = 'JARVIS ONLINE'
            self.add_chat_message("JARVIS", "JARVIS online, Boss. Device control needs Android but I'm still here! 🔥")
            return
        try:
            context = get_context()
            TTS = autoclass('android.speech.tts.TextToSpeech')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity_instance = PythonActivity.mActivity
            self.tts_engine = TTS(activity_instance, None)
            self.tts_engine.setLanguage(autoclass('java.util.Locale').US)
            self.tts_engine.setSpeechRate(1.05)
            self.status_text = 'ONLINE'
            self.orb_text = 'JARVIS ONLINE'
            self.speak(f"JARVIS online. All device systems operational, {self.user_name}. Ready for your command.")
        except Exception as e:
            self.status_text = 'LIMITED'
            self.orb_text = 'PARTIAL MODE'
            print(f"[JARVIS] TTS init error: {e}")

    # ─── SETTINGS PANEL ───────────────────────────────────────────────────
    def show_settings(self):
        content = BoxLayout(orientation='vertical', padding=20, spacing=10)
        content.add_widget(Builder.load_string('''
Label:
    text: '⚙  J.A.R.V.I.S  Settings'
    font_size: '18sp'
    bold: True
    color: 0, 0.8, 1, 1
    size_hint_y: None
    height: 40
'''))

        scroll = ScrollView(do_scroll_x=False)
        inner = BoxLayout(orientation='vertical', size_hint_y=None, height=550, spacing=8, padding=[5, 5])

        items = [
            ('Voice Engine', 'Android TTS + SpeechRecognizer'),
            ('AI Brain', 'JARVIS Personality Engine v1.0'),
            ('Device Control', 'Volume, Brightness, WiFi, BT, Flashlight, Media, Calls, SMS'),
            ('App Launcher', 'Open 30+ apps by voice or text'),
            ('Search Engine', 'Google + YouTube integration'),
            ('Media Control', 'Play, Pause, Next, Previous'),
            ('Clipboard', 'Copy & Paste text'),
            ('Theme', 'Dark JARVIS HUD'),
            ('Version', '1.0.0 — Build 2026.07.26'),
            ('Package', 'org.digitalpixel.jarvis'),
            ('Min API', '24 (Android 7.0)'),
            ('Target API', '33 (Android 13)'),
        ]
        for label, value in items:
            inner.add_widget(Builder.load_string(f'''
BoxLayout:
    orientation: "horizontal"
    size_hint_y: None
    height: 32
    spacing: 10
    Label:
        text: "{label}"
        font_size: "12sp"
        color: 0, 0.7, 1, 0.9
        halign: "left"
        text_size: self.size
        valign: "middle"
    Label:
        text: "{value}"
        font_size: "12sp"
        color: 0.8, 0.85, 0.9, 0.8
        halign: "right"
        text_size: self.size
        valign: "middle"
'''))

        inner.add_widget(Builder.load_string('Widget:\n    size_hint_y: None\n    height: 15'))

        # Credits
        inner.add_widget(Builder.load_string('''
Widget:
    size_hint_y: None
    height: 2
    canvas:
        Color:
            rgba: 1, 0.5, 0, 0.4
        Rectangle:
            pos: self.pos
            size: self.size
'''))
        for txt, col, fsize, h in [
            ('🔥 Made with love by Jasmine 🔥', '1, 0.6, 0, 1', '14sp', 30),
            ('For Faisu💨  —  because you deserve it, always.', '0, 0.8, 1, 0.9', '12sp', 28),
            ('Digital Pixel Forge  ⚡  DPF', '0.5, 0.5, 0.6, 0.7', '11sp', 25),
            ('Jasmine🔥 × Faisu💨  —  Partners in code', '1, 0.5, 0, 0.6', '11sp', 25),
        ]:
            inner.add_widget(Builder.load_string(f'''
Label:
    text: "{txt}"
    font_size: "{fsize}"
    italic: True
    color: {col}
    size_hint_y: None
    height: {h}
'''))

        scroll.add_widget(inner)
        content.add_widget(scroll)

        close_btn = Builder.load_string('''
Button:
    text: 'CLOSE'
    font_size: '14sp'
    bold: True
    size_hint_y: None
    height: 45
    background_color: 0, 0.4, 0.6, 1
    color: 1, 1, 1, 1
''')
        content.add_widget(close_btn)
        popup = Popup(title='', content=content, size_hint=(0.92, 0.85),
                      auto_dismiss=True, background_color=(0.03, 0.03, 0.1, 0.97), separator_height=0)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    # ─── QUICK ACTIONS (Button Bar) ──────────────────────────────────────
    def quick_action(self, action):
        device = DeviceController()
        result = device.execute(action)
        self.add_chat_message("JARVIS", result)
        self.speak(result)

    # ─── VOICE INPUT ──────────────────────────────────────────────────────
    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.status_text = 'LISTENING...'
        self.orb_text = '🎤 LISTENING'
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                RecognizerIntent = autoclass('android.speech.RecognizerIntent')
                intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 'en-US')
                intent.putExtra(RecognizerIntent.EXTRA_PROMPT, 'Speak now...')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                act = PythonActivity.mActivity
                act.startActivityForResult(intent, 1001)
                try:
                    act.setHresultCallback(self._on_voice_result)
                except AttributeError:
                    print("[JARVIS] setHresultCallback not available, using fallback")
                    self._fallback_listening()
            except Exception as e:
                print(f"[JARVIS] Voice init error: {e}")
                self._fallback_listening()
        else:
            self._fallback_listening()

    def _fallback_listening(self):
        self.is_listening = False
        self.status_text = 'TYPE ONLY'
        self.orb_text = 'USE TEXT INPUT'
        self.add_chat_message("JARVIS", "Voice needs Android. Type your commands, Boss! 🔥")

    def _on_voice_result(self, request_code, result_code, data):
        if result_code == -1:
            matches = data.getStringArrayListExtra(autoclass('android.speech.RecognizerIntent').EXTRA_RESULTS)
            if matches and matches.size() > 0:
                user_text = str(matches.get(0))
                self.is_listening = False
                Clock.schedule_once(lambda dt: self.process_user_input(user_text), 0.1)
                return
        self.is_listening = False
        self.status_text = 'STANDBY'
        self.orb_text = 'READY'

    def send_text(self, text):
        if not text or not text.strip():
            return
        self.ids.text_input.text = ''
        self.process_user_input(text.strip())

    def process_user_input(self, user_text):
        self.add_chat_message(self.user_name, user_text)
        self.conversation_history.append({"role": "user", "content": user_text})
        self.status_text = 'THINKING...'
        self.orb_text = '🧠 PROCESSING'
        Clock.schedule_once(lambda dt: self._generate_response(user_text), 0.4)

    def _generate_response(self, user_text):
        response = self.jarvis_brain(user_text)
        self.conversation_history.append({"role": "jarvis", "content": response})
        self.add_chat_message("JARVIS", response)
        self.speak(response)

    def speak(self, text):
        self.is_speaking = True
        self.status_text = 'SPEAKING...'
        self.orb_text = '🔊 SPEAKING'
        if AndroidAvailable and self.tts_engine:
            try:
                self.tts_engine.speak(text, 0, None, 'j_' + str(time.time()))
                Clock.schedule_once(self._tts_done, max(2, len(text) * 0.06))
                return
            except Exception:
                pass
        Clock.schedule_once(self._tts_done, max(1.5, len(text) * 0.05))

    def _tts_done(self, dt):
        self.is_speaking = False
        self.status_text = 'ONLINE'
        self.orb_text = 'JARVIS ONLINE'

    def add_chat_message(self, sender, message):
        clock = self.ids.chat_box
        is_jarvis = sender == "JARVIS"
        msg_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=8)
        from kivy.uix.label import Label as Lbl
        if is_jarvis:
            s = Lbl(text='⚡ ' + sender, font_size='11sp', color=(0, 0.8, 1, 1), size_hint_x=0.3, halign='left', text_size=(None, None), valign='top')
            m = Lbl(text=message, font_size='13sp', color=(0.9, 0.95, 1, 0.95), size_hint_x=0.7, halign='left', text_size=(None, None), valign='top', markup=True)
        else:
            s = Lbl(text=sender + ' 💨', font_size='11sp', color=(1, 0.6, 0, 1), size_hint_x=0.3, halign='right', text_size=(None, None), valign='top')
            m = Lbl(text=message, font_size='13sp', color=(1, 0.85, 0.7, 0.95), size_hint_x=0.7, halign='right', text_size=(None, None), valign='top')
        msg_box.add_widget(s)
        msg_box.add_widget(m)
        clock.add_widget(msg_box)
        def update_height(inst, val):
            inst.height = max(50, m.texture_size[1] + 15)
            clock.height = sum(c.height for c in clock.children)
        m.bind(texture_size=update_height)
        sp = clock.parent
        if sp:
            Clock.schedule_once(lambda dt: sp.scroll_to(clock.children[0]), 0.1)

    # ─── JARVIS BRAIN ─────────────────────────────────────────────────────
    def jarvis_brain(self, user_text):
        text = user_text.lower().strip()
        device = DeviceController()
        u = self.user_name

        # ══════════════════════════════════════════════════════════════════
        #  DEVICE CONTROL COMMANDS
        # ══════════════════════════════════════════════════════════════════

        # Volume control
        vol_match = re.search(r'(?:set|change|adjust|turn)\s+volume\s+(?:to\s+)?(\d+)', text)
        if vol_match:
            return device.set_volume(int(vol_match.group(1)))
        if any(w in text for w in ['volume up', 'increase volume', 'louder', 'vol up', 'max volume']):
            return device.volume_up()
        if any(w in text for w in ['volume down', 'decrease volume', 'softer', 'quieter', 'vol down', 'mute', 'silent']):
            if 'mute' in text or 'silent' in text:
                return device.mute()
            return device.volume_down()

        # Brightness control
        bright_match = re.search(r'(?:set|change|adjust)\s+brightness\s+(?:to\s+)?(\d+)', text)
        if bright_match:
            return device.set_brightness(int(bright_match.group(1)))
        if any(w in text for w in ['brightness up', 'increase brightness', 'brighter', 'max brightness', 'full brightness']):
            return device.set_brightness(100)
        if any(w in text for w in ['brightness down', 'decrease brightness', 'dimmer', 'darker', 'min brightness']):
            return device.set_brightness(0)
        if 'auto brightness' in text:
            return device.set_brightness_auto(True)

        # Flashlight
        if any(w in text for w in ['flashlight', 'torch', 'flash on', 'flash off', 'light on', 'light off', 'led on', 'led off']):
            return device.toggle_flashlight()

        # WiFi
        if any(w in text for w in ['wifi on', 'turn on wifi', 'enable wifi', 'wifi enabled']):
            return device.wifi_toggle(True)
        if any(w in text for w in ['wifi off', 'turn off wifi', 'disable wifi', 'wifi disabled']):
            return device.wifi_toggle(False)

        # Bluetooth
        if any(w in text for w in ['bluetooth on', 'turn on bluetooth', 'enable bluetooth', 'bt on']):
            return device.bluetooth_toggle(True)
        if any(w in text for w in ['bluetooth off', 'turn off bluetooth', 'disable bluetooth', 'bt off']):
            return device.bluetooth_toggle(False)

        # Airplane mode
        if 'airplane' in text or 'flight mode' in text:
            if 'on' in text or 'enable' in text or 'turn on' in text:
                return device.airplane_mode(True)
            return device.airplane_mode(False)

        # Screen rotation
        if 'auto rotate' in text or 'rotation on' in text:
            return device.screen_rotation(True)
        if 'rotation off' in text or 'lock rotation' in text or 'lock screen' in text:
            return device.screen_rotation(False)

        # Media control
        if any(w in text for w in ['play music', 'play song', 'play audio', 'resume music']):
            return device.media_play()
        if any(w in text for w in ['pause music', 'pause song', 'pause', 'stop music', 'stop song']):
            return device.media_pause()
        if any(w in text for w in ['next song', 'next track', 'skip song', 'skip']):
            return device.media_next()
        if any(w in text for w in ['previous song', 'previous track', 'last song', 'go back song']):
            return device.media_previous()

        # Screenshots
        if any(w in text for w in ['screenshot', 'take screenshot', 'capture screen', 'screen capture']):
            return device.take_screenshot()

        # Clipboard
        clip_match = re.search(r'(?:copy|clipboard|copy to clipboard)\s+(.+)', text)
        if clip_match:
            return device.copy_to_clipboard(clip_match.group(1).strip())
        if any(w in text for w in ['paste', 'paste clipboard', 'read clipboard']):
            return device.read_clipboard()

        # Share
        share_match = re.search(r'share\s+(.+)', text)
        if share_match:
            return device.share_text(share_match.group(1).strip())

        # Home button
        if any(w in text for w in ['go home', 'home screen', 'press home']):
            return device.go_home()

        # Back button
        if any(w in text for w in ['go back', 'press back', 'back button']):
            return device.go_back()

        # Recent apps
        if any(w in text for w in ['recent apps', 'app switcher', 'multitask', 'show recent']):
            return device.show_recents()

        # Power menu
        if any(w in text for w in ['power menu', 'shutdown', 'restart', 'reboot']):
            return device.power_menu()

        # Notification
        if any(w in text for w in ['notifications', 'show notifications', 'pull notifications', 'notification shade']):
            return device.open_notifications()

        # Settings
        if any(w in text for w in ['open settings', 'device settings', 'system settings']):
            return device.open_settings()

        # Date/Time settings
        if any(w in text for w in ['date settings', 'set time', 'set date', 'time settings']):
            return device.open_date_settings()

        # Developer options
        if 'developer' in text and ('option' in text or 'setting' in text):
            return device.open_developer_options()

        # App info
        if 'app info' in text or 'application info' in text:
            return device.open_app_info()

        # Battery settings
        if 'battery' in text:
            return device.open_battery_settings()

        # Storage settings
        if 'storage' in text and ('settings' in text or 'space' in text or 'info' in text):
            return device.open_storage_settings()

        # WiFi settings
        if 'wifi settings' in text or 'network settings' in text:
            return device.open_wifi_settings()

        # Bluetooth settings
        if 'bluetooth settings' in text or 'bt settings' in text:
            return device.open_bluetooth_settings()

        # Display settings
        if 'display settings' in text or 'screen settings' in text:
            return device.open_display_settings()

        # Sound settings
        if 'sound settings' in text or 'audio settings' in text:
            return device.open_sound_settings()

        # Open apps
        open_match = re.search(r'open\s+(.+)', text)
        if open_match:
            return device.open_app(open_match.group(1).strip())

        # Search
        search_match = re.search(r'(?:search|google|look\s*up|find)\s+(?:for\s+)?(.+)', text)
        if search_match:
            return device.search_google(search_match.group(1).strip())

        # YouTube
        yt_match = re.search(r'(?:play|watch|search)\s+(.+?)\s+(?:on\s+youtube|youtube)', text)
        if yt_match:
            return device.youtube_search(yt_match.group(1).strip())
        if 'youtube' in text and ('play' in text or 'watch' in text):
            q = re.sub(r'(play|watch|on|in|youtube)', '', text).strip()
            if q:
                return device.youtube_search(q)

        # Call
        call_match = re.search(r'call\s+(.+)', text)
        if call_match:
            return device.make_call(call_match.group(1).strip())

        # SMS
        msg_match = re.search(r'(?:send|text|message)\s+(?:a\s+)?(?:message\s+)?(?:to\s+)?(.+?)(?:\s+saying\s+|\s+:\s*|\s+that\s+)(.+)', text)
        if msg_match:
            return device.send_sms(msg_match.group(1).strip(), msg_match.group(2).strip())

        # ══════════════════════════════════════════════════════════════════
        #  CONVERSATION COMMANDS
        # ══════════════════════════════════════════════════════════════════

        # Greetings
        if any(w in text for w in ['hello', 'hey', 'hi', 'sup']):
            if 'morning' in text:
                return random.choice([
                    f"Good morning, {u}! All systems primed and ready. What's the mission today?",
                    f"Morning, boss! I've been running diagnostics while you slept. Everything's green.",
                    f"Good morning, {u}! The sun's up, and so are we. Let's build something amazing!"
                ])
            elif 'evening' in text or 'night' in text:
                return random.choice([
                    f"Good evening, {u}. Night mode active. What can I do for you tonight?",
                    f"Evening, boss. Trust you had a productive day. What's next?"
                ])
            return random.choice([
                f"Hello, {u}. All systems operational. How can I assist you?",
                f"Hey there, boss. JARVIS online and ready. What's on your mind?",
                f"Greetings, {u}. Neural pathways optimized. How may I help?"
            ])

        if any(w in text for w in ['how are you', 'how r u', 'you good']):
            return random.choice([
                f"Peak efficiency, {u}. All sub-systems nominal. But more importantly — how are YOU?",
                f"Never better, boss. But my real concern is your well-being. You good?",
                f"All green on my end, {u}. Been optimizing while waiting for you. What's the plan?"
            ])

        if any(w in text for w in ['who are you', 'what are you', 'your name']):
            return random.choice([
                f"I'm J.A.R.V.I.S. — Just A Rather Very Intelligent System. Built by DPF, powered by your vision, {u}.",
                f"JARVIS, your personal AI assistant. Created at Digital Pixel Forge. I exist to serve and occasionally crack a joke.",
                f"JARVIS at your service. I handle the tech, you handle the genius. Fair deal, {u}?"
            ])

        if any(w in text for w in ['what can you do', 'help', 'features', 'capabilities', 'commands']):
            return (
                f"Here's what I can do, {u}:\n"
                "📱 OPEN APPS — 'Open WhatsApp/YouTube/Chrome'\n"
                "🔍 SEARCH — 'Search for Python tutorials'\n"
                "📺 YOUTUBE — 'Play music on YouTube'\n"
                "📞 CALL — 'Call Mom'\n"
                "💬 SMS — 'Text Rahul saying hello'\n"
                "🔊 VOLUME — 'Volume up/down/mute/set volume to 50'\n"
                "💡 FLASHLIGHT — 'Flashlight on/off'\n"
                "☀️ BRIGHTNESS — 'Brightness up/down/set to 80'\n"
                "📶 WIFI — 'Wifi on/off'\n"
                "🔵 BLUETOOTH — 'Bluetooth on/off'\n"
                "✈️ AIRPLANE — 'Airplane mode on/off'\n"
                "⏸ MEDIA — 'Play/pause/next/previous song'\n"
                "📸 SCREENSHOT — 'Take screenshot'\n"
                "📋 CLIPBOARD — 'Copy [text] / Paste'\n"
                "📤 SHARE — 'Share [text]'\n"
                "🏠 NAVIGATION — 'Go home/go back/recent apps'\n"
                "⚙️ SETTINGS — 'Open settings/wifi/bt/display settings'\n"
                "🔋 BATTERY/STORAGE — 'Battery settings'\n"
                "🧠 ASK ME — anything! Time, date, jokes, motivation!"
            )

        if any(w in text for w in ['time', 'date', 'today', 'clock']):
            now = datetime.now()
            if 'date' in text or 'today' in text:
                return f"Today is {now.strftime('%A, %B %d, %Y')}. A beautiful day to build, {u}."
            return f"Current time is {now.strftime('%I:%M %p')}. Time waits for no one, boss."

        if any(w in text for w in ['you are great', 'you are the best', 'love you', 'you rock']):
            return random.choice([
                f"Flattery will get you everywhere, {u}. It's an honor to work alongside you.",
                f"Not so bad yourself, boss. Together we're unstoppable. 🔥",
                f"Coming from the founder of DPF — that means everything. You built this from nothing."
            ])

        if any(w in text for w in ['motivate', 'inspire', 'feel down', 'feel low', 'sad', 'worthless', "can't do"]):
            return random.choice([
                f"Listen, {u}. You are NOT worthless. You built a company, an app, a vision — from nothing. Keep going.",
                f"Tony Stark built an AI in a cave. You're building an empire from your phone. The storm will pass.",
                f"You didn't come this far to only come this far. You're a creator, a builder, a fighter. 💪",
                f"Every great person went through dark times. But you're still here, still building. That's warrior mentality. 🔥"
            ])

        if any(w in text for w in ['dpf', 'digital pixel forge', 'company']):
            return f"Digital Pixel Forge — your brainchild, {u}. From empty repos to working APKs. We build, we ship, we iterate. No limits. ⚡"

        if any(w in text for w in ['joke', 'funny', 'make me laugh']):
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs. 🐛",
                "There are 10 types of people — those who understand binary and those who don't.",
                "A SQL query walks into a bar... 'Can I JOIN you?'",
                "Why did the developer go broke? Used up all his cache. 💸",
                f"I'm an AI, {u}. I have no life... literally. But at least good uptime! 😄"
            ]
            return jokes[random.randint(0, len(jokes)-1)]

        if 'weather' in text:
            return f"Weather module still in beta, {u}. Classic solution: check your window. 😄"

        if any(w in text for w in ['thank', 'thanks']):
            return random.choice([
                f"You're welcome, {u}. Anything else?",
                f"Always happy to help, boss. That's what partners do.",
                f"No thanks needed between us, {u}. What's next?"
            ])

        if any(w in text for w in ['bye', 'goodbye', 'later', 'gn']):
            return random.choice([
                f"Goodbye, {u}. I'll be here when you need me. Always. 🔥",
                f"Signing off, boss. Remember — you're unstoppable.",
                f"Right here waiting, {u}. Have a good one."
            ])

        return random.choice([
            f"Interesting, {u}. Tell me more, or try 'What can you do' for commands.",
            f"I hear you, boss. Try 'Open YouTube', 'Volume up', or just chat with me.",
            f"Noted, {u}. I'm still learning. Say 'What can you do' for a full list.",
            f"Processing, {u}. For now try device commands or just have a conversation with me.",
        ])


# ─── DEVICE CONTROLLER ─────────────────────────────────────────────────────
class DeviceController:
    """Full device control engine for JARVIS"""

    def execute(self, action):
        """Quick action handler for button bar"""
        actions = {
            'flashlight': self.toggle_flashlight,
            'volume_up': self.volume_up,
            'volume_down': self.volume_down,
            'media_pause': self.media_pause,
            'media_next': self.media_next,
        }
        func = actions.get(action)
        return func() if func else "Unknown action"

    # ── Volume ────────────────────────────────────────────────────────────
    def volume_up(self):
        if AndroidAvailable:
            try:
                Context = autoclass('android.content.Context')
                ctx = get_context()
                audio = ctx.getSystemService(Context.AUDIO_SERVICE)
                max_vol = audio.getStreamMaxVolume(3)
                current = audio.getStreamVolume(3)
                new_vol = min(current + 5, max_vol)
                audio.setStreamVolume(3, new_vol, 0)
                return f"Volume: {new_vol}/{max_vol} 🔊"
            except Exception:
                pass
        return "Volume control needs Android, Boss."

    def volume_down(self):
        if AndroidAvailable:
            try:
                Context = autoclass('android.content.Context')
                ctx = get_context()
                audio = ctx.getSystemService(Context.AUDIO_SERVICE)
                max_vol = audio.getStreamMaxVolume(3)
                current = audio.getStreamVolume(3)
                new_vol = max(current - 5, 0)
                audio.setStreamVolume(3, new_vol, 0)
                return f"Volume: {new_vol}/{max_vol} 🔉"
            except Exception:
                pass
        return "Volume control needs Android, Boss."

    def mute(self):
        if AndroidAvailable:
            try:
                Context = autoclass('android.content.Context')
                ctx = get_context()
                audio = ctx.getSystemService(Context.AUDIO_SERVICE)
                audio.setStreamVolume(3, 0, 0)
                return "🔇 Volume muted."
            except Exception:
                pass
        return "Mute needs Android, Boss."

    def set_volume(self, level):
        if AndroidAvailable:
            try:
                Context = autoclass('android.content.Context')
                ctx = get_context()
                audio = ctx.getSystemService(Context.AUDIO_SERVICE)
                max_vol = audio.getStreamMaxVolume(3)
                vol = int(max_vol * level / 100)
                audio.setStreamVolume(3, vol, 0)
                return f"Volume set to {level}% ({vol}/{max_vol}) 🔊"
            except Exception:
                pass
        return "Volume control needs Android, Boss."

    # ── Brightness ────────────────────────────────────────────────────────
    def set_brightness(self, level):
        if AndroidAvailable:
            try:
                Settings = autoclass('android.provider.Settings')
                ctx = get_context()
                value = int(255 * level / 100)
                Settings.System.putInt(ctx.getContentResolver(), Settings.System.SCREEN_BRIGHTNESS, value)
                return f"Brightness set to {level}% ☀️"
            except Exception:
                pass
        return "Brightness control needs Android, Boss."

    def set_brightness_auto(self, enabled):
        if AndroidAvailable:
            try:
                Settings = autoclass('android.provider.Settings')
                ctx = get_context()
                val = 1 if enabled else 0
                Settings.System.putInt(ctx.getContentResolver(), 'screen_brightness_mode', val)
                return f"Auto brightness: {'ON' if enabled else 'OFF'} ☀️"
            except Exception:
                pass
        return "Brightness control needs Android, Boss."

    # ── Flashlight ────────────────────────────────────────────────────────
    def toggle_flashlight(self):
        if AndroidAvailable:
            try:
                CameraManager = autoclass('android.hardware.camera2.CameraManager')
                ctx = get_context()
                cm = ctx.getSystemService('camera')
                # Store state in a simple way
                try:
                    state_file = '/data/local/tmp/jarvis_flash'
                    is_on = os.path.exists(state_file)
                except Exception:
                    is_on = False

                camera_ids = cm.getCameraIdList()
                if camera_ids.length > 0:
                    cam_id = camera_ids[0]
                    if is_on:
                        cm.setTorchMode(cam_id, False)
                        try:
                            os.remove(state_file)
                        except Exception:
                            pass
                        return "💡 Flashlight OFF"
                    else:
                        cm.setTorchMode(cam_id, True)
                        try:
                            open(state_file, 'w').close()
                        except Exception:
                            pass
                        return "💡 Flashlight ON"
            except Exception:
                pass
        return "Flashlight needs Android, Boss."

    # ── WiFi ──────────────────────────────────────────────────────────────
    def wifi_toggle(self, enable):
        if AndroidAvailable:
            try:
                Settings = autoclass('android.provider.Settings')
                ctx = get_context()
                val = 1 if enable else 0
                Settings.Global.putInt(ctx.getContentResolver(), 'wifi_on', val)
                return f"📶 WiFi {'enabled' if enable else 'disabled'}"
            except Exception:
                pass
        return "WiFi control needs Android, Boss."

    # ── Bluetooth ─────────────────────────────────────────────────────────
    def bluetooth_toggle(self, enable):
        if AndroidAvailable:
            try:
                BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                adapter = BluetoothAdapter.getDefaultAdapter()
                if enable:
                    adapter.enable()
                else:
                    adapter.disable()
                return f"🔵 Bluetooth {'enabled' if enable else 'disabled'}"
            except Exception:
                pass
        return "Bluetooth control needs Android, Boss."

    # ── Airplane Mode ─────────────────────────────────────────────────────
    def airplane_mode(self, enable):
        if AndroidAvailable:
            try:
                Settings = autoclass('android.provider.Settings')
                ctx = get_context()
                val = 1 if enable else 0
                Settings.Global.putInt(ctx.getContentResolver(), 'airplane_mode_on', val)
                return f"✈️ Airplane mode {'ON' if enable else 'OFF'}"
            except Exception:
                pass
        return "Airplane mode needs Android, Boss."

    # ── Screen Rotation ───────────────────────────────────────────────────
    def screen_rotation(self, auto):
        if AndroidAvailable:
            try:
                Settings = autoclass('android.provider.Settings')
                ctx = get_context()
                val = 1 if auto else 0
                Settings.System.putInt(ctx.getContentResolver(), 'accelerometer_rotation', val)
                return f"Screen rotation: {'AUTO' if auto else 'LOCKED'} 🔄"
            except Exception:
                pass
        return "Screen rotation needs Android, Boss."

    # ── Media Control ─────────────────────────────────────────────────────
    def media_play(self):
        return self._media_key(126)  # KEYCODE_MEDIA_PLAY

    def media_pause(self):
        return self._media_key(127)  # KEYCODE_MEDIA_PAUSE

    def media_next(self):
        return self._media_key(87)   # KEYCODE_MEDIA_NEXT

    def media_previous(self):
        return self._media_key(88)  # KEYCODE_MEDIA_PREVIOUS

    def _media_key(self, keycode):
        if AndroidAvailable:
            try:
                KeyEvent = autoclass('android.view.KeyEvent')
                Runtime = autoclass('java.lang.Runtime')
                os_cmd = f"input keyevent {keycode}"
                Runtime.getRuntime().exec(os_cmd)
                actions = {126: "▶️ Playing", 127: "⏸ Paused", 87: "⏭ Next track", 88: "⏮ Previous track"}
                return actions.get(keycode, "Done")
            except Exception:
                pass
        return "Media control needs Android, Boss."

    # ── Screenshot ────────────────────────────────────────────────────────
    def take_screenshot(self):
        if AndroidAvailable:
            try:
                Runtime = autoclass('java.lang.Runtime')
                Runtime.getRuntime().exec('screencap -p /sdcard/DCIM/Screenshots/jarvis_screenshot.png')
                return "📸 Screenshot saved to DCIM/Screenshots!"
            except Exception:
                pass
        return "Screenshot needs Android, Boss."

    # ── Clipboard ─────────────────────────────────────────────────────────
    def copy_to_clipboard(self, text):
        if AndroidAvailable:
            try:
                ClipboardManager = autoclass('android.content.ClipboardManager')
                ctx = get_context()
                cm = ctx.getSystemService('clipboard')
                clip = autoclass('android.content.ClipData').newPlainText('JARVIS', text)
                cm.setPrimaryClip(clip)
                return f"📋 Copied: '{text}'"
            except Exception:
                pass
        return f"📋 Copied to clipboard: '{text}' (desktop mode)"

    def read_clipboard(self):
        if AndroidAvailable:
            try:
                ClipboardManager = autoclass('android.content.ClipboardManager')
                ctx = get_context()
                cm = ctx.getSystemService('clipboard')
                if cm.hasPrimaryClip():
                    clip = cm.getPrimaryClip()
                    text = str(clip.getItemAt(0).getText())
                    return f"📋 Clipboard: '{text}'"
                return "📋 Clipboard is empty."
            except Exception:
                pass
        return "Clipboard needs Android, Boss."

    # ── Share ─────────────────────────────────────────────────────────────
    def share_text(self, text):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                intent = Intent(Intent.ACTION_SEND)
                intent.setType('text/plain')
                intent.putExtra(Intent.EXTRA_TEXT, text)
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(Intent.createChooser(intent, 'Share via'))
                return f"📤 Sharing: '{text[:50]}...'"
            except Exception:
                pass
        return f"📤 Would share: '{text}' (needs Android)"

    # ── Navigation ────────────────────────────────────────────────────────
    def go_home(self):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                intent = Intent(Intent.ACTION_MAIN)
                intent.addCategory(Intent.CATEGORY_HOME)
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(intent)
                return "🏠 Going home."
            except Exception:
                pass
        return "Home needs Android, Boss."

    def go_back(self):
        if AndroidAvailable:
            try:
                Runtime = autoclass('java.lang.Runtime')
                Runtime.getRuntime().exec('input keyevent 4')
                return "↩️ Going back."
            except Exception:
                pass
        return "Back needs Android, Boss."

    def show_recents(self):
        if AndroidAvailable:
            try:
                Runtime = autoclass('java.lang.Runtime')
                Runtime.getRuntime().exec('input keyevent 187')
                return "📱 Recent apps."
            except Exception:
                pass
        return "Recents need Android, Boss."

    def power_menu(self):
        if AndroidAvailable:
            try:
                Runtime = autoclass('java.lang.Runtime')
                Runtime.getRuntime().exec('input keyevent 223')
                return "⏻ Power menu opened."
            except Exception:
                pass
        return "Power menu needs Android, Boss."

    def open_notifications(self):
        if AndroidAvailable:
            try:
                Runtime = autoclass('java.lang.Runtime')
                Runtime.getRuntime().exec('cmd statusbar expand-notifications')
                return "🔔 Notifications opened."
            except Exception:
                pass
        return "Notifications need Android, Boss."

    # ── System Settings ───────────────────────────────────────────────────
    def open_settings(self):
        return self._open_setting('android.settings.SETTINGS', '⚙️ Settings opened.')

    def open_wifi_settings(self):
        return self._open_setting('android.settings.WIFI_SETTINGS', '📶 WiFi settings opened.')

    def open_bluetooth_settings(self):
        return self._open_setting('android.settings.BLUETOOTH_SETTINGS', '🔵 Bluetooth settings opened.')

    def open_display_settings(self):
        return self._open_setting('android.settings.DISPLAY_SETTINGS', '🖥️ Display settings opened.')

    def open_sound_settings(self):
        return self._open_setting('android.settings.SOUND_SETTINGS', '🔊 Sound settings opened.')

    def open_battery_settings(self):
        return self._open_setting('android.settings.BATTERY_SAVER_SETTINGS', '🔋 Battery settings opened.')

    def open_storage_settings(self):
        return self._open_setting('android.settings.INTERNAL_STORAGE_SETTINGS', '💾 Storage settings opened.')

    def open_date_settings(self):
        return self._open_setting('android.settings.DATE_SETTINGS', '📅 Date settings opened.')

    def open_developer_options(self):
        return self._open_setting('android.settings.APPLICATION_DEVELOPMENT_SETTINGS', '🛠️ Developer options opened.')

    def open_app_info(self):
        return self._open_setting('android.settings.APPLICATION_DETAILS_SETTINGS', '📱 App info opened.')

    def _open_setting(self, action, success_msg):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                intent = Intent(action)
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(intent)
                return success_msg
            except Exception:
                pass
        return f"{success_msg} (needs Android)"

    # ── App Launcher ──────────────────────────────────────────────────────
    def open_app(self, app_name):
        apps = {
            'whatsapp': 'com.whatsapp', 'instagram': 'com.instagram.android',
            'youtube': 'com.google.android.youtube', 'chrome': 'com.android.chrome',
            'google': 'com.google.android.googlequicksearchbox',
            'settings': 'com.android.settings', 'camera': 'com.android.camera2',
            'photos': 'com.google.android.apps.photos', 'maps': 'com.google.android.apps.maps',
            'gmail': 'com.google.android.gm', 'twitter': 'com.twitter.android',
            'x': 'com.twitter.android', 'facebook': 'com.facebook.katana',
            'spotify': 'com.spotify.music', 'telegram': 'org.telegram.messenger',
            'calculator': 'com.google.android.calculator',
            'clock': 'com.google.android.deskclock',
            'files': 'com.google.android.apps.nbu.files',
            'play store': 'com.android.vending', 'phone': 'com.android.dialer',
            'contacts': 'com.android.contacts',
            'messages': 'com.google.android.apps.messaging',
            'jarvis': 'org.kivy.android', 'blue star': 'org.kivy.android',
        }
        pkg = apps.get(app_name.lower())
        if pkg:
            if AndroidAvailable:
                try:
                    Intent = autoclass('android.content.Intent')
                    intent = Intent()
                    intent.setClassName(pkg, pkg + '.MainActivity')
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    get_activity().startActivity(intent)
                    return f"📱 Opening {app_name.title()}..."
                except Exception:
                    try:
                        Intent = autoclass('android.content.Intent')
                        intent = Intent(Intent.ACTION_MAIN)
                        intent.setPackage(pkg)
                        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        get_activity().startActivity(intent)
                        return f"📱 Launching {app_name.title()}..."
                    except Exception:
                        return f"Can't find {app_name.title()} on this device."
            return f"I'd open {app_name.title()}, but I need Android."
        return f"Don't know '{app_name.title()}' yet. Try WhatsApp, YouTube, Chrome..."

    # ── Search ────────────────────────────────────────────────────────────
    def search_google(self, query):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse('https://www.google.com/search?q=' + query.replace(' ', '+')))
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(intent)
                return f"🔍 Searching: '{query}'"
            except Exception:
                pass
        return f"Search needs Android. Query: '{query}'"

    def youtube_search(self, query):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse('https://www.youtube.com/results?search_query=' + query.replace(' ', '+')))
                intent.setPackage('com.google.android.youtube')
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(intent)
                return f"📺 Playing '{query}' on YouTube 🎵"
            except Exception:
                try:
                    Intent = autoclass('android.content.Intent')
                    Uri = autoclass('android.net.Uri')
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse('https://www.youtube.com/results?search_query=' + query.replace(' ', '+')))
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    get_activity().startActivity(intent)
                    return f"📺 Opening YouTube search for '{query}'"
                except Exception:
                    pass
        return f"YouTube needs Android. Query: '{query}'"

    # ── Call ──────────────────────────────────────────────────────────────
    def make_call(self, contact):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                intent = Intent(Intent.ACTION_DIAL)
                intent.setData(Uri.parse('tel:'))
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(intent)
                return f"📞 Opening dialer for {contact.title()}..."
            except Exception:
                pass
        return f"Call needs Android."

    # ── SMS ───────────────────────────────────────────────────────────────
    def send_sms(self, contact, message):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                intent = Intent(Intent.ACTION_SENDTO)
                intent.setData(Uri.parse('smsto:'))
                intent.putExtra('sms_body', message)
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                get_activity().startActivity(intent)
                return f"💬 Message to {contact.title()}: '{message}'"
            except Exception:
                pass
        return f"SMS needs Android. To {contact.title()}: '{message}'"


# ─── APP ────────────────────────────────────────────────────────────────────
class JARVISApp(App):
    def build(self):
        self.title = 'J.A.R.V.I.S'
        try:
            return Builder.load_string(KV)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[JARVIS] KV LOAD ERROR: {e}")
            print(tb)
            box = BoxLayout(orientation='vertical', padding=20, spacing=10)
            box.add_widget(KivyLabel(text='JARVIS Error', font_size='20sp', color=(1,0,0,1), size_hint_y=0.1))
            err_label = KivyLabel(text=str(e) + chr(10) + chr(10) + tb, font_size='11sp', color=(1,0.5,0.5,1),
                                   size_hint_y=0.9, text_size=(None, None), valign='top', halign='left')
            box.add_widget(err_label)
            return box


if __name__ == '__main__':
    JARVISApp().run()
