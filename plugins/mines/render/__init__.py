from .field import render

__all__ = ["render"]


if __name__ == "__main__":
    import sys
    import os
    import types
    import random

    # Add the project root to sys.path to allow absolute imports
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    sys.path.append(project_root)

    # Mock plugins.mines to prevent loading its __init__.py (which requires nonebot)
    # This is necessary because we are running this script standalone for testing
    if "plugins.mines" not in sys.modules:
        mines_fake = types.ModuleType("plugins.mines")
        mines_fake.__path__ = [os.path.join(project_root, "plugins", "mines")]
        sys.modules["plugins.mines"] = mines_fake
        # Also ensure plugins is in modules if needed (namespace pkg usually handles itself)

    from plugins.mines.models import Field, BlockType
    from plugins.mines.render import render

    # Patch BlockType into field module because it's missing the import at runtime
    import sys

    if "plugins.mines.render.field" in sys.modules:
        sys.modules["plugins.mines.render.field"].BlockType = BlockType

    field = Field()
    for i in range(6):
        field.reveal_block(random.randint(0, field.width * field.height - 1))

    render(field).show()
