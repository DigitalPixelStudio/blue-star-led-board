from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button


class DigitalPixelForgeLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 40
        self.spacing = 20

        title = Label(
            text='Digital Pixel Forge',
            font_size='28sp',
            size_hint_y=None,
            height=80,
            bold=True,
        )
        subtitle = Label(
            text='Welcome to DPF Universe 🔥',
            font_size='16sp',
            size_hint_y=None,
            height=40,
        )
        btn = Button(
            text='Tap Me',
            size_hint_y=None,
            height=60,
            font_size='18sp',
        )
        btn.bind(on_press=self.on_button_press)

        self.add_widget(title)
        self.add_widget(subtitle)
        self.add_widget(btn)

    def on_button_press(self, instance):
        instance.text = 'You are part of DPF! 🚀'


class DigitalPixelForgeApp(App):
    def build(self):
        return DigitalPixelForgeLayout()


if __name__ == '__main__':
    DigitalPixelForgeApp().run()
