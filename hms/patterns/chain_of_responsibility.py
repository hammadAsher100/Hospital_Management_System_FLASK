"""
Chain of Responsibility Pattern — Patient Request Processing
=============================================================
Processes a patient request through a chain of handlers:
  Triage → Diagnosis → Billing

Each handler either enriches the request context and passes it to the
next handler, or short-circuits the chain on an unrecoverable error.

Usage
-----
    from hms.patterns.chain_of_responsibility import PatientRequestChain

    ctx = {
        "patient_id": 42,
        "request_type": "appointment",   # or "admission"
        "priority": "normal",            # "normal" | "urgent" | "emergency"
        "diagnosis": "",
        "bill_id": None,
    }
    result = PatientRequestChain().process(ctx)
    # result["summary"] -> "Triage: Normal | Status: Scheduled | Billing: Pending"
"""

from __future__ import annotations
from abc import ABC, abstractmethod


# ======================================================================== #
#  Abstract Handler                                                          #
# ======================================================================== #

class PatientRequestHandler(ABC):
    """
    Abstract base for all handlers in the chain.

    Each handler stores a reference to the *next* handler.  If it can
    handle the request it does so and (usually) passes the context on;
    if it cannot, it may short-circuit.
    """

    def __init__(self):
        self._next_handler: PatientRequestHandler | None = None

    def set_next(self, handler: "PatientRequestHandler") -> "PatientRequestHandler":
        """
        Chain the next handler and return it so calls can be chained
        fluently::

            triage.set_next(diagnosis).set_next(billing)
        """
        self._next_handler = handler
        return handler

    def handle(self, request_ctx: dict) -> dict:
        """
        Process the request context and pass it to the next handler.

        Subclasses call ``super().handle(request_ctx)`` at the end of
        their own logic to continue the chain.
        """
        if self._next_handler is not None:
            return self._next_handler.handle(request_ctx)
        return request_ctx

    @abstractmethod
    def get_handler_name(self) -> str:
        """Return a short descriptive name for logging."""


# ======================================================================== #
#  Concrete Handlers                                                         #
# ======================================================================== #

class TriageHandler(PatientRequestHandler):
    """
    **Step 1 — Triage**

    Classifies the patient's request by priority and assigns a triage
    level.  Always passes the context to the next handler.

    Sets in context
    ---------------
    ``triage_level`` : str
        ``"Emergency"`` | ``"Urgent"`` | ``"Normal"``
    ``triage_note`` : str
        Human-readable note about the triage decision.
    """

    _PRIORITY_MAP = {
        "emergency": ("Emergency", "Patient requires immediate attention."),
        "urgent":    ("Urgent",    "Patient should be seen within the hour."),
        "normal":    ("Normal",    "Patient queued for standard processing."),
    }

    def get_handler_name(self) -> str:
        return "TriageHandler"

    def handle(self, request_ctx: dict) -> dict:
        priority = str(request_ctx.get("priority", "normal")).lower()
        level, note = self._PRIORITY_MAP.get(priority, ("Normal", "Standard processing."))

        request_ctx["triage_level"] = level
        request_ctx["triage_note"]  = note
        request_ctx.setdefault("handler_log", []).append(
            f"[Triage] level={level} - {note}"
        )
        print(f"[{self.get_handler_name()}] {level}: {note}")
        return super().handle(request_ctx)


class DiagnosisHandler(PatientRequestHandler):
    """
    **Step 2 — Diagnosis**

    Validates that the request has a diagnosis or reason recorded.
    For appointment requests this is the reason for the visit; for
    admission requests it is the admitting diagnosis.

    Sets in context
    ---------------
    ``diagnosis_status`` : str
        ``"Diagnosed"`` | ``"Pending"``
    ``diagnosis_note`` : str
        Human-readable note.
    """

    def get_handler_name(self) -> str:
        return "DiagnosisHandler"

    def handle(self, request_ctx: dict) -> dict:
        diagnosis = str(request_ctx.get("diagnosis", "") or "").strip()
        reason    = str(request_ctx.get("reason", "") or "").strip()

        has_info = bool(diagnosis or reason)
        if has_info:
            status = "Diagnosed"
            note   = f"Clinical information recorded: '{diagnosis or reason}'"
        else:
            status = "Pending"
            note   = "No diagnosis/reason provided — follow-up required."

        request_ctx["diagnosis_status"] = status
        request_ctx["diagnosis_note"]   = note
        request_ctx.setdefault("handler_log", []).append(
            f"[Diagnosis] {status} - {note}"
        )
        print(f"[{self.get_handler_name()}] {status}: {note}")
        return super().handle(request_ctx)


