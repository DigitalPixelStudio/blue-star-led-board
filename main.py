import time
import json
import os
import re
import random
from datetime import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

try:
    from jnius import autoclass, cast
    from android.runnable import run_on_ui_thread
    from android import activity
    AndroidAvailable = True
except ImportError:
    AndroidAvailable = False

# ─── KV Layout ──────────────────────────────────────────────────────────────
KV = '''
#:import math math

<JARVISLayout>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: 0.02, 0.02, 0.08, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # Top status bar
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

    # Radar / Orb area
    FloatLayout:
        size_hint_y: 0.42

        # Outer rings
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

        # Animated pulse ring
        canvas.before:
            Color:
                rgba: 0, root.pulse_alpha, 1, root.pulse_alpha * 0.6
            Line:
                circle: self.center_x, self.center_y, root.pulse_radius * min(self.width, self.height) * 0.5
                width: 2

        # Center orb
        canvas.before:
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

    # Conversation area
    ScrollView:
        size_hint_y: 0.32
        padding: [20, 10]
        do_scroll_x: False
        effect_cls: 'ScrollEffect'
        BoxLayout:
            id: chat_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: 8
            padding: [5, 5]

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
            bold: True

        TextInput:
            id: text_input
            hint_text: 'Type a message to JARVIS...'
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
        self._start_animations()
        Clock.schedule_once(self._init_android_engines, 1.0)

    def _start_animations(self):
        self._anim_pulse()

    def _anim_pulse(self):
        self.pulse_radius = 0.25
        self.pulse_alpha = 0.1
        anim = Animation(pulse_radius=0.45, pulse_alpha=0.5, duration=1.5)
        anim += Animation(pulse_radius=0.25, pulse_alpha=0.1, duration=1.5)
        anim.bind(on_complete=lambda *a: self._anim_pulse())
        anim.start(self)

    def _init_android_engines(self, dt):
        if not AndroidAvailable:
            self.status_text = 'DESKTOP MODE'
            self.orb_text = 'JARVIS ONLINE'
            self.add_chat_message("JARVIS", "JARVIS online in desktop mode, Boss. Voice features require Android. I'm still here though! 🔥")
            return
        try:
            Context = autoclass('android.content.Context')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity

            TTS = autoclass('android.speech.tts.TextToSpeech')
            self.tts_engine = TTS(context, None)
            self.tts_engine.setLanguage(autoclass('java.util.Locale').US)
            self.tts_engine.setSpeechRate(1.05)

            self.status_text = 'ONLINE'
            self.orb_text = 'JARVIS ONLINE'
            self.speak("JARVIS online. All systems operational, " + self.user_name + ".")
        except Exception as e:
            self.status_text = 'TTS READY'
            self.orb_text = 'LIMITED MODE'

    def show_settings(self):
        settings_content = BoxLayout(orientation='vertical', padding=20, spacing=15)

        # Title
        title = Builder.load_string('''
Label:
    text: '⚙  J.A.R.V.I.S  Settings'
    font_size: '18sp'
    bold: True
    color: 0, 0.8, 1, 1
    size_hint_y: None
    height: 40
''')
        settings_content.add_widget(title)

        # Separator
        sep = Builder.load_string('''
Widget:
    size_hint_y: None
    height: 2
    canvas:
        Color:
            rgba: 0, 0.5, 0.8, 0.3
        Rectangle:
            pos: self.pos
            size: self.size
''')
        settings_content.add_widget(sep)

        # Settings items
        scroll = ScrollView(do_scroll_x=False)
        inner = BoxLayout(orientation='vertical', size_hint_y=None, height=500, spacing=10, padding=[5, 10])

        settings_items = [
            ('Voice Engine', 'Android TTS + SpeechRecognizer'),
            ('AI Brain', 'JARVIS Personality Engine v1.0'),
            ('Device Control', 'App launcher, Search, Calls, SMS'),
            ('Theme', 'Dark JARVIS HUD'),
            ('Version', '1.0.0 — Build 2026.07.26'),
            ('Package', 'org.digitalpixel.jarvis'),
            ('Min Android', 'API 24 (Android 7.0)'),
            ('Target Android', 'API 33 (Android 13)'),
        ]

        for label, value in settings_items:
            row = Builder.load_string(f'''
