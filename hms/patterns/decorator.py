"""
Decorator Pattern - Billing System
====================================
Dynamically composes a patient bill by wrapping a BaseBill with charge
decorators. Each decorator adds its own charge on top of what the wrapped
component already computed.

Class hierarchy::

    BillComponent          (abstract interface)
     |- BaseBill            (concrete: base consultation charge)
     +- BillDecorator       (abstract decorator base)
          |- LabTestDecorator
          |- RoomChargeDecorator
          |- ICUFeeDecorator
          +- EmergencyServiceDecorator

Usage::

    from hms.patterns.decorator import BillingDecoratorBuilder

    builder = (
        BillingDecoratorBuilder("Consultation Fee", base_amount=500.0)
        .add_lab_test(amount=200.0, test_name="Blood Panel")
        .add_room_charge(amount=1500.0, room_type="General Ward", days=3)
        .add_icu_fee(amount=5000.0, days=2)
        .add_emergency_service(amount=800.0)
    )
    total = builder.get_total()
    items = builder.get_bill_items()  # list[dict] ready for db_operations
"""

from __future__ import annotations
from abc import ABC, abstractmethod


# ======================================================================== #
#  Abstract Component                                                        #
# ======================================================================== #

class BillComponent(ABC):
    """Abstract interface shared by the concrete bill and all decorators."""

    @abstractmethod
    def get_total(self) -> float:
        """Return cumulative charge amount."""

    @abstractmethod
    def get_description(self) -> str:
        """Return human-readable description of all charges."""

    @abstractmethod
    def get_bill_items(self) -> list:
        """
        Return list of line-item dicts with keys:
          description, quantity, unit_price
        ready for db_operations.add_bill_item().
        """


# ======================================================================== #
#  Concrete Component - Base Bill                                            #
# ======================================================================== #

class BaseBill(BillComponent):
    """
    Root of every decorator chain - represents the basic consultation
    or admission charge before any extras are applied.
    """

    def __init__(self, description: str, amount: float):
        self._description = description
        self._amount = float(amount)

    def get_total(self) -> float:
        return self._amount

    def get_description(self) -> str:
        return f"{self._description}: PKR {self._amount:,.2f}"

    def get_bill_items(self) -> list:
        return [
            {
                "description": self._description,
                "quantity": 1,
                "unit_price": self._amount,
            }
        ]


# ======================================================================== #
#  Abstract Decorator                                                        #
# ======================================================================== #

class BillDecorator(BillComponent, ABC):
    """
    Abstract base for all bill decorators. Holds a reference to the
    wrapped BillComponent and delegates down the chain before adding
    its own contribution.
    """

    def __init__(self, component: BillComponent):
        if not isinstance(component, BillComponent):
            raise TypeError(
                f"BillDecorator expects a BillComponent, got {type(component)}"
            )
        self._component = component

    def get_total(self) -> float:
        return self._component.get_total() + self._own_charge()

    def get_description(self) -> str:
        return (
            self._component.get_description()
            + f"\n  + {self._own_label()}: PKR {self._own_charge():,.2f}"
        )

    def get_bill_items(self) -> list:
        return self._component.get_bill_items() + self._own_items()

    @abstractmethod
    def _own_charge(self) -> float:
        """Amount this decorator adds."""

    @abstractmethod
    def _own_label(self) -> str:
        """Short label for get_description()."""

    @abstractmethod
    def _own_items(self) -> list:
        """Line-item dicts this decorator contributes."""


# ======================================================================== #
#  Concrete Decorators                                                       #
# ======================================================================== #

class LabTestDecorator(BillDecorator):
    """Adds lab-test charges to the wrapped bill."""

    def __init__(self, component: BillComponent, amount: float,
                 test_name: str = "Lab Tests"):
        super().__init__(component)
        self._amount = float(amount)
        self._test_name = test_name

    def _own_charge(self) -> float:
        return self._amount

    def _own_label(self) -> str:
        return f"Lab Test - {self._test_name}"

    def _own_items(self) -> list:
        return [
            {
                "description": f"Lab Test - {self._test_name}",
                "quantity": 1,
                "unit_price": self._amount,
            }
        ]


