"""Thin Supabase data access for customers, invoices, payments and bills; no business logic."""


def list_customers(client, business_id: str, status: str | None, batch: str | None) -> list[dict]:
    """Return the business's customers, optionally filtered by status and batch, ordered by name."""
    query = client.table("customers").select("*").eq("business_id", business_id)
    if status is not None:
        query = query.eq("status", status)
    if batch is not None:
        query = query.eq("batch", batch)
    return query.order("name").execute().data


def get_customer(client, business_id: str, customer_id: str) -> dict | None:
    """Return one customer scoped to the business, or None if not found."""
    response = (
        client.table("customers")
        .select("*")
        .eq("id", customer_id)
        .eq("business_id", business_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def insert_customer(client, business_id: str, data: dict) -> dict:
    """Insert a customer for the business and return the inserted row."""
    response = client.table("customers").insert({**data, "business_id": business_id}).execute()
    return response.data[0]


def update_customer(client, business_id: str, customer_id: str, data: dict) -> dict | None:
    """Update the given customer fields and return the updated row, or None if not found."""
    if not data:
        raise ValueError("Update data must not be empty")
    response = (
        client.table("customers")
        .update(data)
        .eq("id", customer_id)
        .eq("business_id", business_id)
        .execute()
    )
    return response.data[0] if response.data else None


def list_invoices(
    client,
    business_id: str,
    status: str | None,
    customer_id: str | None,
    period: str | None,
) -> list[dict]:
    """Return the business's invoices, filtered only by the arguments given, ordered by due date."""
    query = client.table("invoices").select("*").eq("business_id", business_id)
    if status is not None:
        query = query.eq("status", status)
    if customer_id is not None:
        query = query.eq("customer_id", customer_id)
    if period is not None:
        query = query.eq("period", period)
    return query.order("due_date").execute().data


def list_invoices_for_customer(client, business_id: str, customer_id: str) -> list[dict]:
    """Return all invoices for one customer, ordered by due date."""
    return (
        client.table("invoices")
        .select("*")
        .eq("business_id", business_id)
        .eq("customer_id", customer_id)
        .order("due_date")
        .execute()
        .data
    )


def existing_periods(client, business_id: str, period: str) -> set[str]:
    """Return the customer_ids that already have an invoice for the given period."""
    response = (
        client.table("invoices")
        .select("customer_id")
        .eq("business_id", business_id)
        .eq("period", period)
        .execute()
    )
    return {row["customer_id"] for row in response.data}


def insert_invoices(client, rows: list[dict]) -> list[dict]:
    """Insert invoice rows (each already carrying business_id) and return the inserted rows."""
    if not rows:
        return []
    return client.table("invoices").insert(rows).execute().data


def list_active_customers(client, business_id: str) -> list[dict]:
    """Return the business's customers with status 'active'."""
    return (
        client.table("customers")
        .select("*")
        .eq("business_id", business_id)
        .eq("status", "active")
        .execute()
        .data
    )


def list_unpaid_invoices(client, business_id: str) -> list[dict]:
    """Return invoices with no paid_at whose status is neither 'paid' nor 'draft', ordered by due date."""
    return (
        client.table("invoices")
        .select("*")
        .eq("business_id", business_id)
        .is_("paid_at", "null")
        .not_.in_("status", ["paid", "draft"])
        .order("due_date")
        .execute()
        .data
    )


def list_payments_for_customer(client, business_id: str, customer_id: str) -> list[dict]:
    """Return one customer's payments (linked through their invoices), most recently received first."""
    invoice_ids = [row["id"] for row in list_invoices_for_customer(client, business_id, customer_id)]
    if not invoice_ids:
        return []
    return (
        client.table("payments")
        .select("*")
        .eq("business_id", business_id)
        .in_("invoice_id", invoice_ids)
        .order("received_at", desc=True)
        .execute()
        .data
    )


def insert_payment(client, row: dict) -> dict:
    """Insert a payment row (dropping customer_id, which the payments table does not have) and return it."""
    clean = {key: value for key, value in row.items() if key != "customer_id"}
    return client.table("payments").insert(clean).execute().data[0]


def update_invoice(client, business_id: str, invoice_id: str, data: dict) -> dict | None:
    """Update invoice fields (e.g. status, paid_at) and return the updated row, or None if not found."""
    response = (
        client.table("invoices")
        .update(data)
        .eq("id", invoice_id)
        .eq("business_id", business_id)
        .execute()
    )
    return response.data[0] if response.data else None


def list_payments_for_month(client, business_id: str, start_iso: str, end_iso: str) -> list[dict]:
    """Return payments received at or after start_iso and before end_iso."""
    return (
        client.table("payments")
        .select("*")
        .eq("business_id", business_id)
        .gte("received_at", start_iso)
        .lt("received_at", end_iso)
        .execute()
        .data
    )


def list_bills(client, business_id: str) -> list[dict]:
    """Return the business's bills ordered by name."""
    return (
        client.table("bills")
        .select("*")
        .eq("business_id", business_id)
        .order("name")
        .execute()
        .data
    )


def get_bill(client, business_id: str, bill_id: str) -> dict | None:
    """Return one bill scoped to the business, or None if not found."""
    response = (
        client.table("bills")
        .select("*")
        .eq("id", bill_id)
        .eq("business_id", business_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def insert_bill(client, business_id: str, data: dict) -> dict:
    """Insert a bill for the business and return the inserted row."""
    response = client.table("bills").insert({**data, "business_id": business_id}).execute()
    return response.data[0]


def update_bill(client, business_id: str, bill_id: str, data: dict) -> dict | None:
    """Update the given bill fields and return the updated row, or None if not found."""
    if not data:
        raise ValueError("Update data must not be empty")
    response = (
        client.table("bills")
        .update(data)
        .eq("id", bill_id)
        .eq("business_id", business_id)
        .execute()
    )
    return response.data[0] if response.data else None