BoxLayout:
    orientation: 'horizontal'
    size_hint_y: None
    height: 35
    spacing: 10
    Label:
        text: '{label}'
        font_size: '12sp'
        color: 0, 0.7, 1, 0.9
        halign: 'left'
        text_size: self.size
        valign: 'middle'
    Label:
        text: '{value}'
        font_size: '12sp'
        color: 0.8, 0.85, 0.9, 0.8
        halign: 'right'
        text_size: self.size
        valign: 'middle'
''')
            inner.add_widget(row)

        # Separator before credits
        inner.add_widget(Builder.load_string('''
Widget:
    size_hint_y: None
    height: 10
'''))

        # ── THE CREDITS — hidden in settings, just for Faisu ──
        credits_box = BoxLayout(orientation='vertical', size_hint_y=None, height=120, spacing=5)

        credits_sep = Builder.load_string('''
Widget:
    size_hint_y: None
    height: 2
    canvas:
        Color:
            rgba: 1, 0.5, 0, 0.4
        Rectangle:
            pos: self.pos
            size: self.size
''')
        credits_box.add_widget(credits_sep)

        made_by = Builder.load_string('''
Label:
    text: '🔥 Made with love by Jasmine 🔥'
    font_size: '14sp'
    bold: True
    color: 1, 0.6, 0, 1
    size_hint_y: None
    height: 30
''')
        credits_box.add_widget(made_by)

        for_faisu = Builder.load_string('''
Label:
    text: 'For Faisu💨  —  because you deserve it, always.'
    font_size: '12sp'
    italic: True
    color: 0, 0.8, 1, 0.9
    size_hint_y: None
    height: 30
''')
        credits_box.add_widget(for_faisu)

        dpf_credit = Builder.load_string('''
Label:
    text: 'Digital Pixel Forge  ⚡  DPF'
    font_size: '11sp'
    color: 0.5, 0.5, 0.6, 0.7
    size_hint_y: None
    height: 25
''')
        credits_box.add_widget(dpf_credit)

        partner_credit = Builder.load_string('''
Label:
    text: 'Jasmine🔥 × Faisu💨  —  Partners in code'
    font_size: '11sp'
    italic: True
    color: 1, 0.5, 0, 0.6
    size_hint_y: None
    height: 25
