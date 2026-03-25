"""Seed multiple customer and merchant accounts for development.

Usage:
  python seed.py
  python seed.py --customers 25 --merchants 12 --password Seed@123
"""

from __future__ import annotations

import argparse
from typing import Tuple

from app.config import Config
from app.flask_app import flask_app
from app.database import db
from app.models import Branch, Customer, Merchant, User


def _create_customer(index: int, password: str) -> Tuple[User, Customer]:
    email = f"customer{index:03d}@seed.local"
    existing = User.query.filter_by(email=email).first()
    if existing and existing.customer:
        return existing, existing.customer

    user = User(
        email=email,
        full_name=f"Seed Customer {index:03d}",
        phone=f"+96655{index:06d}",
        national_id=f"2{index:09d}"[:10],
        role="customer",
        is_active=True,
        is_verified=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    customer = Customer(
        user_id=user.id,
        credit_limit=Config.DEFAULT_CREDIT_LIMIT,
        available_balance=Config.DEFAULT_CREDIT_LIMIT,
        outstanding_balance=0.0,
        status="active",
    )
    db.session.add(customer)
    return user, customer


def _create_merchant(index: int, password: str) -> Tuple[User, Merchant]:
    email = f"merchant{index:03d}@seed.local"
    existing = User.query.filter_by(email=email).first()
    if existing and existing.merchant:
        return existing, existing.merchant

    user = User(
        email=email,
        full_name=f"Seed Merchant {index:03d}",
        phone=f"+96654{index:06d}",
        national_id=f"1{index:09d}"[:10],
        role="merchant",
        is_active=True,
        is_verified=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    merchant = Merchant(
        user_id=user.id,
        shop_name=f"Seed Shop {index:03d}",
        shop_name_ar=f"متجر تجريبي {index:03d}",
        city="Riyadh",
        status="active",
        is_verified=True,
        business_phone=user.phone,
        business_email=user.email,
    )
    db.session.add(merchant)
    db.session.flush()

    branch = Branch(
        merchant_id=merchant.id,
        name="Main Branch",
        address="Riyadh, Saudi Arabia",
        city="Riyadh",
        is_active=True,
    )
    db.session.add(branch)
    return user, merchant


def run_seed(customers: int, merchants: int, password: str) -> None:
    with flask_app.app_context():
        db.create_all()

        created_customers = 0
        created_merchants = 0

        for i in range(1, customers + 1):
            before = User.query.filter_by(email=f"customer{i:03d}@seed.local").first()
            _create_customer(i, password)
            if before is None:
                created_customers += 1

        for i in range(1, merchants + 1):
            before = User.query.filter_by(email=f"merchant{i:03d}@seed.local").first()
            _create_merchant(i, password)
            if before is None:
                created_merchants += 1

        db.session.commit()

        total_customers = Customer.query.count()
        total_merchants = Merchant.query.count()

        print("\nSeed completed")
        print(f"Created customers: {created_customers}")
        print(f"Created merchants: {created_merchants}")
        print(f"Total customers in DB: {total_customers}")
        print(f"Total merchants in DB: {total_merchants}")
        print(f"Default seed password: {password}")
        print("Tip: customer codes are generated automatically and can be regenerated via POST /customers/me/regenerate-code")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Bareeq Alysr dev data")
    parser.add_argument("--customers", type=int, default=20, help="Number of customer accounts to ensure")
    parser.add_argument("--merchants", type=int, default=10, help="Number of merchant accounts to ensure")
    parser.add_argument("--password", type=str, default="Seed@123", help="Default password for seeded users")
    return parser.parse_args()


if __name__ == "__main__":
    args = _args()
    run_seed(customers=args.customers, merchants=args.merchants, password=args.password)
