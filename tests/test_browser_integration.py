from nixi.automation.browser import BrowserController
from nixi.core.browser_agent import BrowserExecutionAgent


class FakeLocator:
    def __init__(self):
        self.value = ""
        self.first = self

    def count(self):
        return 1

    def is_visible(self):
        return True

    def fill(self, value, timeout=None):
        self.value = value

    def input_value(self, timeout=None):
        return self.value


class FakeKeyboard:
    def __init__(self):
        self.key = None

    def press(self, key):
        self.key = key


class FakePage:
    def __init__(self):
        self.url = "https://example.test"
        self.keyboard = FakeKeyboard()
        self.field = FakeLocator()

    def get_by_label(self, *args, **kwargs):
        return self.field

    def get_by_placeholder(self, *args, **kwargs):
        return self.field

    def get_by_role(self, *args, **kwargs):
        return self.field

    def get_by_text(self, *args, **kwargs):
        return self.field

    def title(self):
        return "Example"


def test_no_controlled_browser_does_not_claim_action_succeeded():
    browser = BrowserController()
    result = browser.act("click the Save button")
    assert "no browser action was performed" in result.lower()


def test_dom_fill_is_performed_and_field_value_verified():
    browser = BrowserController()
    browser._page = FakePage()
    result = browser.act('type "hello" into the search field')
    assert "verified" in result.lower()
    assert browser._page.field.value == "hello"


def test_unsupported_browser_instruction_performs_no_action():
    browser = BrowserController()
    browser._page = FakePage()
    result = browser.act("delete all my emails")
    assert "no action was performed" in result.lower()


def test_vision_fallback_never_fills_guessed_data():
    agent = BrowserExecutionAgent(llm_client=None)
    assert "no screen clicks or typing" in agent._fallback_fill("fill a form").lower()
