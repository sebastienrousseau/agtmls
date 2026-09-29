# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
"""Billing service entry point (eval fixture)."""


def total(amounts: list[int]) -> int:
    return sum(amounts)
