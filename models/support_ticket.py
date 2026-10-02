from dataclasses import dataclass


@dataclass
class SupportTicket:
    ticket_id: int
    customer_id: int
    product_name: str | None
    date_of_purchase: str | None
    ticket_type: str | None
    subject: str | None
    description: str | None
    status: str | None
    resolution: str | None
    priority: str | None
    channel: str | None
    first_response_time: str | None
    time_to_resolution: str | None
    satisfaction_rating: float | None
