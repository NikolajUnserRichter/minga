"""Abo-Positionen (B6, Gernot 08.10.2026): Bestandsabos nachtragen.

Bis B6 trug ein Abo genau ein Produkt in seinen Kopffeldern (product_id,
product_variant_id, seed_id, menge, einheit). Seit B6 liest der Abo-Lauf nur
noch subscription_items. tenancy._auto_migrate ruft positionen_nachtragen bei
jedem Start und nach jedem Demo-Reset.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Subscription, SubscriptionItem


def positionen_nachtragen(db: Session) -> int:
    """Jedes Abo ohne Position bekommt seinen Kopf als Position 1.

    Idempotent: Abos mit mindestens einer Position bleiben unberührt. Auch
    inaktive Abos und Abos ohne Produkt und Sorte werden übernommen, so wie
    sie sind: verlustfrei, der Abo-Lauf überspringt Letztere wie bisher mit
    Meldung. Committet nicht.
    """
    ohne_position = db.execute(
        select(Subscription).where(~Subscription.positionen.any())
    ).scalars().all()
    for sub in ohne_position:
        sub.positionen.append(SubscriptionItem(
            position=1,
            product_id=sub.product_id,
            product_variant_id=sub.product_variant_id,
            seed_id=sub.seed_id,
            menge=sub.menge,
            einheit=sub.einheit,
        ))
    db.flush()
    return len(ohne_position)