class BillingHandler(PatientRequestHandler):
    """
    **Step 3 — Billing**

    Checks whether a bill has been associated with this request.  If a
    ``bill_id`` is present the step is marked complete; otherwise it is
    flagged as pending so the billing team is notified.

    This is the terminal handler — it does not call ``super().handle()``
    unless a next handler is explicitly set.

    Sets in context
    ---------------
    ``billing_status`` : str
        ``"Billed"`` | ``"Pending"``
    ``billing_note`` : str
        Human-readable note.
    ``summary`` : str
        One-line summary of the full chain result.
    """

    def get_handler_name(self) -> str:
        return "BillingHandler"

    def handle(self, request_ctx: dict) -> dict:
        bill_id = request_ctx.get("bill_id")

        if bill_id:
            status = "Billed"
            note   = f"Bill #{bill_id} has been generated for this request."
        else:
            status = "Pending"
            note   = "No bill generated yet - billing step pending."

        request_ctx["billing_status"] = status
        request_ctx["billing_note"]   = note
        request_ctx.setdefault("handler_log", []).append(
            f"[Billing] {status} - {note}"
        )

        # Build the one-line summary for the UI flash message
        triage    = request_ctx.get("triage_level", "—")
        diagnosis = request_ctx.get("diagnosis_status", "—")
        request_ctx["summary"] = (
            f"Triage: {triage} | Diagnosis: {diagnosis} | Billing: {status}"
        )

        print(f"[{self.get_handler_name()}] {status}: {note}")
        print(f"[PatientRequestChain] Summary -> {request_ctx['summary']}")

        # Pass to next handler if one was chained (extensibility)
        return super().handle(request_ctx)


# ======================================================================== #
#  Chain Facade                                                              #
# ======================================================================== #

class PatientRequestChain:
    """
    Convenience facade that wires the full Triage → Diagnosis → Billing
    chain and exposes a single ``process()`` entry point.

    Example
    -------
    ::

        chain = PatientRequestChain()
        result = chain.process({
            "patient_id":   42,
            "request_type": "appointment",
            "priority":     "urgent",
            "diagnosis":    "Chest pain",
            "bill_id":      None,
        })
        print(result["summary"])
        # "Triage: Urgent | Diagnosis: Diagnosed | Billing: Pending"
    """

    def __init__(self):
        self._triage    = TriageHandler()
        self._diagnosis = DiagnosisHandler()
        self._billing   = BillingHandler()

        # Wire the chain
        self._triage.set_next(self._diagnosis).set_next(self._billing)

    def process(self, request_ctx: dict) -> dict:
        """
        Run the request context through the full handler chain.

        Parameters
        ----------
        request_ctx : dict
            Must contain at minimum:
              - ``patient_id``   (int)
              - ``request_type`` (str) — ``"appointment"`` or ``"admission"``
            Optional keys:
              - ``priority``     (str) — ``"normal"`` | ``"urgent"`` | ``"emergency"``
              - ``diagnosis``    (str)
              - ``reason``       (str) — appointment reason
              - ``bill_id``      (int | None)

        Returns
        -------
        dict
            The enriched context with keys ``triage_level``, ``triage_note``,
            ``diagnosis_status``, ``diagnosis_note``, ``billing_status``,
            ``billing_note``, ``summary``, and ``handler_log``.
        """
        # Ensure required defaults
        request_ctx.setdefault("priority", "normal")
        request_ctx.setdefault("diagnosis", "")
        request_ctx.setdefault("reason", "")
        request_ctx.setdefault("bill_id", None)
        request_ctx.setdefault("handler_log", [])

        return self._triage.handle(request_ctx)
