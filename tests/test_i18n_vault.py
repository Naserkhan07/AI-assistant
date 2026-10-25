from nixi.i18n.catalog import I18N
from nixi.security.vault import Vault
from nixi.automation.recorder import MacroRecorder
from nixi.ui.themes import palette, css_vars
from nixi.ui.markdown_view import render_markdown, citations_block
from nixi.ui.notifications import NotificationCenter
import tempfile
def test_i18n():
    i=I18N("en"); assert i.t("status.idle")=="Idle"
    i.set_locale("hi"); assert "तैयार" in i.t("status.idle")
    i.set_locale("hinglish"); assert "Ready" in i.t("status.idle")
    assert i.t("unknown.key") == "unknown.key"
def test_vault(tmp_path=None):
    import tempfile; td=tempfile.mkdtemp()
    from nixi.config import NixiConfig
    cfg=NixiConfig.from_env({"NIXI_DATA_DIR": td})
    v=Vault(cfg); v.put("my_key","s3cret"); assert v.get("my_key")=="s3cret"
    assert len(v.list_keys())==1; assert v.delete("my_key"); assert v.get("my_key") is None
def test_recorder():
    import tempfile; from nixi.config import NixiConfig
    cfg=NixiConfig.from_env({"NIXI_DATA_DIR": tempfile.mkdtemp()})
    r=MacroRecorder(cfg); r.start("t"); r.record_action({"type":"click","x":10,"y":20}); msg=r.stop("t")
    assert "Saved" in msg; assert r.list_macros(); assert "dry-run" in r.replay(r.list_macros()[0], dry_run=True)
def test_themes_md():
    assert palette("dark")["bg"] == "#1a1a2e"; assert "--scale" in css_vars("light", 1.2)
    html=render_markdown("**bold** and [link](https://example.com) `code`")
    assert "<b>bold</b>" in html and "<a href" in html
    assert "citations" in citations_block(["https://a.com"])
def test_notifications():
    import tempfile; from nixi.config import NixiConfig
    cfg=NixiConfig.from_env({"NIXI_DATA_DIR": tempfile.mkdtemp()})
    nc=NotificationCenter(cfg); nc.push("Hello","world"); assert nc.unread_count()==1; nc.mark_all_read(); assert nc.unread_count()==0
