"""Mock business processors. 5 functions share similar shape with status string."""

def process_user(data):
    status = "pending"
    if data.get("active"):
        status = "active"
    return {"id": data["id"], "status": status}

def process_order(data):
    status = "pending"
    if data.get("paid"):
        status = "paid"
    return {"id": data["id"], "status": status}

def process_payment(data):
    status = "init"
    if data.get("amount", 0) > 0:
        status = "complete"
    return {"id": data["id"], "status": status}

def process_shipment(data):
    status = "pending"
    if data.get("shipped"):
        status = "shipped"
    return {"id": data["id"], "status": status}

def process_refund(data):
    status = "pending"
    if data.get("approved"):
        status = "refunded"
    return {"id": data["id"], "status": status}
