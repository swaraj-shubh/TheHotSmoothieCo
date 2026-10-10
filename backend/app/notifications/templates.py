"""Built-in message templates. `$name` placeholders (string.Template): templates can be edited by
staff, and Template only substitutes plain names, unlike str.format which can reach object attributes."""

from dataclasses import dataclass
from string import Template


@dataclass(frozen=True)
class MessageTemplate:
    subject: str
    body: str
    sensitive: bool = False  # context holds secrets (tokens): scrubbed once sent
    marketing: bool = False  # respects the user's marketing opt-out

    def render(self, context: dict) -> tuple[str, str]:
        ctx = {k: str(v) for k, v in context.items()}
        return Template(self.subject).safe_substitute(ctx), Template(self.body).safe_substitute(ctx)


SIGNOFF = "\n\n— The Hot Smoothie Co.\n"

TEMPLATES: dict[str, MessageTemplate] = {
    "verify_email": MessageTemplate(
        "Verify your email",
        "Hi $name,\n\nPlease confirm your email address:\n$link\n\nThis link expires in 24 hours." + SIGNOFF,
        sensitive=True,
    ),
    "password_reset": MessageTemplate(
        "Reset your password",
        "Hi $name,\n\nSomeone (hopefully you) asked to reset your password:\n$link\n\n"
        "This link expires in 1 hour. If it wasn't you, you can ignore this email." + SIGNOFF,
        sensitive=True,
    ),
    "order_confirmed": MessageTemplate(
        "Order $order_number confirmed",
        "Hi $name,\n\nThanks for your order! We've received your payment of $total and will start "
        "printing soon.\n\nOrder details: $order_url" + SIGNOFF,
    ),
    "order_shipped": MessageTemplate(
        "Order $order_number is on its way",
        "Hi $name,\n\nYour art has left the studio. Track it here: $order_url" + SIGNOFF,
    ),
    "order_delivered": MessageTemplate(
        "Order $order_number delivered",
        "Hi $name,\n\nYour order has been delivered. We'd love to see it on your wall — "
        "leave a review: $order_url" + SIGNOFF,
    ),
    "order_cancelled": MessageTemplate(
        "Order $order_number cancelled",
        "Hi $name,\n\nYour order $order_number has been cancelled. Any payment will be refunded to "
        "the original payment method within 5–7 working days.\n\n$order_url" + SIGNOFF,
    ),
    "refund_processed": MessageTemplate(
        "Refund of $amount processed",
        "Hi $name,\n\nWe've refunded $amount for order $order_number. Depending on your bank it may "
        "take 5–7 working days to show up.\n\n$order_url" + SIGNOFF,
    ),
    "abandoned_cart": MessageTemplate(
        "Still thinking it over?",
        "Hi $name,\n\nYou left $item_count item(s) in your cart. They're waiting for you:\n$cart_url"
        + SIGNOFF,
        marketing=True,
    ),
}


def rupees(paise: int) -> str:
    """Indian digit grouping: 123456789 paise -> ₹12,34,567.89"""
    whole, frac = divmod(abs(paise), 100)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(i - 2, 0) : i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return f"{'-' if paise < 0 else ''}₹{s}.{frac:02d}"
