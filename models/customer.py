from dataclasses import dataclass


@dataclass
class Customer:
    customer_id: int
    name: str
    email: str
    age: int | None
    gender: str | None
