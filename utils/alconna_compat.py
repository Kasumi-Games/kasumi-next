"""Narrow compatibility guards for upstream Alconna message conversion."""


def install_satori_file_segment_guard() -> None:
    """Ignore Satori ``file`` segments that do not contain a source.

    QQ can emit metadata-only file segments such as ``{"size": "39219"}``.
    Alconna's Satori builder currently indexes ``data["src"]`` unconditionally,
    which makes every Alconna rule check fail for that message.
    """

    from nonebot_plugin_alconna.uniseg.builder import build
    from nonebot_plugin_alconna.uniseg.adapters.satori.builder import (
        SatoriMessageBuilder,
    )

    original = SatoriMessageBuilder.file
    if getattr(original, "__kasumi_src_guard__", False):
        return

    @build("file")
    def guarded_file(self, segment):
        if not segment.data.get("src"):
            return None
        return original(self, segment)

    guarded_file.__name__ = "file"
    guarded_file.__kasumi_src_guard__ = True
    SatoriMessageBuilder.file = guarded_file
