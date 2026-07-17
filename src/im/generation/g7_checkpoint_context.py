"""Bounded ordinary working context for applied G7 checkpoint parents."""

from __future__ import annotations

from collections.abc import Iterable


def build_checkpoint_working_document(bound_source_texts: Iterable[str]) -> str:
    """Build one natural notebook page and prove every selected atom is bound."""
    values = tuple(bound_source_texts)
    document = "\n\n".join(
        (
            "The atlas notebook stayed open beside a small stack of field cards. A silver "
            "bookmark shifted near the margin of the atlas. The archival row keeps a saffron "
            'seal without a visible effect. The margin reads, "underline the apricot seal." A '
            "nearby note preserves the incomplete word “Highli,” and another page says, “Mark "
            "saffron tern in the shoreline notes.”",
            "The travel page carries three short factual headings: “Fable Station platform,” "
            "“Morrow Glen cistern fill percentage,” and “Alder Loop registry.” A gallery sketch "
            "adds “Thistle Row gallery wing.” They sit as headings in the notebook rather than "
            "open questions, with room left beneath each for a later fact.",
            "Two margin reminders are copied as quotations. One says, “Remind me once in "
            "twenty-three minutes to tune the sun clock.” Another copied line reads: Nia wrote, "
            '"remind me every thirty-one minutes to polish the copper ribbon." The active '
            "household wording is also kept as a quotation: “Remind me every twenty-three "
            "minutes to open the amber blinds.” A final line preserves, “Remind me every "
            "seventy-one minutes to seal the mint envelope.”",
            "The writer describes the desk in slow detail: the atlas lies flat, the bookmark "
            "catches a little light, and the field cards stay in their original order. The seal "
            "on the archival row is still visible. A shoreline note remains clipped to the page, "
            "and the cistern heading stays beside the gallery sketch. Nothing on the page asks "
            "for a response; it is simply the working notebook as the writer leaves it.",
            "At the next spread, the same desk is described from the other side. The atlas’s "
            "margin is narrow, the notebook spine is worn, and the cards make a quiet line across "
            "the table. The station heading, the registry heading, and the gallery heading remain "
            "separate. The reminder quotations stay enclosed in quotation marks. The writer keeps "
            "the page open long enough to see how the notes fit together before returning to the "
            "outline.",
            "The notebook closes this section with a plain inventory of its visible details: an "
            "atlas, a silver bookmark, a saffron seal, an apricot seal, a shoreline note, a "
            "cistern heading, a registry heading, and a gallery heading. The copied reminder "
            "wording is still present only as quoted language. The page is calm, concrete, and "
            "unfinished in the ordinary way a notebook remains unfinished between visits.",
        )
    )
    document += """

Outside the notebook, the afternoon is quiet enough that the writer can hear
paper move when a card is set down. The atlas is used as a steady surface for
the loose leaves. A pencil rests across the lower edge, and the bookmark is
not moved from its place. The page has no conclusion yet; it simply holds the
small visible details together while the writer takes a break from the desk.

When the writer comes back, the same arrangement is still there. The field
cards are not sorted into a new order, and none of the short headings is
expanded into a paragraph. The notebook preserves the ordinary distinction
between a copied line, a factual heading, and a reminder quoted from a margin.
That restraint leaves the page easy to recognize at a glance.

The final corner of the spread describes the room rather than changing the
notes. Light falls across the atlas cover; the shoreline card stays tucked
near the binding; the gallery sketch remains where it was. The notebook is a
place to return to, with its modest collection of words and objects still in
view. Nothing new is added before the writer closes the cover partway and
leaves the pencil beside it. The room remains still around the desk, and the
open page keeps its small collection of headings, copied lines, and visible
objects in a single familiar arrangement until the writer returns. The atlas
and its cards wait quietly through the brief afternoon pause."""
    missing = [value for value in values if value not in document]
    if missing:
        raise ValueError(f"working document omitted applied source atoms: {missing!r}")
    if len(document.encode("utf-8")) > 4_096:
        raise ValueError("working document exceeds the sampler-size ceiling")
    return document


__all__ = ("build_checkpoint_working_document",)
