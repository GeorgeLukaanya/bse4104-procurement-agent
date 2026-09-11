"""SME Procurement-Preparation Agent — Week 2 quotation field extraction baseline.

Framework-free, importable. This package extracts the eleven-field Normalised
Quotation contract (Requirements Document v1.1 glossary) from a Converted
Quotation Document, and does nothing else.

It performs NO arithmetic. Unit normalisation, VAT application, delivery
apportionment, currency conversion, landed cost and ranking all belong to the
deterministic calculator that consumes this output (AI Boundary Matrix v1.1,
Requirements Document v1.1 requirement 6.6).
"""

__all__ = ["__version__"]

__version__ = "0.2.0"
