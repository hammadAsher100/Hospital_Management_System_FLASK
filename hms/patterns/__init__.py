"""
hms.patterns
============
Design-pattern implementations for the Hospital Management System.

Sub-modules (import directly to avoid circular-import issues at startup):
  - hms.patterns.singleton               : DatabaseSingleton  (Singleton Pattern)
  - hms.patterns.factory                 : UserRoleFactory    (Factory Pattern)
  - hms.patterns.decorator               : BillingDecorator   (Decorator Pattern)
  - hms.patterns.chain_of_responsibility : PatientRequestChain (Chain of Responsibility)

Each sub-module is intentionally NOT imported here so that flask.url_for
(used inside factory.py) is never called before the Flask application
context is ready.  Import from the sub-module directly, e.g.::

    from hms.patterns.singleton import DatabaseSingleton
    from hms.patterns.factory   import UserRoleFactory
"""

__all__ = [
    "singleton",
    "factory",
    "decorator",
    "chain_of_responsibility",
]