class RoomChargeDecorator(BillDecorator):
    """Adds room/ward charges to the wrapped bill."""

    def __init__(self, component: BillComponent, amount: float,
                 room_type: str = "General Ward", days: int = 1):
        super().__init__(component)
        self._rate = float(amount)
        self._room_type = room_type
        self._days = max(1, int(days))

    def _own_charge(self) -> float:
        return self._rate * self._days

    def _own_label(self) -> str:
        return f"Room Charges - {self._room_type} x {self._days} day(s)"

    def _own_items(self) -> list:
        return [
            {
                "description": f"Room Charges - {self._room_type}",
                "quantity": self._days,
                "unit_price": self._rate,
            }
        ]


class ICUFeeDecorator(BillDecorator):
    """Adds ICU fees to the wrapped bill."""

    def __init__(self, component: BillComponent, amount: float, days: int = 1):
        super().__init__(component)
        self._rate = float(amount)
        self._days = max(1, int(days))

    def _own_charge(self) -> float:
        return self._rate * self._days

    def _own_label(self) -> str:
        return f"ICU Charges x {self._days} day(s)"

    def _own_items(self) -> list:
        return [
            {
                "description": "ICU Charges",
                "quantity": self._days,
                "unit_price": self._rate,
            }
        ]


class EmergencyServiceDecorator(BillDecorator):
    """Adds an emergency-service surcharge to the wrapped bill."""

    def __init__(self, component: BillComponent, amount: float):
        super().__init__(component)
        self._amount = float(amount)

    def _own_charge(self) -> float:
        return self._amount

    def _own_label(self) -> str:
        return "Emergency Services"

    def _own_items(self) -> list:
        return [
            {
                "description": "Emergency Services",
                "quantity": 1,
                "unit_price": self._amount,
            }
        ]


# ======================================================================== #
#  Fluent Builder Helper                                                     #
# ======================================================================== #

class BillingDecoratorBuilder:
    """
    Fluent builder that assembles a decorator chain and exposes the final
    get_total() / get_bill_items() results for persistence.

    Example::

        builder = (
            BillingDecoratorBuilder("Consultation Fee", base_amount=500.0)
            .add_lab_test(200.0, "CBC")
            .add_room_charge(1500.0, room_type="Private Room", days=3)
            .add_icu_fee(5000.0, days=1)
            .add_emergency_service(800.0)
        )
        total = builder.get_total()
        items = builder.get_bill_items()
    """

    def __init__(self, description: str, base_amount: float):
        self._bill: BillComponent = BaseBill(description, base_amount)

    # ------------------------------------------------------------------ #
    #  Fluent decorator adders                                             #
    # ------------------------------------------------------------------ #

    def add_lab_test(self, amount: float,
                     test_name: str = "Lab Tests") -> "BillingDecoratorBuilder":
        """Wrap the current bill with a LabTestDecorator."""
        self._bill = LabTestDecorator(self._bill, amount, test_name)
        return self

    def add_room_charge(self, amount: float, room_type: str = "General Ward",
                        days: int = 1) -> "BillingDecoratorBuilder":
        """Wrap the current bill with a RoomChargeDecorator."""
        self._bill = RoomChargeDecorator(self._bill, amount, room_type, days)
        return self

    def add_icu_fee(self, amount: float,
                    days: int = 1) -> "BillingDecoratorBuilder":
        """Wrap the current bill with an ICUFeeDecorator."""
        self._bill = ICUFeeDecorator(self._bill, amount, days)
        return self

    def add_emergency_service(self, amount: float) -> "BillingDecoratorBuilder":
        """Wrap the current bill with an EmergencyServiceDecorator."""
        self._bill = EmergencyServiceDecorator(self._bill, amount)
        return self

    # ------------------------------------------------------------------ #
    #  Result accessors                                                    #
    # ------------------------------------------------------------------ #

    def get_total(self) -> float:
        """Return the grand total of all charges."""
        return self._bill.get_total()

    def get_description(self) -> str:
        """Return the full human-readable charge chain description."""
        return self._bill.get_description()

    def get_bill_items(self) -> list:
        """
        Return list of line-item dicts ready for db_operations.add_bill_item().
        Each dict has keys: description, quantity, unit_price.
        """
        return self._bill.get_bill_items()

    def build(self) -> BillComponent:
        """Return the fully decorated BillComponent for further use."""
        return self._bill