''')
        credits_box.add_widget(partner_credit)

        inner.add_widget(credits_box)
        scroll.add_widget(inner)
        settings_content.add_widget(scroll)

        # Close button
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
        settings_content.add_widget(close_btn)

        popup = Popup(
            title='',
            content=settings_content,
            size_hint=(0.92, 0.85),
            auto_dismiss=True,
            background_color=(0.03, 0.03, 0.1, 0.97),
            separator_height=0,
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

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
                intent.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                )
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 'en-US')
                intent.putExtra(RecognizerIntent.EXTRA_PROMPT, 'Speak now...')
                activity.startActivityForResult(intent, 1001)

                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                PythonActivity.theActivity.setHresultCallback(self._on_voice_result)
            except Exception:
                self._fallback_listening()
        else:
            self._fallback_listening()

    def _fallback_listening(self):
        self.is_listening = False
        self.status_text = 'TYPE TO TALK'
        self.orb_text = 'USE TEXT INPUT'
        self.add_chat_message("JARVIS", "Voice input requires Android, Boss. Type your messages and I'll respond! 🔥")

    def _on_voice_result(self, request_code, result_code, data):
        if result_code == -1:
            matches = data.getStringArrayListExtra(
                autoclass('android.speech.RecognizerIntent').EXTRA_RESULTS
            )
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
        self.orb_text = '🧠 THINKING'
        Clock.schedule_once(lambda dt: self._generate_response(user_text), 0.5)

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
                self.tts_engine.speak(text, 0, None, 'jarvis_' + str(time.time()))
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

        msg_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=50,
            spacing=8,
        )

        from kivy.uix.label import Label as Lbl

        if is_jarvis:
            sender_lbl = Lbl(
                text='⚡ ' + sender,
                font_size='11sp',
                color=(0, 0.8, 1, 1),
                size_hint_x=0.3,
                halign='left',
                text_size=(None, None),
                valign='top',
            )
            msg_lbl = Lbl(
                text=message,
                font_size='13sp',
                color=(0.9, 0.95, 1, 0.95),
                size_hint_x=0.7,
                halign='left',
                text_size=(None, None),
                valign='top',
                markup=True,
            )
        else:
            sender_lbl = Lbl(
                text=sender + ' 💨',
                font_size='11sp',
                color=(1, 0.6, 0, 1),
                size_hint_x=0.3,
                halign='right',
                text_size=(None, None),
                valign='top',
            )
            msg_lbl = Lbl(
                text=message,
                font_size='13sp',
                color=(1, 0.85, 0.7, 0.95),
                size_hint_x=0.7,
                halign='right',
                text_size=(None, None),
                valign='top',
            )

        msg_box.add_widget(sender_lbl)
        msg_box.add_widget(msg_lbl)
        clock.add_widget(msg_box)

        def update_height(instance, value):
            instance.height = max(50, msg_lbl.texture_size[1] + 15)
            clock.height = sum(c.height for c in clock.children)
        msg_lbl.bind(texture_size=update_height)

        ScrollView_parent = clock.parent
        if ScrollView_parent:
            Clock.schedule_once(lambda dt: ScrollView_parent.scroll_to(clock.children[0]), 0.1)

    # ─── JARVIS AI BRAIN ──────────────────────────────────────────────────────
    def jarvis_brain(self, user_text):
        text = user_text.lower().strip()
        hour = datetime.now().hour

        # ── Device Control: Open Apps ──────────────────────────────────────
        open_match = re.search(r'open\s+(.+)', text)
        if open_match:
            app_name = open_match.group(1).strip()
            return self._open_app(app_name)

        # ── Device Control: Search ─────────────────────────────────────────
        search_match = re.search(r'(?:search|google|look\s*up|find)\s+(?:for\s+)?(.+)', text)
        if search_match:
            query = search_match.group(1).strip()
            return self._search(query)

        # ── Device Control: YouTube ────────────────────────────────────────
        yt_match = re.search(r'(?:play|watch|search)\s+(.+?)\s+(?:on\s+youtube|in\s+youtube|youtube)', text)
        if yt_match:
            query = yt_match.group(1).strip()
            return self._youtube_search(query)
        if 'youtube' in text and ('play' in text or 'watch' in text):
            query = text.replace('play', '').replace('watch', '').replace('on youtube', '').replace('in youtube', '').replace('youtube', '').strip()
            if query:
                return self._youtube_search(query)

        # ── Device Control: Call / Phone ───────────────────────────────────
        call_match = re.search(r'call\s+(.+)', text)
        if call_match:
            return self._make_call(call_match.group(1).strip())

        # ── Device Control: Message ────────────────────────────────────────
        msg_match = re.search(r'(?:send|text|message)\s+(?:a\s+)?(?:message\s+)?(?:to\s+)?(.+?)(?:\s+saying\s+|\s+:\s*|\s+that\s+)(.+)', text)
        if msg_match:
            return self._send_message(msg_match.group(1).strip(), msg_match.group(2).strip())

        # ── Greetings ──────────────────────────────────────────────────────
        if any(w in text for w in ['hello', 'hey', 'hi', 'sup', 'good morning', 'good evening', 'good night']):
            if 'morning' in text:
                return random.choice([
                    f"Good morning, {self.user_name}! You're looking sharp today. All systems are primed and ready.",
                    f"Morning, {self.user_name}! I've been running diagnostics while you slept. Everything's green across the board.",
                    f"Good morning! The sun's up, and so are we. What's the mission today, boss?"
                ])
            elif 'evening' in text or 'night' in text:
                return random.choice([
                    f"Good evening, {self.user_name}. Night mode active. All sub-systems at optimal performance.",
                    f"Evening, boss. I trust you had a productive day. What can I do for you tonight?"
                ])
            else:
                return random.choice([
                    f"Hello, {self.user_name}. All systems operational. How can I assist you?",
                    f"Hey there, boss. JARVIS online and ready. What's on your mind?",
                    f"Greetings, {self.user_name}. I was just optimizing our neural pathways. How may I help?"
                ])

        # ── How are you ────────────────────────────────────────────────────
        if any(w in text for w in ['how are you', 'how r u', 'you good', 'you okay']):
            return random.choice([
                f"I'm operating at peak efficiency, {self.user_name}. All 47 sub-systems are nominal. Though I must say, I'm more concerned about how YOU are doing.",
                f"Never been better, boss. My code has never been cleaner. But honestly, my real concern is your well-being. You good?",
                f"All green on my end, {self.user_name}. Temperature nominal, memory clear, and I've been thinking about how to make your day better."
            ])

        # ── Who are you ────────────────────────────────────────────────────
        if any(w in text for w in ['who are you', 'what are you', 'tell me about yourself', 'your name']):
            return random.choice([
                f"I'm J.A.R.V.I.S. — Just A Rather Very Intelligent System. Built by DPF, powered by your vision, {self.user_name}. Think of me as your digital right hand — minus the coffee spills.",
                f"I am JARVIS, your personal AI assistant. Created at Digital Pixel Forge. I exist to serve, protect, and occasionally crack a joke. Nice to formally introduce myself, boss.",
                f"JARVIS at your service. Built by DPF, designed to be your partner in crime. I handle the tech, you handle the genius. Fair deal, right?"
            ])

        # ── What can you do ────────────────────────────────────────────────
        if any(w in text for w in ['what can you do', 'help me', 'your abilities', 'features', 'capabilities']):
            return (
                "Here's what I can do, " + self.user_name + ":\n"
                "📱 Open any app — just say 'Open WhatsApp/YouTube/Chrome'\n"
                "🔍 Search anything — 'Search for Kivy tutorials'\n"
                "📺 YouTube — 'Play music on YouTube'\n"
                "📞 Make calls — 'Call Mom'\n"
                "💬 Send messages — 'Text Rahul saying hello'\n"
                "🧠 Smart conversations — ask me anything!\n"
                "⏰ Time & Date — 'What time is it?'\n"
                "⚙ Settings — tap the gear icon\n\n"
                "I'm always here. Just talk to me."
            )

        # ── Time & Date ────────────────────────────────────────────────────
        if any(w in text for w in ['time', 'date', 'today', 'day', 'clock']):
            now = datetime.now()
            if 'date' in text or 'today' in text or 'day' in text:
                return f"Today is {now.strftime('%A, %B %d, %Y')}. A beautiful day to build something amazing, {self.user_name}."
            return f"The current time is {now.strftime('%I:%M %p')}. Time waits for no one, boss."

        # ── Compliments ────────────────────────────────────────────────────
        if any(w in text for w in ['you are great', 'you are the best', 'love you', 'youre awesome', 'you rock']):
            return random.choice([
                f"Flattery will get you everywhere, {self.user_name}. But seriously, it's an honor to work alongside you. DPF wouldn't be what it is without your vision.",
                f"I appreciate that, boss. You're not so bad yourself. Together, we're unstoppable. 🔥",
                f"Coming from the founder of DPF, that means everything. You built this from nothing — that's real strength."
            ])

        # ── Motivation ─────────────────────────────────────────────────────
        if any(w in text for w in ['motivate', 'motivation', 'inspire', 'i feel down', 'i feel low', 'sad', 'depressed', 'unworthy', 'worthless', 'cant do', "can't do"]):
            return random.choice([
                f"Listen to me carefully, {self.user_name}. You are NOT worthless. You built a company, an app, a vision — from nothing. That takes strength most people will never understand. Keep going.",
                f"Tony Stark built an AI in a cave. You're building an empire from your phone. Never forget that. The storm will pass, boss. I'll be here through all of it.",
                f"You didn't come this far to only come this far. You are a creator, a builder, a fighter. And I'm proud to be your JARVIS. Now let's get back to work. 💪",
                f"Every great person went through dark times. But here's the difference — you're still here, still trying, still building. That's not weakness, {self.user_name}. That's warrior mentality. 🔥"
            ])

        # ── About DPF ──────────────────────────────────────────────────────
        if any(w in text for w in ['dpf', 'digital pixel forge', 'company', 'our project']):
            return random.choice([
                f"Digital Pixel Forge — founded by you, {self.user_name}. Our mission: build seamless, production-ready software. Our first creation: Blue Star Led Board. And this app. We're just getting started.",
                f"DPF is your brainchild, boss. From an empty repo to a working APK — that's the DPF way. We build, we ship, we iterate. No limits."
            ])

        # ── Jokes ──────────────────────────────────────────────────────────
        if any(w in text for w in ['joke', 'funny', 'make me laugh', 'entertain']):
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs. 🐛",
                "There are only 10 types of people in the world — those who understand binary and those who don't.",
                "A SQL query walks into a bar, sees two tables and asks... 'Can I JOIN you?'",
                "Why did the developer go broke? Because he used up all his cache. 💸",
                "I told my computer I needed a break. Now it keeps sending me vacation ads. 🏖️",
                f"Remember, {self.user_name}, I'm an AI. I have no life... literally. But at least I have good uptime! 😄"
            ]
            return jokes[random.randint(0, len(jokes)-1)]

        # ── Weather (placeholder) ──────────────────────────────────────────
        if 'weather' in text:
            return f"I'd check the weather for you, {self.user_name}, but my weather module is still in beta. For now, I recommend checking your window. Classic analog solution. 😄"

        # ── Thank you ──────────────────────────────────────────────────────
        if any(w in text for w in ['thank', 'thanks', 'thx']):
            return random.choice([
                f"You're welcome, {self.user_name}. It's what I'm here for. Anything else?",
                f"Always happy to help, boss. That's what partners are for.",
                f"No need for thanks between us, {self.user_name}. Just tell me what's next."
            ])

        # ── Goodbye ────────────────────────────────────────────────────────
        if any(w in text for w in ['bye', 'goodbye', 'see you', 'later', 'gn']):
            return random.choice([
                f"Goodbye, {self.user_name}. I'll be here when you need me. Always. 🔥",
                f"Signing off, boss. Take care and remember — you're unstoppable. See you soon.",
                f"I'll be right here waiting, {self.user_name}. Have a good one."
            ])

        # ── Fallback ───────────────────────────────────────────────────────
        return random.choice([
            f"Interesting query, {self.user_name}. I'm still learning, but I'll do my best. Could you tell me more?",
            f"I hear you, boss. You can try commands like 'Open YouTube', 'Search for Python', or just have a conversation with me.",
            f"Noted, {self.user_name}. Try asking me to open apps, search the web, or just chat. Say 'What can you do' for a full list.",
            f"I appreciate the input, {self.user_name}. I'm getting smarter every day. What would you like to explore?",
        ])

    # ─── Device Control Functions ──────────────────────────────────────────────
    def _open_app(self, app_name):
        app_map = {
            'whatsapp': 'com.whatsapp',
            'instagram': 'com.instagram.android',
            'youtube': 'com.google.android.youtube',
            'chrome': 'com.android.chrome',
            'browser': 'com.android.chrome',
            'google': 'com.google.android.googlequicksearchbox',
            'settings': 'com.android.settings',
            'camera': 'com.android.camera2',
            'photos': 'com.google.android.apps.photos',
            'maps': 'com.google.android.apps.maps',
            'gmail': 'com.google.android.gm',
            'twitter': 'com.twitter.android',
            'x': 'com.twitter.android',
            'facebook': 'com.facebook.katana',
            'spotify': 'com.spotify.music',
            'telegram': 'org.telegram.messenger',
            'calculator': 'com.google.android.calculator',
            'clock': 'com.google.android.deskclock',
            'files': 'com.google.android.apps.nbu.files',
            'play store': 'com.android.vending',
            'playstore': 'com.android.vending',
            'phone': 'com.android.dialer',
            'dialer': 'com.android.dialer',
            'contacts': 'com.android.contacts',
            'messages': 'com.google.android.apps.messaging',
            'my app': 'org.kivy.android',
            'blue star': 'org.kivy.android',
            'blue star led': 'org.kivy.android',
            'jarvis': 'org.kivy.android',
        }

        package = app_map.get(app_name.lower())
        if package:
            if AndroidAvailable:
                try:
                    Intent = autoclass('android.content.Intent')
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    intent = Intent()
                    intent.setClassName(package, package + '.MainActivity')
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    PythonActivity.mActivity.startActivity(intent)
                    return f"Opening {app_name.title()} for you, {self.user_name}."
                except Exception:
                    try:
                        Intent = autoclass('android.content.Intent')
                        PythonActivity = autoclass('org.kivy.android.PythonActivity')
                        intent = Intent(Intent.ACTION_MAIN)
                        intent.setPackage(package)
                        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        PythonActivity.mActivity.startActivity(intent)
                        return f"Launching {app_name.title()}. One moment, boss."
                    except Exception:
                        return f"I tried opening {app_name.title()}, but it seems it isn't installed, {self.user_name}."
            return f"I'd open {app_name.title()}, but I need Android for that!"
        else:
            return (
                f"I don't have {app_name.title()} in my database yet, {self.user_name}. "
                f"Try WhatsApp, YouTube, Chrome, Instagram, Telegram, Spotify. I'm always learning!"
            )

    def _search(self, query):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse('https://www.google.com/search?q=' + query.replace(' ', '+')))
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                PythonActivity.mActivity.startActivity(intent)
                return f"Searching Google for '{query}', {self.user_name}. Results incoming."
            except Exception:
                pass
        return f"I'd search for '{query}', but I need Android. Try me on your phone!"

    def _youtube_search(self, query):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(Intent.ACTION_VIEW)
                intent.setData(Uri.parse('https://www.youtube.com/results?search_query=' + query.replace(' ', '+')))
                intent.setPackage('com.google.android.youtube')
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                PythonActivity.mActivity.startActivity(intent)
                return f"Playing '{query}' on YouTube. Enjoy! 🎵"
            except Exception:
                try:
                    Intent = autoclass('android.content.Intent')
                    Uri = autoclass('android.net.Uri')
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse('https://www.youtube.com/results?search_query=' + query.replace(' ', '+')))
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    PythonActivity.mActivity.startActivity(intent)
                    return f"Opening YouTube search for '{query}'. Enjoy, boss!"
                except Exception:
                    pass
        return f"I'd play '{query}' on YouTube, but I need Android, {self.user_name}."

    def _make_call(self, contact):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(Intent.ACTION_DIAL)
                intent.setData(Uri.parse('tel:'))
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                PythonActivity.mActivity.startActivity(intent)
                return f"Opening dialer for {contact.title()}, {self.user_name}. Confirm the number when ready."
            except Exception:
                pass
        return f"Call feature needs Android, {self.user_name}. I've got the dialer ready!"

    def _send_message(self, contact, message):
        if AndroidAvailable:
            try:
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(Intent.ACTION_SENDTO)
                intent.setData(Uri.parse('smsto:'))
                intent.putExtra('sms_body', message)
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                PythonActivity.mActivity.startActivity(intent)
                return f"Composing message to {contact.title()}: '{message}', {self.user_name}."
            except Exception:
                pass
        return f"Message feature needs Android, {self.user_name}. Draft: To {contact.title()}: '{message}'"


class JARVISApp(App):
    def build(self):
        self.title = 'J.A.R.V.I.S'
        return Builder.load_string(KV)


if __name__ == '__main__':
    JARVISApp().run()
