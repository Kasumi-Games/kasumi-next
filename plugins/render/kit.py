from abc import ABC
from abc import abstractmethod
from typing import Literal
from typing import Sequence
from dataclasses import dataclass

from .core import Component
from .core import Background
from .color import ColorLike
from .types import ImageFit
from .types import Overflow
from .types import TextAlign
from .types import ImageSource
from .sizing import SizeValue
from .spacing import InsetsLike


@dataclass(frozen=True)
class PlayerIdentity:
    """Who a rendered surface belongs to.

    Assembled in the message handler (``utils.identity.identity_for``) and
    passed into renderers, so the render layer never touches a database.

    Attributes:
        nickname: Display name; never empty.
        level: Permanent level, or ``None`` to omit.
        avatar: Optional avatar image. When ``None`` the surface draws a
            fallback (typically an initial-letter badge) instead of leaving a
            hole; avatar fetching currently costs one HTTP call per lookup, so
            most surfaces pass ``None`` until a cache exists.
        avatar_frame: Optional equipped avatar-frame art. Keeping it beside the
            avatar makes every identity surface (games, profile, rankings) use
            the same cosmetic instead of querying inventory at render sites.
    """

    nickname: str
    level: int | None = None
    avatar: ImageSource | None = None
    avatar_frame: ImageSource | None = None


@dataclass(frozen=True)
class PullRevealItem:
    """One result inside a gacha reveal.

    Attributes:
        name: Item display name.
        rarity: Star rarity (1-6).
        is_new: Whether the player did not own this item before the pull.
        featured: Whether this is a featured banner item.
        image: Optional art thumbnail.
        note: Short annotation, e.g. a duplicate-compensation grant.
    """

    name: str
    rarity: int
    is_new: bool = False
    featured: bool = False
    image: ImageSource | None = None
    note: str = ""


class BaseKit(ABC):
    """Abstract contract for neutral render-kit atoms.

    Concrete kits may expose richer theme-specific helpers, but shared callers
    should only depend on these general factories.

    Alongside the atom factories, a kit publishes a small palette so callers can
    tint content they draw themselves without assuming a light theme. The
    defaults below describe a light kit; dark kits override them. Callers that
    need a themed surface should omit ``fill`` and let the kit decide rather
    than hard-coding a color.

    Attributes:
        text_color: Default body text color.
        muted_text_color: De-emphasized text color for secondary content.
        panel_fill: Default panel surface color.
        theme_signature_enabled: Whether standard cards append the small theme
            credit line. Character themes may disable it when their visual
            identity is already unmistakable and the line only adds clutter.

    **Tier A surfaces.** ``game_identity``, ``player_card`` and ``pull_reveal``
    are the three high-visibility surfaces that get a bespoke, hand-authored
    treatment per kit rather than a shared composition. Their base
    implementations raise; callers never invoke them directly and instead go
    through the dispatchers in ``utils.cards`` (``game_identity(kit, ...)``
    etc.), which fall back to a generic atom composition when a kit has not
    authored its own. A kit that overrides one of these owns the full visual:
    the dispatcher passes data through untouched.
    """

    text_color: ColorLike = (80, 80, 80, 255)
    muted_text_color: ColorLike = (130, 130, 145, 255)
    panel_fill: ColorLike = (255, 255, 255, 208)
    theme_signature_enabled: bool = True

    @abstractmethod
    def background(self, *, fill: ColorLike | None = None) -> Background:
        """Create a neutral page background.

        Args:
            fill: Optional background fill color override.

        Returns:
            Background renderer.
        """

        ...

    @abstractmethod
    def text(
        self,
        text: str,
        *,
        font_size: int = 40,
        color: ColorLike | None = None,
        align: TextAlign = "left",
        wrap: bool = True,
        max_lines: int | None = None,
        overflow: Overflow = "ellipsis",
        line_height: int | None = None,
    ) -> Component:
        """Create text.

        Args:
            text: Text content.
            font_size: Requested font size in pixels.
            color: Optional text color override.
            align: Horizontal text alignment.
            wrap: Whether text may wrap inside a bounded width.
            max_lines: Optional maximum number of rendered lines.
            overflow: Behavior when text exceeds its bounds.
            line_height: Optional line height override.

        Returns:
            Text component.
        """

        ...

    @abstractmethod
    def image(
        self,
        image: ImageSource,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        fit: ImageFit = "contain",
        opacity: float = 1.0,
        radius: int = 0,
    ) -> Component:
        """Create an image wrapper.

        Args:
            image: Image path or in-memory PIL image.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            fit: Resize behavior inside the assigned rectangle.
            opacity: Alpha multiplier from 0.0 to 1.0.
            radius: Optional corner radius in pixels.

        Returns:
            Image component.
        """

        ...

    @abstractmethod
    def panel(
        self,
        child: Component | None = None,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        padding: InsetsLike = 0,
        fill: ColorLike | None = None,
        radius: int | None = None,
    ) -> Component:
        """Create a container surface.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.

        Returns:
            Panel component.
        """

        ...

    @abstractmethod
    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a divider.

        Args:
            orientation: Divider direction.
            length: Optional length sizing token or pixel value.
            thickness: Divider thickness in pixels.
            color: Optional divider color override.

        Returns:
            Separator component.
        """

        ...

    def game_identity(
        self,
        identity: PlayerIdentity,
        *,
        width: SizeValue | int,
        detail: str | None = None,
    ) -> Component:
        """Create the identity strip placed on a game board.

        This is the highest-exposure Tier A surface: a game posts one board
        image per move into the channel, and this strip is what ties the visual
        to a player. Keep it compact (target height 64-88 logical px) — it sits
        above the board, not instead of it. No theme signature here; mid-game
        boards deliberately carry none.

        Args:
            identity: Player identity data.
            width: Strip width; games pass their board width.
            detail: Optional game-specific right-hand text, e.g. ``押注 120 Pt``.

        Returns:
            Strip component.
        """

        raise NotImplementedError("game_identity must be implemented by the kit")

    def player_card(
        self,
        *,
        avatar_image: ImageSource | None,
        frame_image: ImageSource | None,
        title1_image: ImageSource | None,
        title2_image: ImageSource | None,
        nickname: str,
        level: int,
        current_pt: int,
        description: str,
        width: SizeValue | int,
        height: SizeValue | int,
    ) -> Component:
        """Create a kit-specific player identity card.

        Tier A: concrete kits override this with their own composition instead
        of sharing a generic render-module implementation. ``avatar_image`` may
        be ``None`` (draw an initial-letter fallback); frame and title images
        are ``None`` until those cosmetic assets exist.
        """

        raise NotImplementedError("player_card must be implemented by the kit")

    def pull_reveal(
        self,
        pulls: Sequence[PullRevealItem],
        *,
        width: SizeValue | int,
    ) -> Component:
        """Create the gacha reveal grid for one to ten pulls.

        The reveal is the emotional peak of the gacha loop, which is what makes
        it Tier A. Rarity must be encoded by shape and weight, never hue alone
        (the manga kit is monochrome): a ``★6`` chip, a heavier border, a
        filled marker. The banner header and pity footer are page concerns
        assembled by the caller — this component is only the grid of results.

        Args:
            pulls: Pull results in draw order (1-10 items).
            width: Grid width.

        Returns:
            Reveal component.
        """

        raise NotImplementedError("pull_reveal must be implemented by the kit")
