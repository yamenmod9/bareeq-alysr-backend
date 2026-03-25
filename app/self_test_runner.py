"""
Backend self-test runner.
Executes endpoint and service-function checks and returns a structured report.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.database import db
from app.models import Customer, Merchant, PurchaseRequest, Settlement, Transaction, User
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.merchant_service import MerchantService
from app.services.payment_service import PaymentService
from app.utils.response import BusinessError, ConflictError, NotFoundError


def _status_payload(response) -> Dict[str, Any]:
    try:
        return response.get_json() or {}
    except Exception:
        return {}


def _add_check(
    checks: List[Dict[str, Any]],
    kind: str,
    name: str,
    ok: bool,
    status_code: Optional[int] = None,
    message: str = "",
    duration_ms: float = 0.0,
    details: Optional[Dict[str, Any]] = None,
):
    checks.append(
        {
            "kind": kind,
            "name": name,
            "ok": ok,
            "status_code": status_code,
            "message": message,
            "duration_ms": round(duration_ms, 2),
            "details": details or {},
        }
    )


def _run_endpoint(
    checks: List[Dict[str, Any]],
    client,
    name: str,
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    expected_statuses: Optional[List[int]] = None,
):
    start = time.perf_counter()
    try:
        response = client.open(path=path, method=method, headers=headers or {}, json=body)
        payload = _status_payload(response)
        allowed = expected_statuses or list(range(200, 400))
        ok = response.status_code in allowed
        message = payload.get("message") or payload.get("error") or ""
        _add_check(
            checks,
            kind="endpoint",
            name=f"{method} {path}",
            ok=ok,
            status_code=response.status_code,
            message=message,
            duration_ms=(time.perf_counter() - start) * 1000,
        )
        return response, payload
    except Exception as exc:
        _add_check(
            checks,
            kind="endpoint",
            name=f"{method} {path}",
            ok=False,
            status_code=500,
            message=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.perf_counter() - start) * 1000,
        )
        return None, {}


def _run_function(
    checks: List[Dict[str, Any]],
    name: str,
    fn: Callable[..., Any],
    *args,
    expected_exceptions: tuple[type[Exception], ...] = (),
    **kwargs,
):
    start = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        _add_check(
            checks,
            kind="function",
            name=name,
            ok=True,
            message="ok",
            duration_ms=(time.perf_counter() - start) * 1000,
            details={"result_type": type(result).__name__},
        )
        return result
    except Exception as exc:
        # Keep the self-test transaction healthy after any failed DB operation.
        try:
            db.session.rollback()
        except Exception:
            pass

        if expected_exceptions and isinstance(exc, expected_exceptions):
            _add_check(
                checks,
                kind="function",
                name=name,
                ok=True,
                message=f"expected exception: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
                details={"expected_exception": type(exc).__name__},
            )
            return None

        _add_check(
            checks,
            kind="function",
            name=name,
            ok=False,
            message=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.perf_counter() - start) * 1000,
        )
        return None


def run_full_backend_self_test(app) -> Dict[str, Any]:
    """Run endpoint + service function checks and return a report."""
    started = time.perf_counter()
    checks: List[Dict[str, Any]] = []

    with app.app_context():
        client = app.test_client()

        # Bootstrap test data and login context.
        _run_endpoint(checks, client, "bootstrap", "GET", "/admin/create-test-data", expected_statuses=[200])

        login_customer_response, login_customer_payload = _run_endpoint(
            checks,
            client,
            "customer-login",
            "POST",
            "/auth/login",
            body={"email": "customer@test.com", "password": "password123"},
            expected_statuses=[200],
        )
        customer_token = (login_customer_payload.get("data") or {}).get("access_token")

        login_merchant_response, login_merchant_payload = _run_endpoint(
            checks,
            client,
            "merchant-login",
            "POST",
            "/auth/login",
            body={"email": "merchant@test.com", "password": "password123"},
            expected_statuses=[200],
        )
        merchant_token = (login_merchant_payload.get("data") or {}).get("access_token")

        customer_headers = {"Authorization": f"Bearer {customer_token}"} if customer_token else {}
        merchant_headers = {"Authorization": f"Bearer {merchant_token}"} if merchant_token else {}
        seed_customer_code = None
        seed_customer_user = User.query.filter_by(email="customer@test.com").first()
        if seed_customer_user:
            seed_customer = Customer.query.filter_by(user_id=seed_customer_user.id).first()
            seed_customer_code = seed_customer.customer_code if seed_customer else None

        # Prepare request/transaction IDs for parameterized endpoints.
        accept_request_id = None
        reject_request_id = None
        transaction_id = None
        payment_id = None
        payment_reference = None

        if merchant_token and seed_customer_code:
            accept_req_response, accept_req_payload = _run_endpoint(
                checks,
                client,
                "prepare-accept-request",
                "POST",
                "/merchants/send-purchase-request",
                headers=merchant_headers,
                body={"customer_code": seed_customer_code, "amount": 200, "description": "Self-test accept"},
                expected_statuses=[201],
            )
            accept_request_id = (accept_req_payload.get("data") or {}).get("id")

            reject_req_response, reject_req_payload = _run_endpoint(
                checks,
                client,
                "prepare-reject-request",
                "POST",
                "/merchants/send-purchase-request",
                headers=merchant_headers,
                body={"customer_code": seed_customer_code, "amount": 50, "description": "Self-test reject"},
                expected_statuses=[201],
            )
            reject_request_id = (reject_req_payload.get("data") or {}).get("id")

        if customer_token and accept_request_id:
            accept_response, accept_payload = _run_endpoint(
                checks,
                client,
                "customer-accept",
                "POST",
                f"/customers/purchase-requests/{accept_request_id}/accept",
                headers=customer_headers,
                body={},
                expected_statuses=[200],
            )
            transaction_id = (accept_payload.get("data") or {}).get("transaction_id")

        if customer_token and reject_request_id:
            _run_endpoint(
                checks,
                client,
                "customer-reject",
                "POST",
                f"/customers/purchase-requests/{reject_request_id}/reject",
                headers=customer_headers,
                body={},
                expected_statuses=[200],
            )

        if customer_token and transaction_id:
            pay_response, pay_payload = _run_endpoint(
                checks,
                client,
                "customer-pay",
                "POST",
                f"/customers/transactions/{transaction_id}/pay",
                headers=customer_headers,
                body={"amount": 25, "payment_method": "card"},
                expected_statuses=[200],
            )
            payment_id = (pay_payload.get("data") or {}).get("payment_id")
            payment_reference = (pay_payload.get("data") or {}).get("payment_number")

        # Endpoint inventory checks.
        unique_email = f"selftest_{int(time.time())}@test.com"
        endpoint_specs = [
            ("GET", "/", None, None, [200]),
            ("GET", "/health", None, None, [200]),
            ("GET", "/config", None, None, [200]),
            ("GET", "/debug/files", None, None, [200]),
            ("GET", "/admin/stats", None, None, [200]),
            ("GET", "/admin/create-test-data", None, None, [200]),
            ("POST", "/auth/login", None, {"email": "customer@test.com", "password": "password123"}, [200]),
            ("POST", "/auth/register", None, {"email": unique_email, "password": "password123", "full_name": "Self Test User", "role": "customer"}, [201]),
            ("GET", "/auth/me", customer_headers, None, [200]),
            ("GET", "/customers/me/dashboard", customer_headers, None, [200]),
            ("GET", "/customers/me/transactions", customer_headers, None, [200]),
            ("GET", "/customers/me", customer_headers, None, [200]),
            ("GET", "/customers/pending-requests", customer_headers, None, [200]),
            ("GET", "/customers/limit-history", customer_headers, None, [200]),
            ("GET", "/customers/limits", customer_headers, None, [200]),
            ("GET", "/customers/requests", customer_headers, None, [200]),
            ("GET", "/customers/schedules", customer_headers, None, [200]),
            ("GET", "/customers/my-transactions", customer_headers, None, [200]),
            ("GET", "/customers/upcoming-payments", customer_headers, None, [200]),
            ("GET", "/customers/repayment-plans", customer_headers, None, [200]),
            ("GET", "/customers/transactions", customer_headers, None, [200]),
            ("GET", "/customers/purchase-requests/pending", customer_headers, None, [200]),
            ("GET", "/merchants/stats", merchant_headers, None, [200]),
            ("GET", "/merchants/branches", merchant_headers, None, [200]),
            ("GET", "/merchants/me/dashboard", merchant_headers, None, [200]),
            ("GET", "/merchants/me/transactions", merchant_headers, None, [200]),
            ("GET", "/merchants/me/settlements", merchant_headers, None, [200]),
            ("GET", "/merchants/transactions", merchant_headers, None, [200]),
            ("GET", "/merchants/settlements", merchant_headers, None, [200]),
            ("GET", "/merchants/me", merchant_headers, None, [200]),
            ("GET", "/merchants/purchase-requests", merchant_headers, None, [200]),
            # duplicate health route check
            ("GET", "/health", None, None, [200]),
        ]

        if seed_customer_code:
            endpoint_specs.extend(
                [
                    ("GET", f"/merchants/lookup-customer/{seed_customer_code}", merchant_headers, None, [200]),
                    ("POST", "/merchants/purchase-requests", merchant_headers, {"customer_code": seed_customer_code, "amount": 20, "description": "Endpoint check"}, [201]),
                    ("POST", "/merchants/send-purchase-request", merchant_headers, {"customer_code": seed_customer_code, "amount": 20, "description": "Endpoint check alt"}, [201]),
                ]
            )

        if accept_request_id:
            endpoint_specs.append(("POST", f"/customers/purchase-requests/{accept_request_id}/accept", customer_headers, {}, [200, 400]))
        if reject_request_id:
            endpoint_specs.append(("POST", f"/customers/purchase-requests/{reject_request_id}/reject", customer_headers, {}, [200, 400]))
        if transaction_id:
            endpoint_specs.append(("POST", f"/customers/transactions/{transaction_id}/pay", customer_headers, {"amount": 10, "payment_method": "card"}, [200, 400]))

        for method, path, headers, body, expected in endpoint_specs:
            _run_endpoint(checks, client, f"inventory-{method}-{path}", method, path, headers=headers, body=body, expected_statuses=expected)

        # Service function checks.
        customer_user = User.query.filter_by(email="customer@test.com").first()
        merchant_user = User.query.filter_by(email="merchant@test.com").first()
        customer = Customer.query.filter_by(user_id=customer_user.id).first() if customer_user else None
        merchant = Merchant.query.filter_by(user_id=merchant_user.id).first() if merchant_user else None

        _run_function(checks, "AuthService.authenticate", AuthService.authenticate, "customer@test.com", "password123")
        _run_function(checks, "AuthService.get_user_by_email", AuthService.get_user_by_email, "customer@test.com")
        if customer_user:
            _run_function(checks, "AuthService.get_user_by_id", AuthService.get_user_by_id, customer_user.id)
            _run_function(checks, "AuthService.get_customer_by_user_id", AuthService.get_customer_by_user_id, customer_user.id)
        if merchant_user:
            _run_function(checks, "AuthService.get_merchant_by_user_id", AuthService.get_merchant_by_user_id, merchant_user.id)

        function_customer_email = f"fn_customer_{int(time.time())}@test.com"
        function_merchant_email = f"fn_merchant_{int(time.time())}@test.com"
        fn_customer_pair = _run_function(
            checks,
            "AuthService.register_customer",
            AuthService.register_customer,
            function_customer_email,
            "password123",
            "Function Customer",
        )
        fn_merchant_pair = _run_function(
            checks,
            "AuthService.register_merchant",
            AuthService.register_merchant,
            function_merchant_email,
            "password123",
            "Function Merchant Owner",
            "Function Merchant Shop",
        )

        if fn_customer_pair:
            fn_user, _fn_customer = fn_customer_pair
            unique_national_id = str(int(time.time() * 1000))[-10:]
            _run_function(checks, "AuthService.update_profile", AuthService.update_profile, fn_user.id, full_name="Function Customer Updated")
            _run_function(checks, "AuthService.change_password", AuthService.change_password, fn_user.id, "password123", "password456")
            _run_function(checks, "AuthService.enable_2fa", AuthService.enable_2fa, fn_user.id)
            _run_function(checks, "AuthService.disable_2fa", AuthService.disable_2fa, fn_user.id)
            _run_function(
                checks,
                "AuthService.simulate_nafath_verification",
                AuthService.simulate_nafath_verification,
                fn_user.id,
                unique_national_id,
            )

        if fn_merchant_pair:
            fn_merchant_user, _fn_merchant = fn_merchant_pair
            _run_function(checks, "AuthService.deactivate_user", AuthService.deactivate_user, fn_merchant_user.id)

        if customer:
            _run_function(checks, "CustomerService.get_customer_transactions", CustomerService.get_customer_transactions, customer.id)
            _run_function(checks, "CustomerService.get_customer_pending_requests", CustomerService.get_customer_pending_requests, customer.id)
            _run_function(checks, "CustomerService.get_customer_repayment_plans", CustomerService.get_customer_repayment_plans, customer.id)
            _run_function(checks, "CustomerService.get_customer_all_requests", CustomerService.get_customer_all_requests, customer.id)
            _run_function(checks, "CustomerService.get_customer_schedules", CustomerService.get_customer_schedules, customer.id)
            _run_function(checks, "CustomerService.update_credit_limit", CustomerService.update_credit_limit, customer.id, max(customer.credit_limit, customer.outstanding_balance) + 100)

        if customer and merchant:
            fn_req = _run_function(
                checks,
                "MerchantService.send_purchase_request",
                MerchantService.send_purchase_request,
                merchant.id,
                customer.id,
                "Function Service Item",
                30.0,
                1,
            )
            if fn_req:
                _run_function(checks, "CustomerService.accept_purchase", CustomerService.accept_purchase, customer.id, fn_req.id, 1)
                _run_function(checks, "MerchantService.cancel_purchase_request", MerchantService.cancel_purchase_request, merchant.id, fn_req.id, expected_exceptions=(BusinessError,))

            _run_function(checks, "MerchantService.get_merchant_branches", MerchantService.get_merchant_branches, merchant.id)
            _run_function(checks, "MerchantService.get_merchant_transactions", MerchantService.get_merchant_transactions, merchant.id)
            _run_function(checks, "MerchantService.get_merchant_settlements", MerchantService.get_merchant_settlements, merchant.id)
            _run_function(checks, "MerchantService.get_merchant_pending_requests", MerchantService.get_merchant_pending_requests, merchant.id)
            _run_function(checks, "MerchantService.get_merchant_all_requests", MerchantService.get_merchant_all_requests, merchant.id)
            _run_function(checks, "MerchantService.get_merchant_stats", MerchantService.get_merchant_stats, merchant.id)
            _run_function(checks, "MerchantService.create_branch", MerchantService.create_branch, merchant.id, f"Self Test Branch {int(time.time())}", "Riyadh", "Riyadh", "+966500000000")

            # Process an existing pending settlement if available.
            pending_settlement = Settlement.query.filter_by(merchant_id=merchant.id, status="pending").first()
            if pending_settlement:
                _run_function(checks, "MerchantService.process_settlement", MerchantService.process_settlement, pending_settlement.id)

            # Withdrawal requires available balance.
            merchant_after = Merchant.query.get(merchant.id)
            if merchant_after and merchant_after.balance > 0:
                withdraw_amount = min(merchant_after.balance, 10.0)
                _run_function(
                    checks,
                    "MerchantService.request_withdrawal",
                    MerchantService.request_withdrawal,
                    merchant.id,
                    withdraw_amount,
                    "Bank Test",
                    "123456789",
                    "SA0000000000000000000000",
                )

        if customer:
            _run_function(checks, "PaymentService.get_customer_payments", PaymentService.get_customer_payments, customer.id)
            _run_function(checks, "PaymentService.get_upcoming_payments", PaymentService.get_upcoming_payments, customer.id)
            _run_function(checks, "PaymentService.get_overdue_payments", PaymentService.get_overdue_payments, customer.id)
            _run_function(checks, "PaymentService.calculate_late_status", PaymentService.calculate_late_status, customer.id)

        _run_function(checks, "PaymentService.get_platform_revenue", PaymentService.get_platform_revenue)
        _run_function(checks, "PaymentService.update_overdue_transactions", PaymentService.update_overdue_transactions)

        if payment_id:
            _run_function(checks, "PaymentService.get_payment_by_id", PaymentService.get_payment_by_id, payment_id)
        if payment_reference:
            _run_function(checks, "PaymentService.get_payment_by_reference", PaymentService.get_payment_by_reference, payment_reference)
        if payment_id:
            _run_function(checks, "PaymentService.generate_payment_receipt", PaymentService.generate_payment_receipt, payment_id)

    passed = sum(1 for item in checks if item["ok"])
    failed = len(checks) - passed

    return {
        "success": failed == 0,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "generated_at": datetime.utcnow().isoformat(),
        },
        "checks": checks,
    }
