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

    current = SatoriMessageBuilder.file
    if getattr(current, "__kasumi_src_guard__", False):
        guarded_file = current
    else:
        original = current

        @build("file")
        def guarded_file(self, segment):
            if not segment.data.get("src"):
                return None
            return original(self, segment)

        guarded_file.__name__ = "file"
        guarded_file.__kasumi_src_guard__ = True
        SatoriMessageBuilder.file = guarded_file

    # Alconna caches builder instances when its uniseg adapter registry is
    # imported.  Updating only the class leaves those existing instances bound
    # to the old method, which is exactly what happens during normal bot startup.
    from nonebot_plugin_alconna.uniseg.adapters import BUILDER_MAPPING

    for builder in BUILDER_MAPPING.values():
        if isinstance(builder, SatoriMessageBuilder):
            builder._mapping["file"] = guarded_file.__get__(
                builder, SatoriMessageBuilder
            )
