from src.models.orm.hibob_purchase_review import HiBobPurchaseReview


def review_to_dict(review: HiBobPurchaseReview) -> dict:
    return {
        "id": review.id,
        "user_id": review.user_id,
        "hibob_employee_id": review.hibob_employee_id,
        "hibob_entry_id": review.hibob_entry_id,
        "entry_date": review.entry_date,
        "description": review.description,
        "amount_cents": review.amount_cents,
        "currency": review.currency,
        "status": review.status,
        "matched_order_id": review.matched_order_id,
        "adjustment_id": review.adjustment_id,
        "resolved_by": review.resolved_by,
        "resolved_at": review.resolved_at,
        "created_at": review.created_at,
    }
