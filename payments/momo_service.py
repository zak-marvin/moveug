"""
MTN MoMo Collections/Disbursements integration.

MOMO_SIMULATE (env var, defaults to True) lets you exercise the full booking -> payment
flow without live MTN sandbox credentials or network access -- useful for local/dev
testing (including this Django-only web-view smoke test, which runs in a network-
restricted environment and can't reach momodeveloper.mtn.com at all). Flip it to False
once you're testing against real MTN sandbox credentials.
"""
import base64
import os
import uuid

import requests
from django.conf import settings

SUBSCRIPTION_KEY_COLLECTION = os.getenv("MOMO_COLLECTION_SUB_KEY")
SUBSCRIPTION_KEY_DISBURSEMENT = os.getenv("MOMO_DISBURSEMENT_SUB_KEY")
API_USER = os.getenv("MOMO_API_USER")
API_KEY = os.getenv("MOMO_API_KEY")
TARGET_ENV = os.getenv("MOMO_TARGET_ENV", "sandbox")
BASE_URL = "https://sandbox.momodeveloper.mtn.com" if TARGET_ENV == "sandbox" else "https://momodeveloper.mtn.com"

MOMO_SIMULATE = os.getenv("MOMO_SIMULATE", "True") == "True"


def get_access_token(is_collection=True):
    sub_key = SUBSCRIPTION_KEY_COLLECTION if is_collection else SUBSCRIPTION_KEY_DISBURSEMENT
    url = f"{BASE_URL}/collection/token/" if is_collection else f"{BASE_URL}/disbursement/token/"
    auth_str = base64.b64encode(f"{API_USER}:{API_KEY}".encode()).decode()
    headers = {
        "Ocp-Apim-Subscription-Key": sub_key,
        "Authorization": f"Basic {auth_str}",
    }
    res = requests.post(url, headers=headers, timeout=10)
    return res.json().get("access_token")


def request_to_pay(amount, phone_number, external_id="MoveUG"):
    """Customer -> MoveUG"""
    reference_id = str(uuid.uuid4())
    if MOMO_SIMULATE:
        return {"reference_id": reference_id, "status_code": 202, "simulated": True}

    token = get_access_token(is_collection=True)
    url = f"{BASE_URL}/collection/v1_0/requesttopay"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Reference-Id": reference_id,
        "X-Target-Environment": TARGET_ENV,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY_COLLECTION,
        "Content-Type": "application/json",
    }
    body = {
        "amount": str(amount),
        "currency": "EUR" if TARGET_ENV == "sandbox" else "UGX",
        "externalId": str(external_id),
        "payer": {"partyIdType": "MSISDN", "partyId": phone_number},
        "payerMessage": "Payment for MoveUG delivery",
        "payeeNote": "MoveUG Delivery Payment",
    }
    res = requests.post(url, json=body, headers=headers, timeout=15)
    return {"reference_id": reference_id, "status_code": res.status_code, "simulated": False}


def get_collection_status(reference_id):
    if MOMO_SIMULATE:
        return {"status": "SUCCESSFUL", "simulated": True}

    token = get_access_token(is_collection=True)
    url = f"{BASE_URL}/collection/v1_0/requesttopay/{reference_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Target-Environment": TARGET_ENV,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY_COLLECTION,
    }
    res = requests.get(url, headers=headers, timeout=10)
    return res.json()


def transfer_to_driver(amount, driver_phone):
    """MoveUG -> Driver (85%)"""
    reference_id = str(uuid.uuid4())
    if MOMO_SIMULATE:
        return {"reference_id": reference_id, "status_code": 202, "simulated": True}

    token = get_access_token(is_collection=False)
    url = f"{BASE_URL}/disbursement/v1_0/transfer"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Reference-Id": reference_id,
        "X-Target-Environment": TARGET_ENV,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY_DISBURSEMENT,
        "Content-Type": "application/json",
    }
    body = {
        "amount": str(amount),
        "currency": "EUR" if TARGET_ENV == "sandbox" else "UGX",
        "externalId": "driver_payout",
        "payee": {"partyIdType": "MSISDN", "partyId": driver_phone},
        "payerMessage": "MoveUG driver earnings",
        "payeeNote": "MoveUG payout",
    }
    res = requests.post(url, json=body, headers=headers, timeout=15)
    return {"reference_id": reference_id, "status_code": res.status_code, "simulated": False}
